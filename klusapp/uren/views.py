import calendar
from datetime import date, time, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.db.models.functions import Lower
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from klussen import afbeeldingen
from klussen.forms import BijlageForm, KlusFotoForm
from klussen.fotoposts import groepeer_in_posts
from klussen.models import Klus
from klussen.views import batch_van_upload, bewaar_bijlage
from medewerkers.models import Medewerker
from medewerkers.rechten import alleen_eigenaar

from . import bezetting, export, kalender, periode, totalen
from .forms import UurblokForm, UurblokFotosForm
from .models import Aanwezigheid, Dagnotitie, Inzet, Klusdag, Uurblok


def _tijd_uit(waarde):
    try:
        return time.fromisoformat(waarde)
    except (TypeError, ValueError):
        return None


def _terug_naar_dag(dag):
    return redirect(f"{reverse('mijn_uren')}?dag={dag.isoformat()}")


WEERGAVEN = {"dag", "week", "maand"}


def _gekozen_weergave(request):
    """Dag is de standaard: de enige weergave die op geen enkele
    schermbreedte hoeft te scrollen. Week en maand kies je erbij."""
    weergave = request.GET.get("weergave")
    return weergave if weergave in WEERGAVEN else "dag"


def _dag_info(datum, blokken, vandaag):
    """Één dag omgezet naar wat het raster direct kan tekenen. Gebruikt door
    zowel de dag- als de weekweergave — alleen het aantal dagen verschilt."""
    van_die_dag = [blok for blok in blokken if blok.datum == datum]
    return {
        "datum": datum,
        "is_vandaag": datum == vandaag,
        "getekend": kalender.plaats_blokken(van_die_dag),
        "totaal": kalender.als_uren(sum(blok.duur_minuten for blok in van_die_dag)),
        "heeft_uren": bool(van_die_dag),
    }


def _maand_erbij(eerste_van_maand, aantal):
    maand_index = eerste_van_maand.month - 1 + aantal
    jaar = eerste_van_maand.year + maand_index // 12
    maand = maand_index % 12 + 1
    return date(jaar, maand, 1)


@login_required
def mijn_uren(request):
    weergave = _gekozen_weergave(request)
    dag = periode.gekozen_dag(request)
    vandaag = periode.vandaag()

    if weergave == "maand":
        return _maand_weergave(request, dag, vandaag)

    if weergave == "week":
        periode_begin = dag - timedelta(days=dag.weekday())
        periode_eind = periode_begin + timedelta(days=6)
    else:
        periode_begin = periode_eind = dag

    blokken = (
        Uurblok.objects.filter(medewerker=request.user, datum__range=(periode_begin, periode_eind))
        .select_related("klus")
        .order_by("begintijd")
    )
    dagen = [
        _dag_info(periode_begin + timedelta(days=n), blokken, vandaag)
        for n in range((periode_eind - periode_begin).days + 1)
    ]

    # Voor de "uren toevoegen"-dialoog die over de agenda heen opent (in
    # plaats van ernaartoe te navigeren, zie kalender.js): begintijd sluit
    # standaard aan op het laatste blok van de dag, net als uurblok_nieuw dat
    # zonder ?van= zou doen.
    laatste_van_dag = max(
        (blok for blok in blokken if blok.datum == dag), key=lambda blok: blok.eindtijd, default=None
    )
    formulier = UurblokForm(
        initial={"datum": dag, "begintijd": laatste_van_dag.eindtijd if laatste_van_dag else None}
    )
    # Zodat je in dezelfde dialoog meteen een foto bij de uren kunt hangen —
    # zie uurblok_nieuw() voor het wegschrijven ervan.
    bijlagenformulier = UurblokFotosForm()

    context = {
        "weergave": weergave,
        "dag": dag,
        "dagen": dagen,
        "formulier": formulier,
        "bijlagenformulier": bijlagenformulier,
        # Met ?dag= erbij, zodat een mislukte post (validatiefout) via
        # periode.gekozen_dag() op dezelfde dag terechtkomt als waar je 'm
        # opende — zie uurblok_nieuw().
        "uurblok_nieuw_actie": f"{reverse('uurblok_nieuw')}?dag={dag.isoformat()}",
        "vakken": kalender.vakken(),
        "uurlabels": kalender.uurlabels(),
        "rasterhoogte": kalender.raster_hoogte(),
        "rijhoogte": kalender.RIJ_H,
        "vandaag": vandaag,
        "totaal_waarde": kalender.als_uren(sum(blok.duur_minuten for blok in blokken)),
    }
    if weergave == "week":
        context.update(
            {
                "maandag": periode_begin,
                "zondag": periode_eind,
                "vorige_week": periode_begin - timedelta(days=7),
                "volgende_week": periode_begin + timedelta(days=7),
                "is_deze_week": periode_begin <= vandaag <= periode_eind,
                "weektotaal": context["totaal_waarde"],
                "vorige": periode_begin - timedelta(days=7),
                "volgende": periode_begin + timedelta(days=7),
                "is_huidige_periode": periode_begin <= vandaag <= periode_eind,
            }
        )
    else:
        context.update(
            {
                "vorige": dag - timedelta(days=1),
                "volgende": dag + timedelta(days=1),
                "is_huidige_periode": dag == vandaag,
            }
        )
    return render(request, "uren/mijn_uren.html", context)


def _maand_weergave(request, dag, vandaag):
    eerste_van_maand = dag.replace(day=1)
    # Zelfde som als de maandwidget op het startscherm — zie uren/totalen.py.
    weken, minuten_per_dag = totalen.maand_per_dag(request.user, eerste_van_maand)

    def hoort_bij_maand(datum):
        return (datum.year, datum.month) == (eerste_van_maand.year, eerste_van_maand.month)

    def dagcel(datum):
        return {
            "datum": datum,
            "in_maand": hoort_bij_maand(datum),
            "is_vandaag": datum == vandaag,
            "totaal": kalender.als_uren(minuten_per_dag[datum]) if datum in minuten_per_dag else None,
        }

    return render(
        request,
        "uren/mijn_uren.html",
        {
            "weergave": "maand",
            "dag": dag,
            "maandraster": [[dagcel(datum) for datum in week] for week in weken],
            "vorige": _maand_erbij(eerste_van_maand, -1),
            "volgende": _maand_erbij(eerste_van_maand, 1),
            "is_huidige_periode": (eerste_van_maand.year, eerste_van_maand.month) == (vandaag.year, vandaag.month),
            # Alleen de dagen van déze maand. `minuten_per_dag` loopt over het
            # hele raster, dus inclusief de rand-dagen uit de vorige en
            # volgende maand — die horen wel in het rooster maar niet in het
            # totaal dat er als "deze maand" boven staat.
            "totaal_waarde": kalender.als_uren(
                sum(minuten for datum, minuten in minuten_per_dag.items() if hoort_bij_maand(datum))
            ),
            "vandaag": vandaag,
        },
    )


@login_required
def uurblok_nieuw(request):
    dag = periode.gekozen_dag(request)
    if request.method == "POST":
        formulier = UurblokForm(request.POST, medewerker=request.user)
        # Bestanden kiezen is optioneel (zie UurblokFotosForm), dus die mogen
        # het opslaan van de uren zelf nooit blokkeren.
        bijlagenformulier = UurblokFotosForm(request.POST, request.FILES)
        if formulier.is_valid() and bijlagenformulier.is_valid():
            blok = formulier.save(commit=False)
            blok.medewerker = request.user
            blok.save()

            # Onbenoemd blijft de dag van het uurblok zelf: een foto die je
            # bij het invullen meteen toevoegt gaat vrijwel altijd over die
            # werkdag, niet per se over vandaag.
            datum = bijlagenformulier.cleaned_data["datum"] or blok.datum
            toelichting = bijlagenformulier.cleaned_data["toelichting"]
            batch = batch_van_upload(bijlagenformulier.cleaned_data["bestanden"])
            for bestand in bijlagenformulier.cleaned_data["bestanden"]:
                # Het bestandenveld biedt alleen foto's aan (accept="image/*"
                # op UurblokFotosForm), maar de server moet dat zelf ook
                # afdwingen: zie klussen.forms.AlleenFotosForm.
                if not afbeeldingen.lijkt_afbeelding(bestand.name):
                    messages.error(request, f"{bestand.name}: hier kan alleen een foto bij.")
                    continue
                try:
                    bewaar_bijlage(bestand, datum, toelichting, blok.klus, blok, request.user, batch)
                except afbeeldingen.BestandNietLeesbaar as probleem:
                    # Het uurblok staat er al; alleen deze foto mislukt, niet de rest.
                    messages.error(request, f"{bestand.name}: {probleem}")

            return _terug_naar_dag(blok.datum)

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            # De "uren toevoegen"-knop opent dit formulier als bottom sheet
            # boven de agenda (zie mijn_uren.html/_uurblokformulier.html) en
            # dient 'm met fetch in i.p.v. een gewone post, juist om bij een
            # foutieve invoer niet de hele pagina te vervangen door de
            # no-javascript-terugvalpagina hieronder — alleen het formulier
            # opnieuw teruggeven, dan blijft de sheet openstaan.
            return render(
                request,
                "uren/_uurblokformulier.html",
                {
                    "formulier": formulier,
                    "bijlagenformulier": bijlagenformulier,
                    "actie": request.get_full_path(),
                    "in_dialoog": True,
                },
            )
    else:
        # Uit de kalender komen begin- en eindtijd mee van het vak waarop je
        # hebt gesleept; anders sluiten we aan op het laatste blok van die dag.
        van = _tijd_uit(request.GET.get("van"))
        tot = _tijd_uit(request.GET.get("tot"))
        if van is None:
            laatste = (
                Uurblok.objects.filter(medewerker=request.user, datum=dag)
                .order_by("eindtijd")
                .last()
            )
            van = laatste.eindtijd if laatste else None
        formulier = UurblokForm(initial={"datum": dag, "begintijd": van, "eindtijd": tot})
        bijlagenformulier = UurblokFotosForm()
    return render(
        request,
        "uren/uurblok_form.html",
        {"formulier": formulier, "bijlagenformulier": bijlagenformulier, "dag": dag},
    )


def _uurblok_detail_context(request, pk, formulier_override=None, bewerken=None):
    """De context voor het uurblok-detailscherm — gedeeld door de volledige
    pagina (`uurblok_detail`), het fragment voor de bottom sheet op de agenda
    (`uurblok_detail_paneel`) en een mislukte opslagpoging (`uurblok_bewerken`).

    De eigenaar mag elk blok bekijken — anders klapt de doorklik vanuit het
    planbord stuk. Bewerken blijft van de medewerker zelf: een gecorrigeerd
    uurblok waar de mede­werker niets van weet levert discussie op die deze app
    juist moet voorkomen.

    SPEC §5, view-first: klikken op een blok toont precies hetzelfde scherm
    als bewerken (_uurblokformulier.html, met de waarden ingevuld), maar niet
    bewerkbaar, met een bewerkknop. Dat "op slot zetten" gebeurt hier op de
    velden zelf (disabled), net als bij het eigen profiel — zie
    medewerkers.views.mijn_profiel voor hetzelfde patroon.
    """
    blok = get_object_or_404(Uurblok.objects.select_related("klus", "medewerker"), pk=pk)
    if blok.medewerker_id != request.user.pk and not request.user.is_eigenaar:
        raise Http404
    mag_bewerken = blok.medewerker_id == request.user.pk

    if bewerken is None:
        bewerken = mag_bewerken and request.GET.get("bewerken") == "1"

    uurblok_formulier = formulier_override or UurblokForm(instance=blok)
    if not bewerken:
        for veld in uurblok_formulier.fields.values():
            veld.widget.attrs["disabled"] = True

    bijlagen = blok.bijlagen.zichtbaar_voor(request.user).select_related("toegevoegd_door").order_by("-toegevoegd_op")
    return {
        "blok": blok,
        "duur": kalender.als_uren(blok.duur_minuten),
        "mag_bewerken": mag_bewerken,
        "alleen_lezen": not bewerken,
        "uurblok_formulier": uurblok_formulier,
        "bewerk_knop_href": "?bewerken=1" if mag_bewerken else "",
        "foto_posts": groepeer_in_posts(los for los in bijlagen if los.is_foto),
        "document_bijlagen": [los for los in bijlagen if not los.is_foto],
        "formulier": BijlageForm(),
        "foto_formulier": KlusFotoForm(),
        "upload_url": reverse("bijlage_toevoegen"),
        "terug": request.get_full_path(),
    }


@login_required
def uurblok_detail(request, pk):
    """Het blok bekijken, niet bewerken (SPEC §5: view-first)."""
    return render(request, "uren/uurblok_detail.html", _uurblok_detail_context(request, pk))


@login_required
def uurblok_detail_paneel(request, pk):
    """Zelfde inhoud als `uurblok_detail`, maar alleen het fragment: de agenda
    (static/js/kalender.js) haalt dit op via fetch om in de bottom sheet te
    tonen, in plaats van naar een nieuwe pagina te navigeren."""
    context = _uurblok_detail_context(request, pk)
    context["in_dialoog"] = True
    return render(request, "uren/_uurblokdetail_inhoud.html", context)


@login_required
def uurblok_bewerken(request, pk):
    # Een medewerker komt alleen bij zijn eigen blokken; die van een ander
    # bestaan voor hem niet.
    blok = get_object_or_404(Uurblok, pk=pk, medewerker=request.user)
    if request.method != "POST":
        # Geen los bewerkscherm meer: dit is dezelfde pagina als bekijken,
        # alleen opengezet — zie _uurblok_detail_context hierboven.
        return redirect(f"{reverse('uurblok_detail', args=[pk])}?bewerken=1")

    formulier = UurblokForm(request.POST, instance=blok)
    if formulier.is_valid():
        formulier.save()
        return _terug_naar_dag(formulier.instance.datum)

    # Bij een fout terug naar hetzelfde scherm, open en met de foutmelding
    # erbij (zie _uurblokformulier.html), i.p.v. een leeg formulier opnieuw
    # te tonen.
    context = _uurblok_detail_context(request, pk, formulier_override=formulier, bewerken=True)
    return render(request, "uren/uurblok_detail.html", context)


@login_required
def uurblok_verwijderen(request, pk):
    blok = get_object_or_404(Uurblok, pk=pk, medewerker=request.user)
    dag = blok.datum
    if request.method == "POST":
        blok.delete()
    return _terug_naar_dag(dag)


@alleen_eigenaar
def planbord(request):
    """Wie staat deze week waar — het scherm dat Maarten elke ochtend opent.

    Rijen zijn medewerkers en kolommen zijn dagen, niet andersom (SPEC §5):
    met zes man op één dag wordt een dagkalender zo smal dat er per blok nog
    een pixel of vijftien overblijft en niemand meer ziet wat er staat. Daarom
    ook geen kalender.plaats_blokken hier: dat rekent plekken uit op een
    tijdas, terwijl een cel op dit bord een stapeltje chips is.
    """
    week = periode.week_context(request)

    # Filter op één klus, via "Filter op klus" onder het bord. Dan staan
    # alleen de blokken van die klus erop en tellen de totalen alleen die
    # uren: "wie heeft deze week hoeveel aan Tuin Vermeer gedaan". Het wisselen
    # zelf doet static/js/planbordfilter.js zonder de pagina te herladen; het
    # bord bevat daarom altijd álle blokken, en een verborgen blok krijgt
    # hidden. ?klus=<pk> in het adres is waar dat script de keuze bewaart,
    # zodat bladeren, verversen en het terugpijltje hem onthouden.
    gekozen_klus = None
    if request.GET.get("klus", "").isdigit():
        gekozen_klus = Klus.objects.filter(pk=request.GET["klus"]).first()

    # Eén query voor de hele week, daarna groeperen in Python. Zes mensen en
    # een paar honderd blokken — daar weegt een aggregatie per cel niet tegen
    # op, en de index op (datum, medewerker) dekt precies deze filter.
    blokken = (
        Uurblok.objects.filter(datum__range=(week["maandag"], week["zondag"]))
        .select_related("klus", "medewerker")
        .order_by("begintijd")
    )
    per_cel = {}
    # Alle klussen van de week, ook met een filter aan: dat is de lijst
    # waaruit je kiest, en die mag niet krimpen tot die ene.
    klussen_in_beeld = {}
    for blok in blokken:
        klussen_in_beeld[blok.klus_id] = blok.klus
        per_cel.setdefault((blok.medewerker_id, blok.datum), []).append(blok)
    if gekozen_klus:
        klussen_in_beeld[gekozen_klus.pk] = gekozen_klus

    def zichtbaar(blok):
        return gekozen_klus is None or blok.klus_id == gekozen_klus.pk

    dagminuten = dict.fromkeys(week["dagen"], 0)
    # Zonder filter: bepaalt welke weekenddag smal wordt. Anders verspringen
    # de kolommen bij elke filterkeuze.
    alle_dagminuten = dict.fromkeys(week["dagen"], 0)
    rijen = []
    # Ook wie niets schreef krijgt een rij: "wie staat er níét ingepland" is
    # net zo goed de vraag waarvoor dit scherm bestaat.
    for medewerker in Medewerker.objects.filter(uit_dienst_sinds__isnull=True):
        dagen, weekminuten = [], 0
        for datum in week["dagen"]:
            cel = per_cel.get((medewerker.pk, datum), [])
            minuten = sum(blok.duur_minuten for blok in cel if zichtbaar(blok))
            weekminuten += minuten
            dagminuten[datum] += minuten
            alle_dagminuten[datum] += sum(blok.duur_minuten for blok in cel)
            dagen.append(
                {
                    "datum": datum,
                    "is_vandaag": datum == week["vandaag"],
                    "blokken": [
                        {
                            "blok": blok,
                            "kleur": kalender.kleur_van(blok.klus),
                            "duur": kalender.als_uren(blok.duur_minuten),
                            "uren": kalender.als_decimaal(blok.duur_minuten),
                            "zichtbaar": zichtbaar(blok),
                        }
                        for blok in cel
                    ],
                    "totaal": kalender.als_uren(minuten) if minuten else "",
                }
            )
        rijen.append(
            {
                "medewerker": medewerker,
                "kleur": kalender.medewerker_kleur_van(medewerker),
                "dagen": dagen,
                "weektotaal": kalender.als_uren(weekminuten) if weekminuten else "",
                "heeft_uren": weekminuten > 0,
            }
        )

    # Een zaterdag of zondag waarop niemand werkte, krijgt een smalle kolom:
    # daar valt niets te lezen, en de ruimte gaat naar de namen en de dagen
    # die wel gevuld zijn. Een lege doordeweekse dag blijft breed — dat er
    # op een dinsdag niemand stond, is juist iets om te zien.
    smal = {
        datum for datum, minuten in alle_dagminuten.items() if datum.weekday() >= 5 and not minuten
    }
    for rij in rijen:
        for dagcel in rij["dagen"]:
            dagcel["smal"] = dagcel["datum"] in smal
    kolommen = [BORD_SMAL if datum in smal else BORD_DAG for datum in week["dagen"]]

    return render(
        request,
        "uren/planbord.html",
        {
            **week,
            "rijen": rijen,
            "bordkolommen": " ".join([f"{BORD_NAAM}px"] + [
                f"{breedte}px" if breedte == BORD_SMAL else f"minmax({breedte}px,1fr)"
                for breedte in kolommen
            ] + [f"{BORD_WEEK}px"]),
            "bordbreedte": BORD_NAAM + sum(kolommen) + BORD_WEEK,
            "kopdagen": [
                {
                    "datum": datum,
                    "is_vandaag": datum == week["vandaag"],
                    "smal": datum in smal,
                    "totaal": kalender.als_uren(minuten) if minuten else "",
                }
                for datum, minuten in dagminuten.items()
            ],
            # De kleur draagt op deze breedte de klusidentiteit (SPEC §5), dus
            # hoort er een legenda onder die vertelt welke kleur wat is. Een
            # tik op een klus daarin filtert het bord.
            "legenda": [
                {
                    "klus": klus,
                    "kleur": kalender.kleur_van(klus),
                    "actief": gekozen_klus is not None and klus.pk == gekozen_klus.pk,
                }
                for klus in sorted(klussen_in_beeld.values(), key=lambda klus: klus.naam.lower())
            ],
            "gekozen_klus": gekozen_klus,
            # achter de bladerknoppen, zodat het filter meegaat naar een andere week
            "filter_query": f"&klus={gekozen_klus.pk}" if gekozen_klus else "",
            "weektotaal": kalender.als_uren(sum(dagminuten.values())),
        },
    )


# Kolombreedtes van het planbord, in px. De namenkolom is zo breed dat een
# naam als "Youssef el Amrani" op één regel past: een naam over twee regels
# maakte de hele rij hoger dan zijn uurblokken nodig hadden.
BORD_NAAM = 176
# Zo breed dat een werkweek met lege zaterdag en zondag precies in de vaste
# kaartbreedte past (.kaart in app.css): breder, en het bord gaat op een
# laptop weer horizontaal scrollen.
BORD_DAG = 124
BORD_SMAL = 52
# Het weektotaal per persoon, rechts: spiegelt de regel "Per dag" onderaan.
# Stond eerst als derde regel in de naamcel en maakte die hoger dan nodig.
BORD_WEEK = 72


# Twee weergaven. "Deze week": zeven dagen die precies in de vaste
# kaartbreedte passen (.kaart in app.css, 1040px), met ruimte voor
# "tandarts 12.30" in de cel. "Doorlopend": het hele jaar, 1 januari tot en
# met 31 december, waar je opzij doorheen scrolt zoals in de Excel; hij
# opent op vandaag. De breedte is per dag, in px.
PLANNING_WEERGAVEN = {"week": 112, "doorlopend": 76}
PLANNING_STANDAARD_WEERGAVE = "doorlopend"
# Een heel jaar voor twintig man is ruim 7000 cellen; een grotere post is
# geknoei, geen selectie.
PLANNING_MAX_CELLEN = 8000


def _zelfde_dag_in(dag, jaar):
    """Dezelfde datum een jaar eerder of later; 29 februari wordt de 28e."""
    try:
        return dag.replace(year=jaar)
    except ValueError:
        return dag.replace(year=jaar, day=28)


def _planning_weergave(request):
    weergave = request.GET.get("weergave")
    return weergave if weergave in PLANNING_WEERGAVEN else PLANNING_STANDAARD_WEERGAVE


@alleen_eigenaar
def aanwezigheid(request):
    """De werkplanning: wie is er wanneer, als rooster over meerdere weken.

    Vervangt de Excel "Werkplanning" van Maarten: mensen als rijen, dagen als
    kolommen, groen en rood, en bovenaan per dag hoeveel man er is. Dat getal
    tikte hij met de hand in en klopte op een kwart van de dagen niet; hier
    telt het zichzelf (uren/bezetting.py).

    Alleen voor de eigenaar: de medewerkers zagen de Excel ook niet, en
    Maarten wil dat zo houden (gesprek 01-10-2026). Gemaakt voor een laptop —
    op een telefoon scrolt het bord opzij, maar daar is het niet voor.

    Alle zeven dagen staan erop, zondag ook: in de Excel werd er nooit op
    zondag gepland, maar Thijmen wil hem erbij (01-10-2026). Zonder vaste
    werkdag is hij gewoon leeg.
    """
    weergave = _planning_weergave(request)

    if request.method == "POST":
        _planning_opslaan(request)
        # Terug naar dezelfde weken, als GET: verversen mag de post niet
        # nog een keer versturen.
        dag = _datum_uit(request.POST.get("terug")) or periode.vandaag()
        extra = ",".join(pk for pk in request.GET.get("extra", "").split(",") if pk.isdigit())
        return redirect(
            f"{reverse('aanwezigheid')}?dag={dag.isoformat()}&weergave={weergave}"
            + (f"&extra={extra}" if extra else "")
        )

    dag = periode.gekozen_dag(request)
    vandaag = periode.vandaag()
    maandag, _ = periode.week_van(dag)
    if weergave == "doorlopend":
        eerste, laatste = date(dag.year, 1, 1), date(dag.year, 12, 31)
        vorige, volgende = _zelfde_dag_in(dag, dag.year - 1), _zelfde_dag_in(dag, dag.year + 1)
    else:
        # max(): de week van 1 januari 2000 begint in 1999, buiten het
        # bereik van periode.binnen_bereik.
        eerste, laatste = max(maandag, periode.EERSTE_DAG), maandag + timedelta(days=6)
        vorige, volgende = maandag - timedelta(weeks=1), maandag + timedelta(weeks=1)
    dagen = [eerste + timedelta(days=n) for n in range((laatste - eerste).days + 1)]
    medewerkers = bezetting.medewerkers_tussen(dagen[0], dagen[-1])
    cellen = bezetting.rooster(medewerkers, dagen)
    feest = bezetting.nederlandse_feestdagen_tussen(dagen[0], dagen[-1])
    notities = {n.datum: n.tekst for n in Dagnotitie.objects.filter(datum__range=(dagen[0], dagen[-1]))}

    kopdagen = []
    for k, datum in enumerate(dagen):
        kolom = [cellen[(m.pk, datum)] for m in medewerkers]
        kopdagen.append(
            {
                "datum": datum,
                "index": k,
                "is_vandaag": datum == vandaag,
                "is_weekstart": datum.weekday() == 0 and k > 0,
                "is_zaterdag": datum.weekday() == 5,
                "feestdag": feest.get(datum, ("", False))[0],
                "feestdag_vrij": feest.get(datum, ("", False))[1],
                "notitie": notities.get(datum, ""),
                "aanwezig": sum(1 for c in kolom if c.stand == bezetting.AANWEZIG),
                "in_dienst": sum(1 for c in kolom if c.stand != bezetting.BUITEN),
            }
        )
    rijen = [
        {"medewerker": m, "cellen": [cellen[(m.pk, datum)] for datum in dagen]} for m in medewerkers
    ]
    klusrijen = _klusrijen(request, dagen, cellen.values())
    for kopdag in kopdagen:
        kopdag["klussen"] = sum(1 for rij in klusrijen if rij["cellen"][kopdag["index"]]["gepland"])

    breedte = PLANNING_WEERGAVEN[weergave]
    return render(
        request,
        "uren/aanwezigheid.html",
        {
            "dag": dag,
            "vandaag": vandaag,
            "maandag": maandag,
            "eerste": dagen[0],
            "laatste": dagen[-1],
            "weergave": weergave,
            "vorige": vorige,
            "volgende": volgende,
            "is_huidige_periode": dagen[0] <= vandaag <= dagen[-1],
            # de kolom waar de doorlopende weergave bij openen heen scrolt:
            # vandaag als dat in dit jaar valt, anders de gekozen dag
            "startkolom": ((vandaag if dagen[0] <= vandaag <= dagen[-1] else dag) - dagen[0]).days,
            "kopdagen": kopdagen,
            "rijen": rijen,
            "bordkolommen": f"{BORD_NAAM}px repeat({len(dagen)}, minmax({breedte}px, 1fr))",
            "bordbreedte": BORD_NAAM + breedte * len(dagen),
            "redenen": Aanwezigheid.Reden.choices,
            "klussen": _planbare_klussen(cellen.values()),
            "klusrijen": klusrijen,
            # klussen die er op verzoek bij staan zonder planning (?extra=),
            # zodat de links ze vasthouden
            "extra": ",".join(str(r["klus"].pk) for r in klusrijen if r["extra"]),
        },
    )


SOORT_VOLGORDE = {"onderhoud": 0, "van_ee": 1, "aanleg": 2}


def _klusrijen(request, dagen, cellen):
    """De klussenregels onder de mensen, zoals in de Excel.

    Niet elke lopende klus: met honderd klussen maal 365 dagen wordt de
    pagina onwerkbaar. Wel elke klus die in deze periode gepland staat of
    waar iemand op staat, plus wat je zelf toevoegt met "Klus toevoegen"
    (?extra=, komma-gescheiden). Onderhoud en Van Ee bovenaan: die lopen het
    hele jaar door, net als in de Excel.
    """
    van, tot = dagen[0], dagen[-1]
    gepland = {}
    for klusdag in Klusdag.objects.filter(datum__range=(van, tot)):
        gepland[(klusdag.klus_id, klusdag.datum)] = klusdag.notitie
    mensen = {}
    for cel in cellen:
        for klus in cel.klussen:
            mensen[(klus.pk, cel.datum)] = mensen.get((klus.pk, cel.datum), 0) + 1

    extra = {int(pk) for pk in request.GET.get("extra", "").split(",") if pk.isdigit()}
    met_data = {pk for pk, _ in gepland} | {pk for pk, _ in mensen}
    klussen = sorted(
        Klus.objects.filter(pk__in=met_data | extra),
        key=lambda k: (SOORT_VOLGORDE.get(k.soort, 9), k.naam.lower()),
    )
    rijen = []
    for klus in klussen:
        klus.kleur = kalender.kleur_van(klus)
        rijen.append(
            {
                "klus": klus,
                "extra": klus.pk not in met_data,
                "cellen": [
                    {
                        "datum": datum,
                        "gepland": (klus.pk, datum) in gepland,
                        "notitie": gepland.get((klus.pk, datum), ""),
                        "mensen": mensen.get((klus.pk, datum), 0),
                    }
                    for datum in dagen
                ],
            }
        )
    return rijen


def _planbare_klussen(cellen):
    """De klussen in het venster: alle lopende, plus een afgeronde die in
    deze weken nog op iemand staat — anders verdwijnt hij bij opslaan
    ongemerkt uit die cel. Lopend eerst, dan op naam, net als de
    klussenlijst."""
    al_gepland = {klus.pk for cel in cellen for klus in cel.klussen}
    klussen = list(Klus.objects.filter(Q(actief=True) | Q(pk__in=al_gepland)))
    for klus in klussen:
        klus.kleur = kalender.kleur_van(klus)
    return klussen


def _planning_opslaan(request):
    """Eén post uit de werkplanning wegschrijven: een selectie cellen, of de
    notitie bij een dag.

    Een cel komt binnen als "medewerker-id:JJJJ-MM-DD". Wat niet te lezen is,
    van iemand die niet bestaat of op een dag dat hij niet in dienst is,
    slaan we over in plaats van de hele post te laten mislukken: de rest van
    de selectie is wél goed bedoeld.
    """
    if request.POST.get("actie") == "klusdagen":
        _klusdagen_opslaan(request)
        return

    if request.POST.get("actie") == "notitie":
        datum = _datum_uit(request.POST.get("datum"))
        if not datum:
            return
        tekst = request.POST.get("tekst", "").strip()[:120]
        if tekst:
            Dagnotitie.objects.update_or_create(datum=datum, defaults={"tekst": tekst})
        else:
            Dagnotitie.objects.filter(datum=datum).delete()
        return

    stand = request.POST.get("stand")
    if stand not in {"standaard", "ja", "nee"}:
        return
    reden = request.POST.get("reden", "")
    if stand != "nee" or reden not in Aanwezigheid.Reden.values:
        reden = ""
    opmerking = request.POST.get("opmerking", "").strip()[:200]

    gevraagd = set()
    for waarde in request.POST.getlist("cel")[:PLANNING_MAX_CELLEN]:
        pk, _, datum = waarde.partition(":")
        datum = _datum_uit(datum)
        if pk.isdigit() and datum:
            gevraagd.add((int(pk), datum))
    medewerkers = Medewerker.objects.in_bulk({pk for pk, _ in gevraagd})

    # De klussen alleen aanraken als het venster dat zegt. Kies je tien
    # cellen met elk een andere klus en zet je ze alleen op "aanwezig", dan
    # moeten hun klussen blijven staan (static/js/werkplanning.js).
    klussen_wijzigen = request.POST.get("klussen_wijzigen") == "1"
    klus_ids = [pk for pk in request.POST.getlist("klus") if pk.isdigit()]
    klussen = list(Klus.objects.filter(pk__in=klus_ids)) if klussen_wijzigen else []
    if gevraagd:
        dagen = [datum for _, datum in gevraagd]
        vrij = bezetting.feestdagen_tussen(min(dagen), max(dagen))

    for pk, datum in gevraagd:
        medewerker = medewerkers.get(pk)
        if medewerker is None or not bezetting.in_dienst_op(medewerker, datum):
            continue
        if stand == "standaard":
            Aanwezigheid.objects.filter(medewerker=medewerker, datum=datum).delete()
        else:
            # update_or_create: op (medewerker, datum) ligt een unieke
            # sleutel, en een dubbel verstuurd formulier mag daar niet op
            # stuklopen.
            Aanwezigheid.objects.update_or_create(
                medewerker=medewerker,
                datum=datum,
                defaults={"aanwezig": stand == "ja", "reden": reden, "opmerking": opmerking},
            )

        inzet = Inzet.objects.filter(medewerker=medewerker, datum=datum)
        if stand == "nee":
            # wie afwezig is, gaat nergens heen
            inzet.delete()
            continue
        if not klussen_wijzigen:
            continue
        inzet.exclude(klus__in=klussen).delete()
        for klus in klussen:
            Inzet.objects.get_or_create(medewerker=medewerker, datum=datum, klus=klus)
        # Op een klus gezet op een dag dat hij volgens rooster vrij is (een
        # zaterdag, een oproepkracht): dan is hij er dus wél.
        if klussen and stand == "standaard":
            if bezetting.cel(medewerker, datum, feestdag=vrij.get(datum, "")).stand != bezetting.AANWEZIG:
                Aanwezigheid.objects.update_or_create(
                    medewerker=medewerker, datum=datum, defaults={"aanwezig": True, "reden": "", "opmerking": ""}
                )


def _klusdagen_opslaan(request):
    """Een selectie cellen uit de klussenregels: gepland of niet, met een
    notitie. Een cel komt binnen als "klus-id:JJJJ-MM-DD".

    De notitie alleen overschrijven als het venster dat zegt: kies je vijf
    dagen Van Ee met elk een andere locatie en zet je ze alleen op gepland,
    dan blijven die locaties staan."""
    gepland = request.POST.get("gepland")
    if gepland not in {"ja", "nee"}:
        return
    notitie_wijzigen = request.POST.get("notitie_wijzigen") == "1"
    notitie = request.POST.get("notitie", "").strip()[:120]

    gevraagd = set()
    for waarde in request.POST.getlist("klusdag")[:PLANNING_MAX_CELLEN]:
        pk, _, datum = waarde.partition(":")
        datum = _datum_uit(datum)
        if pk.isdigit() and datum:
            gevraagd.add((int(pk), datum))
    klussen = Klus.objects.in_bulk({pk for pk, _ in gevraagd})

    for pk, datum in gevraagd:
        klus = klussen.get(pk)
        if klus is None:
            continue
        if gepland == "nee":
            Klusdag.objects.filter(klus=klus, datum=datum).delete()
            continue
        klusdag, _ = Klusdag.objects.get_or_create(klus=klus, datum=datum)
        if notitie_wijzigen and klusdag.notitie != notitie:
            klusdag.notitie = notitie
            klusdag.save(update_fields=["notitie", "gewijzigd_op"])


def _datum_uit(waarde):
    try:
        return periode.binnen_bereik(date.fromisoformat(waarde))
    except (TypeError, ValueError):
        return None


def _gekozen_periode(request, vandaag):
    """Begin- en einddatum (beide inclusief) uit ?van= en ?tot=.

    Zonder geldige periode valt het terug op ?maand=JJJJ-MM — de oude
    maandkiezer, zodat bewaarde links blijven werken — en anders op de
    lopende week: De Groene M maakt elke week de lijst op van wat er gedaan
    is, en de administratie maakt daar de facturen van (gesprek Maarten,
    01-10-2026). Een omgedraaide periode wordt rechtgezet in plaats van een
    lege export op te leveren."""
    van, tot = _datum_uit(request.GET.get("van")), _datum_uit(request.GET.get("tot"))
    if van and tot:
        return (van, tot) if van <= tot else (tot, van)

    try:
        jaar, maand = (int(deel) for deel in request.GET.get("maand", "").split("-", 1))
        eerste = periode.binnen_bereik(date(jaar, maand, 1))
        if eerste is None:
            raise ValueError
    except (TypeError, ValueError):
        return periode.week_van(vandaag)
    return eerste, eerste.replace(day=calendar.monthrange(eerste.year, eerste.month)[1])


def _is_hele_week(van, tot):
    return van.weekday() == 0 and tot == van + timedelta(days=6)


def _is_hele_maand(van, tot):
    return (
        van.day == 1
        and (van.year, van.month) == (tot.year, tot.month)
        and tot.day == calendar.monthrange(tot.year, tot.month)[1]
    )


@login_required
def urenexport(request):
    """Exportscherm voor de boekhouder: uren van een gekozen periode als Excel.

    De periode kies je met begin- en einddatum in een kalender
    (static/js/periodekalender.js); standaard is dat de lopende week, want
    zo werkt de administratie (zie _gekozen_periode). Een maand kan nog
    altijd, met de snelkeuzes of de kalender. Maarten heeft op 15-09-2026 bevestigd dat het bestand
    Excel moet zijn, geen CSV, zodat de boekhouding er verder in kan werken.

    Alleen de eigenaar mag dit openen: de boekhouder krijgt geen account in de
    app, hij krijgt het gedownloade bestand toegestuurd (SPEC §2, punt 6).
    """
    if not request.user.is_eigenaar:
        raise Http404

    vandaag = timezone.localdate()
    van, tot = _gekozen_periode(request, vandaag)
    hele_maand = _is_hele_maand(van, tot)
    hele_week = _is_hele_week(van, tot)

    # Alleen cijfers: ?medewerker=bla liet het filter hieronder een 500
    # geven. Een onbekend getal levert gewoon een lege lijst op.
    medewerker_pk = request.GET.get("medewerker", "")
    if not medewerker_pk.isdigit():
        medewerker_pk = ""
    blokken = (
        Uurblok.objects.filter(datum__range=(van, tot))
        .select_related("medewerker", "klus")
        .order_by(
            "medewerker__first_name", "medewerker__last_name", "medewerker__username", "datum", "begintijd"
        )
    )
    if medewerker_pk:
        blokken = blokken.filter(medewerker__pk=medewerker_pk)
    blokken = list(blokken)

    if request.GET.get("download") == "1":
        if hele_maand:
            bladtitel, bestandsnaam = f"Uren {van:%m-%Y}", f"uren-{van:%Y-%m}"
        elif hele_week:
            jaar, week, _ = van.isocalendar()
            bladtitel, bestandsnaam = f"Uren week {week} {jaar}", f"uren-{jaar}-week-{week:02d}"
        else:
            bladtitel = f"Uren {van:%d-%m-%Y} - {tot:%d-%m-%Y}"
            bestandsnaam = f"uren-{van:%Y-%m-%d}-tot-{tot:%Y-%m-%d}"
        boek = export.werkboek_bouwen(blokken, bladtitel)
        antwoord = HttpResponse(
            export.werkboek_als_bytes(boek),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        antwoord["Content-Disposition"] = f'attachment; filename="{bestandsnaam}.xlsx"'
        return antwoord

    totalen = []
    for blok in blokken:
        if not totalen or totalen[-1]["medewerker"] != blok.medewerker:
            totalen.append({"medewerker": blok.medewerker, "minuten": 0})
        totalen[-1]["minuten"] += blok.duur_minuten
    for regel in totalen:
        regel["totaal"] = kalender.als_uren(regel["minuten"])

    vorige_maand_eind = vandaag.replace(day=1) - timedelta(days=1)
    deze_week = periode.week_van(vandaag)
    vorige_week = periode.week_van(vandaag - timedelta(days=7))
    return render(
        request,
        "uren/export.html",
        {
            "van": van,
            "tot": tot,
            "hele_maand": hele_maand,
            "hele_week": hele_week,
            "weeknummer": van.isocalendar()[1],
            "medewerker_pk": medewerker_pk,
            # Snelkeuzes onder de kalender: per week, zoals de administratie
            # werkt, en de maand voor wie toch een maand wil.
            "snelkeuzes": [
                ("Deze week", *deze_week),
                ("Vorige week", *vorige_week),
                ("Deze maand", vandaag.replace(day=1), vandaag.replace(
                    day=calendar.monthrange(vandaag.year, vandaag.month)[1])),
                ("Vorige maand", vorige_maand_eind.replace(day=1), vorige_maand_eind),
            ],
            # Iedereen die uren kán schrijven, niet alleen rol "medewerker":
            # Maarten doet zelf het onderhoud — zes tot acht adressen op een
            # dag — dus zijn uren staan gewoon in het bestand. Zonder hem in
            # deze lijst is hij de enige die niet op zichzelf kan filteren.
            # Ook wie uit dienst is blijft staan: je exporteert ook maanden
            # van vóór zijn vertrek. Zelfde volgorde als de regels in het
            # werkboek (zie de order_by op `blokken` hierboven).
            "medewerkers": Medewerker.objects.order_by(
                Lower("first_name"), Lower("last_name"), "username"
            ),
            "totalen": totalen,
        },
    )
