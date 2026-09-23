import uuid
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.db.models import Prefetch, Q
from django.http import FileResponse, Http404, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify

from medewerkers.rechten import alleen_eigenaar
from uren import export as uren_export
from uren import totalen

from . import afbeeldingen, kleuren, opdrachtgevers, pdf_thumbnails, voorbeeld
from .forms import AlleenFotosForm, BijlageForm, KlusForm, KlusFotoForm, NieuweKlusBijlagenForm
from .fotoposts import groepeer_in_posts
from .models import Bijlage, Klus


def _terug_naar(request, standaard):
    """Na uploaden terug naar het scherm waar je vandaan kwam.

    Het adres komt uit een formulierveld, dus het moet gecontroleerd worden:
    zonder deze check kan een link van buitenaf iemand na het uploaden naar een
    andere site sturen.
    """
    gevraagd = request.POST.get("terug") or request.GET.get("terug")
    if gevraagd and url_has_allowed_host_and_scheme(
        gevraagd, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(gevraagd)
    return redirect(standaard)


def _doel_van(request):
    """Waar de bijlage aan hangt: een klus, een uurblok, of geen van beide.

    Dat laatste is de fotodropbox — losse foto's die (nog) bij geen klus horen.
    """
    from uren.models import Uurblok

    klus = uurblok = None
    if klus_pk := request.POST.get("klus") or request.GET.get("klus"):
        klus = get_object_or_404(Klus, pk=klus_pk)
    if blok_pk := request.POST.get("uurblok") or request.GET.get("uurblok"):
        uurblok = get_object_or_404(Uurblok, pk=blok_pk)
        # Hangt de bijlage aan een uurblok, dan hoort hij ook in het dossier
        # van de klus waarop dat blok geschreven is.
        klus = klus or uurblok.klus
    return klus, uurblok


def bewaar_bijlage(bestand, datum, toelichting, klus, uurblok, gebruiker, batch=None, forceer_document=False):
    """Eén geüpload bestand wegschrijven. Foto's verkleind, documenten zoals ze zijn.

    `batch` is het gedeelde kenmerk van een upload met meerdere bestanden
    tegelijk (zie batch_van_upload hieronder) — daarmee kan het fotoraster ze
    als één post tonen. Leeg bij een upload van één bestand.

    `forceer_document` slaat het bestand altijd op als document, ook als het
    er als foto uitziet — voor de documentenlijst van een klusdossier/uurblok,
    waar bijvoorbeeld een foto van een tekening thuishoort en niet tussen de
    werkfoto's in het fotoraster moet verschijnen (zie
    klussen.views.bijlage_toevoegen). Zo'n bestand blijft dan ook ongemoeid
    zoals elk ander document, in plaats van verkleind te worden.

    Publiek (geen underscore): ook het uren-toevoegformulier hangt hier een
    foto mee op (zie uren.views.uurblok_nieuw), niet alleen deze module.
    """
    naam = bestand.name
    hoofd, thumbnail = (None, None) if forceer_document else afbeeldingen.versies_van(bestand, naam)

    bijlage = Bijlage(
        soort=Bijlage.Soort.FOTO if hoofd else Bijlage.Soort.DOCUMENT,
        datum=datum,
        toelichting=toelichting,
        originele_naam=Path(naam).name[:255],
        klus=klus,
        uurblok=uurblok,
        toegevoegd_door=gebruiker,
        batch=batch,
    )
    if hoofd:
        basis = Path(naam).stem
        bijlage.bestand.save(f"{basis}.jpg", hoofd, save=False)
        bijlage.thumbnail.save(f"{basis}.jpg", thumbnail, save=False)
    else:
        document_thumbnail = pdf_thumbnails.thumbnail_van(bestand, naam) or afbeeldingen.thumbnail_van(bestand, naam)
        bestand.seek(0)
        bijlage.bestand.save(naam, ContentFile(bestand.read()), save=False)
        if document_thumbnail:
            bijlage.thumbnail.save(f"{Path(naam).stem}.jpg", document_thumbnail, save=False)
    bijlage.save()
    return bijlage


def batch_van_upload(bestanden):
    """Eén gedeeld kenmerk voor alle bestanden uit dezelfde upload, zodat het
    fotoraster ze als post bij elkaar kan tonen. Bij één bestand is er niets
    te groeperen, dus dan blijft het leeg."""
    return uuid.uuid4() if len(bestanden) > 1 else None


@login_required
def bijlage_toevoegen(request):
    klus, uurblok = _doel_van(request)
    standaard = klus.get_absolute_url() if klus else reverse("fotos")
    if request.method != "POST":
        return redirect(standaard)

    formulier = BijlageForm(request.POST, request.FILES)
    if not formulier.is_valid():
        if formulier.errors.get("datum"):
            messages.error(request, "Vul een geldige datum in.")
        else:
            messages.error(request, "Kies eerst een bestand.")
        return _terug_naar(request, standaard)

    datum = formulier.cleaned_data["datum"] or timezone.localdate()
    toelichting = formulier.cleaned_data["toelichting"]
    # Geen klus en geen uurblok: dit is de fotodropbox (de "+" op de foto tab).
    # Daar mag geen document meer bij, want die heeft sinds het verdwijnen van
    # de documentenlijst op dat scherm nergens een plek om terug te vinden.
    alleen_fotos = klus is None and uurblok is None
    # Gezet door _documentdialoog.html: die upload hoort in de documentenlijst,
    # ook als het bestand een foto is. Kan dus nooit samen met alleen_fotos
    # gelden — de fotodropbox toont die dialoog niet.
    forceer_document = not alleen_fotos and request.POST.get("forceer_document") == "1"
    batch = batch_van_upload(formulier.cleaned_data["bestanden"])
    gelukt = 0
    for bestand in formulier.cleaned_data["bestanden"]:
        if alleen_fotos and not afbeeldingen.lijkt_afbeelding(bestand.name):
            messages.error(request, f"{bestand.name}: hier kan alleen een foto bij, geen document.")
            continue
        try:
            bewaar_bijlage(bestand, datum, toelichting, klus, uurblok, request.user, batch, forceer_document)
        except afbeeldingen.BestandNietLeesbaar as probleem:
            # De rest van de selectie wel doorzetten: wie acht foto's uploadt
            # wil niet alles opnieuw doen omdat er één niet deugt.
            messages.error(request, f"{bestand.name}: {probleem}")
        else:
            gelukt += 1

    if gelukt:
        messages.success(request, f"{gelukt} bestand{'en' if gelukt > 1 else ''} toegevoegd.")
    return _terug_naar(request, standaard)


@login_required
def bijlage_verwijderen(request, pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    bijlage = get_object_or_404(Bijlage, pk=pk)
    if not bijlage.mag_verwijderen(request.user):
        raise Http404
    standaard = bijlage.klus.get_absolute_url() if bijlage.klus else reverse("fotos")
    bijlage.delete()
    messages.success(request, "Verwijderd.")
    return _terug_naar(request, standaard)


@login_required
def post_verwijderen(request, batch):
    """Het kruisje op een collagekaart in het fotoraster: verwijdert in één
    keer alle foto's van die post (zelfde batch). Ze komen uit dezelfde
    upload en hebben dus dezelfde toegevoegd_door, dus rechten checken op de
    eerste foto geldt voor de hele post."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    bijlagen = list(Bijlage.objects.filter(batch=batch))
    if not bijlagen or not bijlagen[0].mag_verwijderen(request.user):
        raise Http404
    standaard = bijlagen[0].klus.get_absolute_url() if bijlagen[0].klus else reverse("fotos")
    for bijlage in bijlagen:
        bijlage.delete()
    messages.success(request, "Verwijderd.")
    return _terug_naar(request, standaard)


@login_required
def media_bestand(request, pad):
    """Geüploade bestanden uitleveren, maar alleen aan wie is ingelogd.

    Klusdossiers en klantfoto's horen niet op een openbaar adres te staan, dus
    ze gaan niet als statisch bestand de deur uit maar hierlangs.
    """
    wortel = Path(settings.MEDIA_ROOT).resolve()
    # Zonder deze controle haalt ../../.env het hele bestand met de secret key op.
    volledig = (wortel / pad).resolve()
    if not volledig.is_relative_to(wortel) or not volledig.is_file():
        raise Http404

    hoofdbijlage = Bijlage.objects.filter(bestand=pad).first()
    # inline, niet attachment: een pdf moet in de browser te bekijken zijn
    # zonder eerst gedownload te worden. naam blijft gezet zodat "bewaren als"
    # in de browser een leesbare naam voorstelt in plaats van de opslag-uuid.
    #
    # Alleen voor het hoofdbestand, niet voor een thumbnail: een
    # documentthumbnail is altijd een jpg, ook van een pdf. Zonder deze knip
    # stuurt FileResponse voor zo'n thumbnail de originele .pdf-naam mee,
    # leidt daar Content-Type: application/pdf uit af terwijl de bytes een
    # jpeg zijn, en laten sommige mobiele browsers het plaatje dan leeg.
    naam = hoofdbijlage.originele_naam if hoofdbijlage and not hoofdbijlage.is_foto else None

    if settings.GEBRUIK_X_ACCEL:
        # nginx levert het bestand uit; Django doet alleen de rechtencontrole.
        antwoord = HttpResponse()
        antwoord["X-Accel-Redirect"] = f"{settings.MEDIA_INTERN_PAD}{pad}"
        del antwoord["Content-Type"]
        if naam:
            antwoord["Content-Disposition"] = f'inline; filename="{naam}"'
        return antwoord

    return FileResponse(volledig.open("rb"), as_attachment=False, filename=naam)


@login_required
def fotos(request):
    """Foto's: alle foto's op één hoop, met een dropdown om op klus te filteren.

    Documenten staan hier niet meer bij — die zie je op het klusdossier zelf
    (klussen/klus_detail.html) of bij het uurblok waar ze aan hangen."""
    zoek = request.GET.get("q", "").strip()
    klus_pk = request.GET.get("klus", "").strip()
    # "algemeen" is geen klus-pk maar het aparte filter voor foto's zonder klus
    # (de fotodropbox) — elke andere onbekende waarde valt terug op "alle klussen".
    if klus_pk not in ("", "algemeen") and not klus_pk.isdigit():
        klus_pk = ""
    scope = request.GET.get("scope", "altijd")
    if scope not in ("actief", "inactief", "altijd"):
        scope = "altijd"

    context = {
        "zoek": zoek,
        "klus_pk": klus_pk,
        "scope": scope,
        "klussen": Klus.objects.all(),  # Meta.ordering = ["-actief", "naam"]
        "alleen_fotos": True,
        # Sta je al op een klus gefilterd, dan staat de uploaddialoog daar vast
        # op — anders is "Algemeen" (leeg) de standaard.
        "formulier": AlleenFotosForm(initial={"klus": klus_pk} if klus_pk.isdigit() else None),
        "upload_url": reverse("bijlage_toevoegen"),
        "terug": request.get_full_path(),
    }

    bijlagen = Bijlage.objects.select_related("toegevoegd_door", "klus").order_by("-datum", "-toegevoegd_op")
    if zoek:
        # Zelfde belofte als de placeholder in de zoekbalk: "omschrijving, klus
        # of adres" — dus ook de klus waar de foto aan hangt doorzoeken, niet
        # alleen de foto's eigen toelichting/bestandsnaam.
        bijlagen = bijlagen.filter(
            Q(toelichting__icontains=zoek)
            | Q(originele_naam__icontains=zoek)
            | Q(klus__naam__icontains=zoek)
            | Q(klus__adres__icontains=zoek)
            | Q(klus__plaats__icontains=zoek)
        )
    # Een specifieke klus (of "algemeen") kiezen wint van de scope-pil: je
    # vroeg expliciet om die foto's, ook als de klus niet in die scope valt.
    if klus_pk == "algemeen":
        bijlagen = bijlagen.filter(klus__isnull=True)
    elif klus_pk:
        bijlagen = bijlagen.filter(klus_id=klus_pk)
    elif scope == "actief":
        bijlagen = bijlagen.filter(klus__actief=True)
    elif scope == "inactief":
        bijlagen = bijlagen.filter(klus__actief=False)
    context["foto_posts"] = groepeer_in_posts(b for b in bijlagen if b.is_foto)
    return render(request, "klussen/fotos.html", context)


def _lege_melding(soort, scope):
    """Wat er staat als het filter niets oplevert.

    Niet "Nog geen klussen": dat is onwaar zodra er wel klussen zijn maar niet
    in dit filter, en dan lijkt het alsof er niets bestaat in plaats van dat je
    te ver hebt gefilterd.
    """
    staat = {"actief": "lopende", "afgerond": "afgeronde"}.get(scope, "")
    if soort:
        soortnaam = Klus.Soort(soort).label.lower()
        return f"Geen {staat} klussen van de soort {soortnaam}.".replace("  ", " ")
    if staat:
        return f"Geen {staat} klussen."
    return "Nog geen klussen."


@login_required
def klus_lijst(request):
    """Overzicht van klussen, met één filterrij van twee gelijkwaardige groepen:

        [ Alles | Eenmalig | Onderhoud ]   [ Alles | Actief | Afgerond ]
                  soort = ritme                   scope = staat

    Twee assen, dus twee groepen met dezelfde vorm naast elkaar — niet het ene
    filter onder het andere. Hier stond eerst een klus-kiezer met daarin
    verstopt nog een pillenrij Alle/Actief/Niet actief. Dat waren twee filters
    onder elkaar zonder dat het ene onder het andere hing, en erger nog: de
    stand van dat tweede filter was niet te zien. De lijst toonde standaard
    alleen actieve klussen terwijl niets op het scherm dat vertelde.

    De kiezer zelf is hier weg. Op de Galerij doet hij echt iets — foto's
    filteren op klus — maar op een lijst van klussen levert "kies één klus" een
    lijst van één klus op, terwijl je die klus in de lijst eronder gewoon kunt
    aantikken en de zoekbalk hem al op naam vindt. Wat er wél in zat, de staat
    van een klus, staat nu als eigen groep in beeld.

    De soort is de primaire as: SPEC §1 zegt dat aanleg versus onderhoud bijna
    elke ontwerpkeuze bepaalt, en zodra er naast een handvol eenmalige klussen
    tientallen onderhoudsadressen staan, verzuipen die eerste in een lijst die
    alleen op naam sorteert (Meta.ordering = ["-actief", "naam"]).

    Iedereen die inlogt ziet alle klussen: er is geen "toegewezen aan"-veld op
    Klus (dat loopt via Uurblok, per werkdag), dus een medewerker moet elke
    klus kunnen openen om er een foto aan te hangen, ook eentje waar hij
    vandaag niet op staat.
    """
    zoek = request.GET.get("q", "").strip()
    # Leeg is "alles"; een onbekende waarde valt daar ook op terug.
    soort = request.GET.get("soort", "").strip()
    if soort not in Klus.Soort.values:
        soort = ""
    # "actief" is de standaard, niet "alles": je kijkt bijna altijd naar wat er
    # loopt. Anders dan vroeger staat dat nu wél in beeld, als aangezette pil.
    scope = request.GET.get("scope", "actief")
    if scope not in ("alles", "actief", "afgerond"):
        scope = "actief"

    klussen = Klus.objects.all()
    if scope == "actief":
        klussen = klussen.filter(actief=True)
    elif scope == "afgerond":
        klussen = klussen.filter(actief=False)
    if soort:
        klussen = klussen.filter(soort=soort)
    if zoek:
        klussen = klussen.filter(
            Q(naam__icontains=zoek) | Q(adres__icontains=zoek) | Q(plaats__icontains=zoek)
        )
    # Zelfde gewaaierde voorproefje als op het startscherm en het foto's-scherm.
    # De prefetch hoort erbij: zonder to_attr haalt items_voor_stapel() de
    # bijlagen per klus apart op en wordt een lijst van tien klussen elf queries.
    klussen = list(
        klussen.prefetch_related(
            Prefetch(
                "bijlagen",
                queryset=Bijlage.objects.order_by("-datum", "-toegevoegd_op"),
                to_attr="voorbeeld_bijlagen",
            )
        )
    )
    for klus in klussen:
        klus.voorbeeld_items, klus.voorbeeld_meer = voorbeeld.items_voor_stapel(klus)
    return render(
        request,
        "klussen/klussen.html",
        {
            "klussen": klussen,
            "zoek": zoek,
            "scope": scope,
            "soort": soort,
            # Uit Klus.Soort, zodat de pillen meebewegen als die labels ooit
            # veranderen (zoals "Aanleg" → "Eenmalig" al gebeurd is).
            "soort_keuzes": [("", "Alles"), *Klus.Soort.choices],
            # Twee groepen met dezelfde vorm, zodat ze naast elkaar als twee
            # assen lezen en niet als één lijst keuzes.
            "scope_keuzes": [("alles", "Alles"), ("actief", "Actief"), ("afgerond", "Afgerond")],
            # Voor de lege staat. "Nog geen klussen" is onwaar zodra er wel
            # klussen zijn maar niet in dit filter; dan lijkt het alsof er niets
            # bestaat. Hier staat dus welke twee knoppen niets opleverden.
            "lege_melding": _lege_melding(soort, scope),
        },
    )


@login_required
def klus_detail(request, pk):
    """Klusdossier: kerngegevens, wie eraan gewerkt heeft, foto's en documenten.

    Een medewerker ziet het volledige dossier (SPEC §2) — ook de uren van
    collega's, want "wie op welke klus heeft gewerkt" is precies wat dit
    scherm moet laten zien. Zijn eigen urenoverzicht blijft een ander scherm.
    """
    klus = get_object_or_404(
        Klus.objects.prefetch_related(
            Prefetch(
                "bijlagen",
                queryset=Bijlage.objects.order_by("-datum", "-toegevoegd_op"),
                to_attr="voorbeeld_bijlagen",
            )
        ),
        pk=pk,
    )
    # Zelfde gewaaierde voorproefje als op de klussenlijst, nu als hero
    # bovenaan het dossier. Daar moet de vorm altijd kloppen — dus opgevuld
    # tot precies 3 lagen met lege plekken vooraan (achter de echte inhoud),
    # in plaats van het aantal lagen te laten meebewegen met wat er in de
    # klus zit. Zie klussen/_klushero.html.
    klus.voorbeeld_items, klus.voorbeeld_meer = voorbeeld.items_voor_stapel(klus)
    klus.hero_items = [None] * (3 - len(klus.voorbeeld_items)) + klus.voorbeeld_items
    bijlagen = klus.bijlagen.select_related("toegevoegd_door").order_by("-toegevoegd_op")
    gewerkt = totalen.per_medewerker_op_klus(klus)
    return render(
        request,
        "klussen/klus_detail.html",
        {
            "klus": klus,
            "gewerkt": gewerkt,
            "totaal": totalen.totaal_van(gewerkt),
            "foto_posts": groepeer_in_posts(los for los in bijlagen if los.is_foto),
            "document_bijlagen": [los for los in bijlagen if not los.is_foto],
            "formulier": BijlageForm(),
            "foto_formulier": KlusFotoForm(),
            "upload_url": reverse("bijlage_toevoegen"),
            "terug": request.get_full_path(),
        },
    )


@login_required
def klus_uren_export(request, pk):
    """De uren van dit klusdossier als Excel-bestand, per medewerker.

    Zelfde bestandsvorm als de maandelijkse boekhoud-export
    (uren.views.urenexport), nu gefilterd op één klus in plaats van een
    periode. Iedereen die het dossier mag zien mag ook dit downloaden — de
    lijst "Gewerkte uren" op dat dossier toont dezelfde uren al op het scherm.
    """
    from uren.models import Uurblok

    klus = get_object_or_404(Klus, pk=pk)
    blokken = list(
        Uurblok.objects.filter(klus=klus)
        .select_related("medewerker")
        .order_by(
            "medewerker__first_name", "medewerker__last_name", "medewerker__username", "datum", "begintijd"
        )
    )
    boek = uren_export.werkboek_bouwen(blokken, f"Uren {klus.naam}")
    antwoord = HttpResponse(
        uren_export.werkboek_als_bytes(boek),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    antwoord["Content-Disposition"] = f'attachment; filename="uren-{slugify(klus.naam)}.xlsx"'
    return antwoord


@alleen_eigenaar
def klus_nieuw(request):
    formulier = KlusForm(request.POST or None)
    # Eén formulier op de pagina, twee Django-formulieren erachter: bestanden
    # kiezen is optioneel (zie NieuweKlusBijlagenForm), dus die mogen de klus
    # zelf nooit blokkeren.
    bijlagenformulier = NieuweKlusBijlagenForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and formulier.is_valid() and bijlagenformulier.is_valid():
        klus = formulier.save(commit=False)
        # Niet via het formulier: de kleur wordt hier bepaald, niet met de
        # hand gekozen (klussen.kleuren.volgende_kleur), en dat moet ook
        # gelden als iemand het verborgen veld zelf zou aanpassen.
        klus.kleur = kleuren.volgende_kleur()
        klus.save()

        datum = bijlagenformulier.cleaned_data["datum"] or timezone.localdate()
        toelichting = bijlagenformulier.cleaned_data["toelichting"]

        # Twee velden, twee bestemmingen (zie NieuweKlusBijlagenForm): het ene
        # wordt een foto in het raster, het andere een document in de
        # documentenlijst — ook als dat document een gefotografeerde tekening
        # is. Wat in het fotoveld zit maar geen foto is (een offerte in het
        # verkeerde vakje) schuift mee naar de documenten in plaats van
        # geweigerd te worden: de klus staat op dit punt al, dus weigeren
        # betekent dat de offerte weg is en Maarten 'm opnieuw moet zoeken.
        fotos, documenten = [], list(bijlagenformulier.cleaned_data["documenten"])
        for bestand in bijlagenformulier.cleaned_data["bestanden"]:
            if afbeeldingen.lijkt_afbeelding(bestand.name):
                fotos.append(bestand)
            else:
                documenten.append(bestand)
                messages.info(request, f"{bestand.name} staat bij de documenten.")

        for stapel, als_document in ((fotos, False), (documenten, True)):
            # Eigen batch per stapel: het fotoraster groepeert een upload van
            # meerdere bestanden als één post, en de documenten horen daar niet
            # bij te zitten.
            batch = batch_van_upload(stapel)
            for bestand in stapel:
                try:
                    bewaar_bijlage(
                        bestand, datum, toelichting, klus, None, request.user, batch, als_document
                    )
                except afbeeldingen.BestandNietLeesbaar as probleem:
                    # De klus staat er al; alleen het ene bestand mislukt, niet de rest.
                    messages.error(request, f"{bestand.name}: {probleem}")

        messages.success(request, f"Klus '{klus.naam}' aangemaakt.")
        return redirect(klus)
    return render(
        request,
        "klussen/klus_form.html",
        {
            "formulier": formulier,
            "bijlagenformulier": bijlagenformulier,
            "nieuw": True,
            "opdrachtgevers": opdrachtgevers.bekende_opdrachtgevers(),
        },
    )


@alleen_eigenaar
def klus_bewerken(request, pk):
    klus = get_object_or_404(Klus, pk=pk)
    formulier = KlusForm(request.POST or None, instance=klus)
    if request.method == "POST" and formulier.is_valid():
        formulier.save()
        messages.success(request, "Opgeslagen.")
        return redirect(klus)
    return render(
        request,
        "klussen/klus_form.html",
        {
            "formulier": formulier,
            "klus": klus,
            "nieuw": False,
            # Zonder deze klus zelf: anders waarschuwt het formulier bij het
            # bewerken dat er op dit adres al een klus staat — namelijk deze.
            "opdrachtgevers": opdrachtgevers.bekende_opdrachtgevers(uitgezonderd=klus),
        },
    )
