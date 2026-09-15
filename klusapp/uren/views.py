import calendar
from datetime import date, time, timedelta

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from klussen.forms import BijlageForm
from medewerkers.models import Medewerker
from medewerkers.rechten import alleen_eigenaar

from . import export, kalender, periode, totalen
from .forms import UurblokForm
from .models import Uurblok


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

    context = {
        "weergave": weergave,
        "dag": dag,
        "dagen": dagen,
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
    weken = kalender.maandraster(eerste_van_maand.year, eerste_van_maand.month)
    eerste_dag, laatste_dag = weken[0][0], weken[-1][-1]

    blokken = Uurblok.objects.filter(
        medewerker=request.user, datum__range=(eerste_dag, laatste_dag)
    ).only("datum", "begintijd", "eindtijd")
    minuten_per_dag = {}
    for blok in blokken:
        minuten_per_dag[blok.datum] = minuten_per_dag.get(blok.datum, 0) + blok.duur_minuten

    def dagcel(datum):
        return {
            "datum": datum,
            "in_maand": datum.month == eerste_van_maand.month,
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
            "totaal_waarde": kalender.als_uren(sum(minuten_per_dag.values())),
            "vandaag": vandaag,
        },
    )


@login_required
def uurblok_nieuw(request):
    dag = periode.gekozen_dag(request)
    if request.method == "POST":
        formulier = UurblokForm(request.POST)
        if formulier.is_valid():
            blok = formulier.save(commit=False)
            blok.medewerker = request.user
            blok.save()
            return _terug_naar_dag(blok.datum)
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
    return render(
        request, "uren/uurblok_form.html", {"formulier": formulier, "dag": dag, "nieuw": True}
    )


@login_required
def uurblok_detail(request, pk):
    """Het blok bekijken, niet bewerken (SPEC §5: view-first).

    De eigenaar mag elk blok bekijken — anders klapt de doorklik vanuit het
    planbord stuk. Bewerken blijft van de medewerker zelf: een gecorrigeerd
    uurblok waar de mede­werker niets van weet levert discussie op die deze app
    juist moet voorkomen.
    """
    blok = get_object_or_404(Uurblok.objects.select_related("klus", "medewerker"), pk=pk)
    if blok.medewerker_id != request.user.pk and not request.user.is_eigenaar:
        raise Http404

    bijlagen = blok.bijlagen.select_related("toegevoegd_door").order_by("-toegevoegd_op")
    return render(
        request,
        "uren/uurblok_detail.html",
        {
            "blok": blok,
            "kleur": kalender.kleur_van(blok.klus),
            "duur": kalender.als_uren(blok.duur_minuten),
            "mag_bewerken": blok.medewerker_id == request.user.pk,
            "foto_bijlagen": [los for los in bijlagen if los.is_foto],
            "document_bijlagen": [los for los in bijlagen if not los.is_foto],
            "formulier": BijlageForm(),
            "upload_url": reverse("bijlage_toevoegen"),
            "terug": request.get_full_path(),
        },
    )


@login_required
def uurblok_bewerken(request, pk):
    # Een medewerker komt alleen bij zijn eigen blokken; die van een ander
    # bestaan voor hem niet.
    blok = get_object_or_404(Uurblok, pk=pk, medewerker=request.user)
    if request.method == "POST":
        formulier = UurblokForm(request.POST, instance=blok)
        if formulier.is_valid():
            formulier.save()
            return _terug_naar_dag(formulier.instance.datum)
    else:
        formulier = UurblokForm(instance=blok)
    return render(
        request,
        "uren/uurblok_form.html",
        {"formulier": formulier, "dag": blok.datum, "blok": blok, "nieuw": False},
    )


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

    # Eén query voor de hele week, daarna groeperen in Python. Zes mensen en
    # een paar honderd blokken — daar weegt een aggregatie per cel niet tegen
    # op, en de index op (datum, medewerker) dekt precies deze filter.
    blokken = (
        Uurblok.objects.filter(datum__range=(week["maandag"], week["zondag"]))
        .select_related("klus", "medewerker")
        .order_by("begintijd")
    )
    per_cel = {}
    klussen_in_beeld = {}
    for blok in blokken:
        per_cel.setdefault((blok.medewerker_id, blok.datum), []).append(blok)
        klussen_in_beeld[blok.klus_id] = blok.klus

    dagminuten = dict.fromkeys(week["dagen"], 0)
    rijen = []
    # Ook wie niets schreef krijgt een rij: "wie staat er níét ingepland" is
    # net zo goed de vraag waarvoor dit scherm bestaat.
    for medewerker in Medewerker.objects.filter(uit_dienst_sinds__isnull=True):
        dagen, weekminuten = [], 0
        for datum in week["dagen"]:
            cel = per_cel.get((medewerker.pk, datum), [])
            minuten = sum(blok.duur_minuten for blok in cel)
            weekminuten += minuten
            dagminuten[datum] += minuten
            dagen.append(
                {
                    "datum": datum,
                    "is_vandaag": datum == week["vandaag"],
                    "blokken": [
                        {
                            "blok": blok,
                            "kleur": kalender.kleur_van(blok.klus),
                            "duur": kalender.als_uren(blok.duur_minuten),
                        }
                        for blok in cel
                    ],
                    "totaal": kalender.als_uren(minuten) if minuten else "",
                }
            )
        rijen.append(
            {
                "medewerker": medewerker,
                "dagen": dagen,
                "weektotaal": kalender.als_uren(weekminuten) if weekminuten else "",
                "heeft_uren": weekminuten > 0,
            }
        )

    return render(
        request,
        "uren/planbord.html",
        {
            **week,
            "rijen": rijen,
            "kopdagen": [
                {
                    "datum": datum,
                    "is_vandaag": datum == week["vandaag"],
                    "totaal": kalender.als_uren(minuten) if minuten else "",
                }
                for datum, minuten in dagminuten.items()
            ],
            # De kleur draagt op deze breedte de klusidentiteit (SPEC §5), dus
            # hoort er een legenda onder die vertelt welke kleur wat is.
            "legenda": [
                {"klus": klus, "kleur": kalender.kleur_van(klus)}
                for klus in sorted(klussen_in_beeld.values(), key=lambda klus: klus.naam.lower())
            ],
            "weektotaal": kalender.als_uren(sum(dagminuten.values())),
        },
    )


def _gekozen_medewerker(request):
    """Van wie het overzicht gaat.

    Een medewerker die ?medewerker= van iemand anders meestuurt krijgt
    zwijgend zijn eigen cijfers, geen foutpagina. De eigenaar deelt links
    naar dit scherm, en een link die bij hem werkt en bij de rest een
    foutmelding geeft levert alleen telefoontjes op — terwijl niemand
    daarmee iets van een ander te zien krijgt.
    """
    gevraagd = request.GET.get("medewerker", "")
    if request.user.is_eigenaar and gevraagd.isdigit():
        return Medewerker.objects.filter(pk=gevraagd).first() or request.user
    return request.user


def _overzicht_periode(request, weergave, vandaag):
    """Begin en eind van de getoonde periode, en waar ‹ en › heen gaan."""
    if weergave == "maand":
        begin = periode.gekozen_dag(request).replace(day=1)
        eind = begin.replace(day=calendar.monthrange(begin.year, begin.month)[1])
        return {
            "begin": begin,
            "eind": eind,
            "dag": begin,
            "vorige": _maand_erbij(begin, -1),
            "volgende": _maand_erbij(begin, 1),
            "is_huidige_periode": (begin.year, begin.month) == (vandaag.year, vandaag.month),
        }
    week = periode.week_context(request)
    return {
        "begin": week["maandag"],
        "eind": week["zondag"],
        "dag": week["dag"],
        "vorige": week["vorige"],
        "volgende": week["volgende"],
        "is_huidige_periode": week["is_deze_week"],
    }


@login_required
def mijn_overzicht(request):
    """Contractpunt 3: gewerkte uren per medewerker, per week én per maand.

    Beide periodes staan in het contract, dus staan ze allebei achter dezelfde
    `?weergave=`-knoppen als de rest van de app al gebruikt. Het optellen komt
    uit totalen.py — hetzelfde rekenwerk als het klusdossier en de export, want
    drie schermen die los van elkaar uren optellen gaan uiteindelijk drie
    verschillende getallen tonen.
    """
    weergave = "maand" if request.GET.get("weergave") == "maand" else "week"
    vandaag = periode.vandaag()
    medewerker = _gekozen_medewerker(request)
    tijdvak = _overzicht_periode(request, weergave, vandaag)

    # Eén keer ophalen: per_klus en per_dag lopen allebei door dezelfde blokken.
    blokken = list(totalen.blokken_van(medewerker, tijdvak["begin"], tijdvak["eind"]))

    return render(
        request,
        "uren/mijn_overzicht.html",
        {
            **tijdvak,
            "weergave": weergave,
            "vandaag": vandaag,
            "medewerker": medewerker,
            # Alleen de eigenaar mag kiezen; bij de rest blijft de keuzelijst
            # weg én negeert _gekozen_medewerker de parameter.
            "mag_kiezen": request.user.is_eigenaar,
            "medewerker_pk": str(medewerker.pk) if request.user.is_eigenaar else "",
            "medewerkers": (
                Medewerker.objects.filter(uit_dienst_sinds__isnull=True)
                if request.user.is_eigenaar
                else []
            ),
            "klusrijen": [
                dict(rij, kleur=kalender.kleur_van(rij["klus"]))
                for rij in totalen.per_klus(blokken)
            ],
            "dagrijen": totalen.per_dag(blokken),
            "totaal_waarde": kalender.als_uren(sum(blok.duur_minuten for blok in blokken)),
        },
    )


def _maandopties(vandaag, aantal=14):
    """De laatste veertien kalendermaanden, nieuwste eerst — ruim genoeg om
    terug te kunnen tot de start van de app zonder een aparte jaarkeuze."""
    opties = []
    jaar, maand = vandaag.year, vandaag.month
    for _ in range(aantal):
        opties.append(date(jaar, maand, 1))
        maand -= 1
        if maand == 0:
            maand, jaar = 12, jaar - 1
    return opties


def _gekozen_maand(request, vandaag):
    gevraagd = request.GET.get("maand", "")
    try:
        jaar, maand = (int(deel) for deel in gevraagd.split("-", 1))
        return date(jaar, maand, 1)
    except (TypeError, ValueError):
        return vandaag.replace(day=1)


@login_required
def urenexport(request):
    """Exportscherm voor de boekhouder: uren van een kalendermaand als Excel.

    Periode is de kalendermaand-fallback uit docs/VRAGEN-MAARTEN.md; Maarten
    heeft op 15-09-2026 wel al bevestigd dat het bestand Excel moet zijn, geen
    CSV, zodat de boekhouding er verder in kan werken.

    Alleen de eigenaar mag dit openen: de boekhouder krijgt geen account in de
    app, hij krijgt het gedownloade bestand toegestuurd (SPEC §2, punt 6).
    """
    if not request.user.is_eigenaar:
        raise Http404

    vandaag = timezone.localdate()
    gekozen_maand = _gekozen_maand(request, vandaag)
    laatste_dag = calendar.monthrange(gekozen_maand.year, gekozen_maand.month)[1]
    eind_maand = gekozen_maand.replace(day=laatste_dag)

    medewerker_pk = request.GET.get("medewerker", "")
    blokken = (
        Uurblok.objects.filter(datum__range=(gekozen_maand, eind_maand))
        .select_related("medewerker", "klus")
        .order_by(
            "medewerker__first_name", "medewerker__last_name", "medewerker__username", "datum", "begintijd"
        )
    )
    if medewerker_pk:
        blokken = blokken.filter(medewerker__pk=medewerker_pk)
    blokken = list(blokken)

    if request.GET.get("download") == "1":
        boek = export.werkboek_bouwen(blokken, f"Uren {gekozen_maand:%m-%Y}")
        antwoord = HttpResponse(
            export.werkboek_als_bytes(boek),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        antwoord["Content-Disposition"] = f'attachment; filename="uren-{gekozen_maand:%Y-%m}.xlsx"'
        return antwoord

    totalen = []
    for blok in blokken:
        if not totalen or totalen[-1]["medewerker"] != blok.medewerker:
            totalen.append({"medewerker": blok.medewerker, "minuten": 0})
        totalen[-1]["minuten"] += blok.duur_minuten
    for regel in totalen:
        regel["totaal"] = kalender.als_uren(regel["minuten"])

    return render(
        request,
        "uren/export.html",
        {
            "gekozen_maand": gekozen_maand,
            "medewerker_pk": medewerker_pk,
            "maandopties": _maandopties(vandaag),
            "medewerkers": Medewerker.objects.filter(rol=Medewerker.Rol.MEDEWERKER),
            "totalen": totalen,
        },
    )
