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

from . import afbeeldingen, kleuren, pdf_thumbnails, voorbeeld
from .forms import AlleenFotosForm, BijlageForm, KlusForm, NieuweKlusBijlagenForm
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


def bewaar_bijlage(bestand, datum, toelichting, klus, uurblok, gebruiker):
    """Eén geüpload bestand wegschrijven. Foto's verkleind, documenten zoals ze zijn.

    Publiek (geen underscore): ook het uren-toevoegformulier hangt hier een
    foto mee op (zie uren.views.uurblok_nieuw), niet alleen deze module.
    """
    naam = bestand.name
    hoofd, thumbnail = afbeeldingen.versies_van(bestand, naam)

    bijlage = Bijlage(
        soort=Bijlage.Soort.FOTO if hoofd else Bijlage.Soort.DOCUMENT,
        datum=datum,
        toelichting=toelichting,
        originele_naam=Path(naam).name[:255],
        klus=klus,
        uurblok=uurblok,
        toegevoegd_door=gebruiker,
    )
    if hoofd:
        basis = Path(naam).stem
        bijlage.bestand.save(f"{basis}.jpg", hoofd, save=False)
        bijlage.thumbnail.save(f"{basis}.jpg", thumbnail, save=False)
    else:
        document_thumbnail = pdf_thumbnails.thumbnail_van(bestand, naam)
        bestand.seek(0)
        bijlage.bestand.save(naam, ContentFile(bestand.read()), save=False)
        if document_thumbnail:
            bijlage.thumbnail.save(f"{Path(naam).stem}.jpg", document_thumbnail, save=False)
    bijlage.save()
    return bijlage


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
    gelukt = 0
    for bestand in formulier.cleaned_data["bestanden"]:
        if alleen_fotos and not afbeeldingen.lijkt_afbeelding(bestand.name):
            messages.error(request, f"{bestand.name}: hier kan alleen een foto bij, geen document.")
            continue
        try:
            bewaar_bijlage(bestand, datum, toelichting, klus, uurblok, request.user)
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

    context = {
        "zoek": zoek,
        "klus_pk": klus_pk,
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
    if klus_pk == "algemeen":
        bijlagen = bijlagen.filter(klus__isnull=True)
    elif klus_pk:
        bijlagen = bijlagen.filter(klus_id=klus_pk)
    context["foto_bijlagen"] = [b for b in bijlagen if b.is_foto]
    return render(request, "klussen/fotos.html", context)


@login_required
def klus_lijst(request):
    """Overzicht van klussen. Standaard alleen actief, ?alles=1 toont ook afgeronde.

    Iedereen die inlogt ziet alle klussen: er is geen "toegewezen aan"-veld op
    Klus (dat loopt via Uurblok, per werkdag), dus een medewerker moet elke
    klus kunnen openen om er een foto aan te hangen, ook eentje waar hij
    vandaag niet op staat.
    """
    toon_alles = request.GET.get("alles") == "1"
    klussen = Klus.objects.all() if toon_alles else Klus.objects.filter(actief=True)
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
    return render(request, "klussen/klussen.html", {"klussen": klussen, "toon_alles": toon_alles})


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
            "foto_bijlagen": [los for los in bijlagen if los.is_foto],
            "document_bijlagen": [los for los in bijlagen if not los.is_foto],
            "formulier": BijlageForm(),
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
        for bestand in bijlagenformulier.cleaned_data["bestanden"]:
            try:
                bewaar_bijlage(bestand, datum, toelichting, klus, None, request.user)
            except afbeeldingen.BestandNietLeesbaar as probleem:
                # De klus staat er al; alleen het ene bestand mislukt, niet de rest.
                messages.error(request, f"{bestand.name}: {probleem}")

        messages.success(request, f"Klus '{klus.naam}' aangemaakt.")
        return redirect(klus)
    return render(
        request,
        "klussen/klus_form.html",
        {"formulier": formulier, "bijlagenformulier": bijlagenformulier, "nieuw": True},
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
        request, "klussen/klus_form.html", {"formulier": formulier, "klus": klus, "nieuw": False}
    )
