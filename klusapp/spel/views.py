"""Springspel met scorebord (offerte 2026-O01, onderdeel 3)."""

import json
import time

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from uren.kalender import medewerker_kleur_van

from .models import BesteScore
from .scorebord import ranglijst, vlaggen

# De score ontstaat op de telefoon, dus dit is een grens en geen bewijs: wat
# in de verstreken tijd niet te halen is, telt niet. Sneller dan de boost uit
# static/js/springspel.js (1122 eenheden per seconde, 4 eenheden per punt, dus
# 281 punten per seconde) kan niemand stijgen.
MAX_PUNTEN_PER_SECONDE = 500
SPEELRUIMTE_SECONDEN = 2
MAX_PUNTEN = 1_000_000


@login_required
@require_GET
def spel(request):
    beste = BesteScore.objects.filter(medewerker=request.user).first()
    return render(
        request,
        "spel/spel.html",
        {
            "rijen": ranglijst(),
            "beste": beste.punten if beste else 0,
            "kleur": medewerker_kleur_van(request.user),
            "vlaggen": vlaggen(request.user),
        },
    )


@login_required
@require_POST
def spel_start(request):
    """De starttijd staat op de server, zodat de telefoon hem niet kan kiezen."""
    request.session["spel_start"] = time.time()
    return HttpResponse(status=204)


@login_required
@require_POST
def spel_score(request):
    # pop: één start is goed voor één score.
    start = request.session.pop("spel_start", None)
    if start is None:
        return HttpResponseBadRequest("Geen spel gestart")
    try:
        punten = json.loads(request.body)["punten"]
    except (ValueError, KeyError, TypeError):
        return HttpResponseBadRequest("Onbekende score")
    if type(punten) is not int or not 0 <= punten <= MAX_PUNTEN:
        return HttpResponseBadRequest("Onbekende score")
    if punten > (time.time() - start + SPEELRUIMTE_SECONDEN) * MAX_PUNTEN_PER_SECONDE:
        return HttpResponseBadRequest("Onmogelijke score")

    record = False
    if punten > 0:
        nu = timezone.now()
        rij, nieuw = BesteScore.objects.get_or_create(
            medewerker=request.user, defaults={"punten": punten, "behaald_op": nu}
        )
        # In één update-query: twee inzendingen tegelijk kunnen zo een hogere
        # score niet overschrijven.
        record = nieuw or BesteScore.objects.filter(pk=rij.pk, punten__lt=punten).update(
            punten=punten, behaald_op=nu
        ) > 0

    beste = BesteScore.objects.filter(medewerker=request.user).first()
    return JsonResponse(
        {
            "punten": punten,
            "beste": beste.punten if beste else 0,
            "nieuw_record": record,
            "vlaggen": vlaggen(request.user),
            "scorebord": render_to_string("spel/_scorebord.html", {"rijen": ranglijst()}, request=request),
        }
    )
