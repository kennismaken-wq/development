"""Een rem op wachtwoorden raden en op "wachtwoord vergeten"-mails.

De site staat open op internet. Zonder rem waren 30 foute wachtwoorden
achter elkaar gewoon mogelijk, en gaven 30 aanvragen 30 mails vanaf het
afzenderadres — genoeg om dat bij Gmail of Outlook als spam te laten
markeren, en dan komt de back-upmail ook niet meer aan (stresstest
03-10-2026, B5).

Inloggen: na MAX_PER_NAAM mislukte pogingen op één gebruikersnaam, of
MAX_PER_IP vanaf één adres, een kwartier niet. Gelukt inloggen wist de teller
van die naam. Wachtwoord vergeten: hooguit een paar mails per adres per uur;
daarboven toont het scherm hetzelfde ("kijk in je mail"), zodat het niet
verklapt welke adressen bestaan, maar gaat er niets meer de deur uit.
"""

from datetime import timedelta

from django.utils import timezone

from .models import Poging

VENSTER_INLOGGEN = timedelta(minutes=15)
MAX_PER_NAAM = 10
MAX_PER_IP = 50

VENSTER_RESET = timedelta(hours=1)
MAX_RESET_PER_ADRES = 3
MAX_RESET_PER_IP = 10

TE_VEEL_POGINGEN = (
    "Te veel pogingen. Wacht een kwartier en probeer het dan opnieuw, "
    "of gebruik 'Wachtwoord vergeten'."
)


def ip_van(request):
    # nginx zet X-Real-IP (docs/DEPLOY.md); zonder nginx (lokaal) het directe adres.
    return request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR") or None


def _recent(soort, venster):
    return Poging.objects.filter(soort=soort, tijdstip__gte=timezone.now() - venster)


def _opruimen():
    Poging.objects.filter(tijdstip__lt=timezone.now() - timedelta(days=1)).delete()


def inloggen_geblokkeerd(request, naam):
    recent = _recent(Poging.Soort.INLOGGEN, VENSTER_INLOGGEN)
    if recent.filter(sleutel=naam.strip().lower()).count() >= MAX_PER_NAAM:
        return True
    ip = ip_van(request)
    return bool(ip) and recent.filter(ip=ip).count() >= MAX_PER_IP


def inloggen_mislukt(request, naam):
    _opruimen()
    Poging.objects.create(soort=Poging.Soort.INLOGGEN, sleutel=naam.strip().lower()[:254], ip=ip_van(request))


def inloggen_gelukt(naam):
    Poging.objects.filter(soort=Poging.Soort.INLOGGEN, sleutel=naam.strip().lower()).delete()


def reset_toegestaan(request, adres):
    """Telt de aanvraag mee, en zegt of er nog een mail mag."""
    _opruimen()
    adres = adres.strip().lower()[:254]
    ip = ip_van(request) if request else None
    recent = _recent(Poging.Soort.RESET, VENSTER_RESET)
    te_veel = recent.filter(sleutel=adres).count() >= MAX_RESET_PER_ADRES or (
        bool(ip) and recent.filter(ip=ip).count() >= MAX_RESET_PER_IP
    )
    Poging.objects.create(soort=Poging.Soort.RESET, sleutel=adres, ip=ip)
    return not te_veel
