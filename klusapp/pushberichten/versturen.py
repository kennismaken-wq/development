"""Het eigenlijke versturen. Losse module, zodat de tests webpush kunnen
vervangen en er nooit echt iets naar Apple of Google gaat."""
import base64
import json
import logging
import threading

from cryptography.hazmat.primitives import serialization
from django.db import close_old_connections
from py_vapid import Vapid02
from pywebpush import WebPushException, webpush

from .models import Abonnement, Sleutelpaar

log = logging.getLogger(__name__)

WACHTTIJD = 60  # seconden na het sluiten van de app


def sleutelpaar():
    paar = Sleutelpaar.objects.first()
    if paar:
        return paar
    vapid = Vapid02()
    vapid.generate_keys()
    publiek = vapid.public_key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return Sleutelpaar.objects.create(
        prive_pem=vapid.private_pem().decode(),
        publiek=base64.urlsafe_b64encode(publiek).rstrip(b"=").decode(),
    )


def stuur(abonnement, titel, tekst, url="/"):
    """Eén melding naar één toestel. Geeft False als het niet lukte. Heeft het
    toestel het abonnement opgezegd (404/410), dan gooien we het hier weg."""
    paar = sleutelpaar()
    try:
        webpush(
            subscription_info={
                "endpoint": abonnement.endpoint,
                "keys": {"p256dh": abonnement.p256dh, "auth": abonnement.auth},
            },
            data=json.dumps({"titel": titel, "tekst": tekst, "url": url}),
            vapid_private_key=Vapid02.from_pem(paar.prive_pem.encode()),
            vapid_claims={"sub": "mailto:klusapp@handigerai.nl"},
            ttl=300,
        )
        return True
    except WebPushException as fout:
        status = getattr(fout.response, "status_code", None)
        if status in (404, 410):
            abonnement.delete()
        else:
            log.warning("Pushmelding mislukt (%s): %s", status, fout)
        return False
    except Exception:  # netwerk weg, pushdienst onbereikbaar: niet de thread laten crashen
        log.exception("Pushmelding mislukt")
        return False


def stuur_als_nog_dicht(abonnement_pk, gesloten_om):
    """Draait een minuut na het sluiten in een eigen thread. Is de app
    sindsdien weer geopend (of opnieuw gesloten), dan gebeurt er niets."""
    close_old_connections()
    try:
        abonnement = Abonnement.objects.filter(pk=abonnement_pk).first()
        if not abonnement or abonnement.gesloten_om != gesloten_om:
            return False
        if abonnement.geopend_om and abonnement.geopend_om > gesloten_om:
            return False
        return stuur(
            abonnement,
            "De Groene M",
            "Testmelding: je hebt de app een minuut geleden gesloten. Meldingen werken!",
        )
    finally:
        close_old_connections()


def plan_na_sluiten(abonnement):
    """Een eenvoudige timer in het gunicorn-proces: goed genoeg voor deze
    test. Herstart de server binnen die minuut, dan vervalt de melding."""
    timer = threading.Timer(
        WACHTTIJD, stuur_als_nog_dicht, args=(abonnement.pk, abonnement.gesloten_om)
    )
    timer.daemon = True
    timer.start()
    return timer
