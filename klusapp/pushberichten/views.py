"""TIJDELIJK / TEST: meldingen aanzetten en de app dicht/open melden. Alles
geeft 404 als settings.TESTFUNCTIES uit staat (Maartens omgeving)."""
import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from . import versturen
from .models import Abonnement


def _alleen_test():
    if not settings.TESTFUNCTIES:
        raise Http404


@login_required
@require_GET
def sleutel(request):
    _alleen_test()
    return JsonResponse({"sleutel": versturen.sleutelpaar().publiek})


@login_required
@require_POST
def aanmelden(request):
    _alleen_test()
    try:
        data = json.loads(request.body)
        endpoint = data["endpoint"]
        p256dh = data["keys"]["p256dh"]
        auth = data["keys"]["auth"]
    except (ValueError, KeyError, TypeError):
        return HttpResponseBadRequest("Onbekend abonnement")
    if not isinstance(endpoint, str) or not endpoint.startswith("https://"):
        return HttpResponseBadRequest("Onbekend abonnement")
    Abonnement.objects.update_or_create(
        endpoint=endpoint,
        defaults={"medewerker": request.user, "p256dh": p256dh, "auth": auth},
    )
    return HttpResponse(status=204)


@login_required
@require_POST
def status(request):
    """De app meldt zich 'dicht' (visibilitychange naar hidden) of 'open'.
    Komt binnen via navigator.sendBeacon, dus als formulier met CSRF-token."""
    _alleen_test()
    endpoint = request.POST.get("endpoint", "")
    abonnement = Abonnement.objects.filter(endpoint=endpoint, medewerker=request.user).first()
    if not abonnement:
        return HttpResponse(status=204)
    nu = timezone.now()
    if request.POST.get("stand") == "dicht":
        abonnement.gesloten_om = nu
        abonnement.save(update_fields=["gesloten_om"])
        versturen.plan_na_sluiten(abonnement)
    else:
        abonnement.geopend_om = nu
        abonnement.save(update_fields=["geopend_om"])
    return HttpResponse(status=204)
