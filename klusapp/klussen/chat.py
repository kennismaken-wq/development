"""De chat per klus (fase 2): het gesprek dat per 1 januari de WhatsApp-groepen
vervangt. Onder water zijn het de notities van de klus (Notitie); dit is het
scherm eromheen, zoals WhatsApp: ballonnetjes, het nieuwste onderaan, de
typbalk vast onderin, versturen zonder herladen en nieuwe berichten die
vanzelf verschijnen (static/js/chat.js).

Zonder javascript werkt het ook: dan is het een gewoon formulier dat de
pagina opnieuw laadt.

Wie wat mag: iedereen die de klus mag zien, mag meelezen en meeschrijven,
net als bij de notities. Weghalen mag alleen je eigen bericht, ook voor de
eigenaar (Notitie.mag_verwijderen).
Wie een melding en een groen rondje krijgt, staat in klussen/gesprek.py.
"""

import re
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Max, Prefetch
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from . import afbeeldingen, gesprek
from .models import Bijlage, Klus, Notitie
from .views import DUBBEL_BINNEN, batch_van_upload, bewaar_bijlage

MAX_FOTOS = 10
# Zoveel berichten bij het openen; de rest met "Eerdere berichten".
OP_HET_SCHERM = 150
SLEUTEL_VORM = re.compile(r"^[A-Za-z0-9-]{8,40}$")


def _is_chat(request):
    """Verstuurd door chat.js (fetch) in plaats van een gewoon formulier."""
    return request.headers.get("X-Chat") == "1"


def _berichten(klus, gebruiker):
    return (
        klus.notities.select_related("geschreven_door")
        .prefetch_related(
            # Foto's in de chat zijn voor iedereen, maar de regel blijft
            # dezelfde als overal: zichtbaar_voor (stresstest 17-11-2026).
            Prefetch("fotos", queryset=Bijlage.objects.zichtbaar_voor(gebruiker).order_by("pk"))
        )
        .order_by("geschreven_op", "pk")
    )


def _html(request, berichten):
    return render_to_string("klussen/_chatberichten.html", {"berichten": berichten}, request=request)


@login_required
@require_GET
def chat(request, pk):
    klus = get_object_or_404(Klus, pk=pk)
    alles = _berichten(klus, request.user)
    totaal = alles.count()
    # "Eerdere berichten" laadt er telkens OP_HET_SCHERM bij, niet alles in
    # één keer: 2000 berichten met foto's was een pagina van een megabyte
    # (stresstest 17-11-2026).
    aantal = request.GET.get("aantal", "")
    aantal = min(int(aantal), 5000) if aantal.isdigit() and len(aantal) < 6 else OP_HET_SCHERM
    getoond = list(alles[max(0, totaal - aantal):])
    berichten = gesprek.voorbereid(getoond, request.user)
    if berichten:
        gesprek.markeer_gelezen(request, klus, tot=berichten[-1].geschreven_op)
    return render(
        request,
        "klussen/chat.html",
        {
            "klus": klus,
            "berichten": berichten,
            "eerdere": totaal - len(berichten),
            "meer": len(berichten) + OP_HET_SCHERM,
            "betrokkenen": gesprek.zichtbare_betrokkenen(klus),
            "laatste": max((b.pk for b in berichten), default=0),
            "sleutel": _nieuwe_sleutel(),
            "max_fotos": MAX_FOTOS,
        },
    )


def _nieuwe_sleutel():
    """Voor het formulier zonder javascript; chat.js maakt er zelf per
    bericht een."""
    return uuid.uuid4().hex


@login_required
@require_GET
def chat_nieuw(request, pk):
    """Voor chat.js, elke paar seconden: de berichten na ?na=<pk>, en welke
    berichten vanaf ?van=<pk> er nog zijn (zodat een weggehaald bericht ook
    bij de anderen verdwijnt)."""
    klus = get_object_or_404(Klus, pk=pk)
    na = request.GET.get("na", "0")
    van = request.GET.get("van", "0")
    na = int(na) if na.isdigit() and len(na) < 12 else 0
    van = int(van) if van.isdigit() and len(van) < 12 else 0
    berichten = _berichten(klus, request.user)
    nieuw = list(berichten.filter(pk__gt=na))
    vorige = (
        klus.notities.select_related("geschreven_door").filter(pk__lte=na).order_by("geschreven_op", "pk").last()
        if na else None
    )
    nieuw = gesprek.voorbereid(nieuw, request.user, vorige=vorige)
    laatste = max([na] + [b.pk for b in nieuw])
    if request.GET.get("zichtbaar") == "1" and laatste:
        # Gelezen tot het laatste bericht dat nu op het scherm staat, niet tot
        # "nu": een bericht dat net wordt opgeslagen (foto's!) maar nog niet
        # zichtbaar is, telt anders nooit als ongelezen (stresstest 17-11-2026).
        tot = klus.notities.filter(pk__lte=laatste).aggregate(m=Max("geschreven_op"))["m"]
        if tot:
            gesprek.markeer_gelezen(request, klus, tot=tot)
    return JsonResponse(
        {
            "html": _html(request, nieuw) if nieuw else "",
            "laatste": laatste,
            # Welke berichten er vanaf ?van nog zijn. chat.js haalt alleen
            # weg wat hier ontbreekt en niet hoger is dan het hoogste nummer
            # in deze lijst: een bericht dat net na deze momentopname is
            # verstuurd, blijft staan.
            "nog_er": list(klus.notities.filter(pk__gte=van).order_by("pk").values_list("pk", flat=True)) if van else [],
        }
    )


def _fout(request, klus, tekst, status=400):
    if _is_chat(request):
        return JsonResponse({"fout": tekst}, status=status)
    messages.error(request, tekst)
    return redirect(reverse("klus_chat", args=[klus.pk]))


@login_required
@require_POST
def notitie_toevoegen(request, pk):
    """Een bericht in de chat: tekst, foto's, of allebei. De foto's hangen
    aan het bericht én aan de klus, dus ze staan ook in Media. Na het opslaan
    krijgt wie bij de klus hoort een melding (klussen/gesprek.py)."""
    klus = get_object_or_404(Klus, pk=pk)
    tekst = request.POST.get("tekst", "").strip()
    sleutel = request.POST.get("sleutel", "")
    if sleutel and not SLEUTEL_VORM.match(sleutel):
        return _fout(request, klus, "Dit bericht kon niet worden verstuurd. Laad de chat opnieuw.")
    # Lege bestanden (0 bytes) zelf eruit, met de uitleg in het antwoord van
    # de chat; zonder_lege_bestanden zet die in messages, en die verscheen
    # dan pas op het volgende scherm (stresstest 17-11-2026).
    gekozen = request.FILES.getlist("fotos")
    fotos = [foto for foto in gekozen if foto.size]
    leeg = [f"{foto.name} is leeg (0 bytes) en is niet meegestuurd." for foto in gekozen if not foto.size]
    max_lengte = Notitie._meta.get_field("tekst").max_length

    # Zelfde sleutel: dit bericht staat er al (opnieuw verstuurd bij slecht
    # bereik). Geef het bestaande terug in plaats van een tweede.
    if sleutel:
        bestaand = Notitie.objects.filter(geschreven_door=request.user, sleutel=sleutel).first()
        if bestaand and bestaand.klus_id == klus.pk and bestaand.tekst == tekst:
            return _gelukt(request, klus, bestaand)
        if bestaand:
            # Deze sleutel hoort bij een ander bericht (ander gesprek, of
            # zonder javascript terug in de browser en iets anders getypt):
            # niet hergebruiken, anders verdween dit bericht (stresstest
            # 17-11-2026).
            sleutel = ""

    if not tekst and not fotos:
        return _fout(request, klus, " ".join(leeg) or "Er staat nog niets in het bericht.")
    if len(tekst) > max_lengte:
        return _fout(request, klus, f"Een bericht mag hooguit {max_lengte} tekens zijn.")
    for foto in fotos:
        if afbeeldingen.is_niet_ondersteund(foto.name):
            return _fout(
                request, klus,
                f"{foto.name}: HEIC-foto's kunnen we nog niet verwerken. Stel je telefoon in op "
                "'Meest compatibel' (Instellingen › Camera › Formaten), of kies de foto opnieuw uit de galerij.",
            )
        if not afbeeldingen.lijkt_afbeelding(foto.name):
            return _fout(request, klus, f"{foto.name}: hier kan alleen een foto bij. Een document zet je bij Bestanden.")
    te_veel = len(fotos) > MAX_FOTOS
    fotos = fotos[:MAX_FOTOS]

    problemen = list(leeg)
    with transaction.atomic():
        request.user.vergrendel()
        if sleutel:
            # Nog een keer kijken, nu met het slot: twee verzoeken tegelijk.
            bestaand = Notitie.objects.filter(geschreven_door=request.user, sleutel=sleutel).first()
            if bestaand and bestaand.klus_id == klus.pk and bestaand.tekst == tekst:
                return _gelukt(request, klus, bestaand)
            if bestaand:
                sleutel = ""
        elif tekst and not fotos and Notitie.objects.filter(
            klus=klus, tekst=tekst, geschreven_door=request.user,
            geschreven_op__gte=timezone.now() - DUBBEL_BINNEN,
        ).exists():
            # Zonder sleutel (oud formulier): dezelfde tekst binnen een paar
            # seconden is een dubbele tik (stresstest 03-10-2026, B16).
            return redirect(reverse("klus_chat", args=[klus.pk]))
        notitie = Notitie.objects.create(klus=klus, tekst=tekst, geschreven_door=request.user, sleutel=sleutel)
        batch = batch_van_upload(fotos)
        opgeslagen = []
        try:
            for foto in fotos:
                try:
                    bijlage = bewaar_bijlage(foto, timezone.localdate(), "", klus, None, request.user, batch)
                except afbeeldingen.BestandNietLeesbaar as probleem:
                    problemen.append(f"{foto.name}: {probleem}")
                    continue
                opgeslagen.append(bijlage)
                bijlage.notitie = notitie
                bijlage.save(update_fields=["notitie"])
        except Exception:
            # Schijf vol, een onverwachte fout in een foto: de transactie gaat
            # terug, maar de bestanden staan al op schijf. Die ruimen we op
            # (stresstest 17-11-2026).
            for bijlage in opgeslagen:
                bijlage.bestand.delete(save=False)
                if bijlage.thumbnail:
                    bijlage.thumbnail.delete(save=False)
            raise
        if not tekst and not opgeslagen:
            notitie.delete()
            return _fout(request, klus, " ".join(problemen) or "Geen van de foto's was te lezen.")
        gesprek.plan_melding(notitie)
    # Buiten de transactie: een botsing daarin mag het bericht niet kosten.
    gesprek.markeer_gelezen(request, klus, tot=notitie.geschreven_op)
    if te_veel:
        problemen.append(f"Er kunnen hooguit {MAX_FOTOS} foto's in één bericht; de eerste {MAX_FOTOS} zijn meegegaan.")
    return _gelukt(request, klus, notitie, problemen)


def _gelukt(request, klus, notitie, problemen=()):
    if _is_chat(request):
        berichten = _berichten(klus, request.user)
        vorige = berichten.filter(pk__lt=notitie.pk).last()
        bericht = gesprek.voorbereid([berichten.get(pk=notitie.pk)], request.user, vorige=vorige)
        return JsonResponse({"pk": notitie.pk, "html": _html(request, bericht), "meldingen": list(problemen)})
    for probleem in problemen:
        messages.error(request, probleem)
    return redirect(reverse("klus_chat", args=[klus.pk]) + "#onder")


@login_required
@require_POST
def notitie_verwijderen(request, pk):
    notitie = get_object_or_404(Notitie, pk=pk)
    if not notitie.mag_verwijderen(request.user):
        raise Http404
    klus_pk = notitie.klus_id
    notitie.delete()
    if _is_chat(request):
        return JsonResponse({"weg": pk})
    return redirect(reverse("klus_chat", args=[klus_pk]))
