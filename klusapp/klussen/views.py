from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.http import FileResponse, Http404, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from . import afbeeldingen
from .forms import BijlageForm
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


def _bewaar(bestand, datum, toelichting, klus, uurblok, gebruiker):
    """Eén geüpload bestand wegschrijven. Foto's verkleind, documenten zoals ze zijn."""
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
        bestand.seek(0)
        bijlage.bestand.save(naam, ContentFile(bestand.read()), save=False)
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
    gelukt = 0
    for bestand in formulier.cleaned_data["bestanden"]:
        try:
            _bewaar(bestand, datum, toelichting, klus, uurblok, request.user)
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

    bijlage = Bijlage.objects.filter(bestand=pad).first() or Bijlage.objects.filter(thumbnail=pad).first()
    naam = bijlage.originele_naam if bijlage and not bijlage.is_foto else None

    if settings.GEBRUIK_X_ACCEL:
        # nginx levert het bestand uit; Django doet alleen de rechtencontrole.
        antwoord = HttpResponse()
        antwoord["X-Accel-Redirect"] = f"{settings.MEDIA_INTERN_PAD}{pad}"
        del antwoord["Content-Type"]
        if naam:
            antwoord["Content-Disposition"] = f'attachment; filename="{naam}"'
        return antwoord

    return FileResponse(volledig.open("rb"), as_attachment=bool(naam), filename=naam)


@login_required
def fotos(request):
    """De fotodropbox: losse foto's die niet aan een klus hangen.

    Bewust kaal. Filters, de maandindeling en "koppel alsnog aan een klus"
    horen bij taak T1, niet bij het fundament.
    """
    bijlagen = (
        Bijlage.objects.filter(klus__isnull=True)
        .select_related("toegevoegd_door")
        .order_by("-toegevoegd_op")
    )
    return render(
        request,
        "klussen/fotos.html",
        {
            "foto_bijlagen": [los for los in bijlagen if los.is_foto],
            "document_bijlagen": [los for los in bijlagen if not los.is_foto],
            "formulier": BijlageForm(),
            "upload_url": reverse("bijlage_toevoegen"),
            "terug": request.get_full_path(),
        },
    )


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
    return render(request, "klussen/klussen.html", {"klussen": klussen, "toon_alles": toon_alles})


@login_required
def klus_detail(request, pk):
    """Klusdossier: kerngegevens plus de foto's en documenten die eraan hangen."""
    klus = get_object_or_404(Klus, pk=pk)
    bijlagen = klus.bijlagen.select_related("toegevoegd_door").order_by("-toegevoegd_op")
    return render(
        request,
        "klussen/klus_detail.html",
        {
            "klus": klus,
            "foto_bijlagen": [los for los in bijlagen if los.is_foto],
            "document_bijlagen": [los for los in bijlagen if not los.is_foto],
            "formulier": BijlageForm(),
            "upload_url": reverse("bijlage_toevoegen"),
            "terug": request.get_full_path(),
        },
    )
