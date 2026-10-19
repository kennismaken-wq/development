"""Pushmeldingen naar de app op het beginscherm (Web Push).

TIJDELIJK / TEST (okt. 2026): alleen aan met settings.TESTFUNCTIES, dus
op develop.handigerai.nl en niet op Maartens omgeving. Het enige wat het nu
doet is één melding sturen een minuut nadat je de app sluit, om te laten
zien dat meldingen op de telefoon werken. Zie pushberichten/views.py.
"""
from django.conf import settings
from django.db import models


class Sleutelpaar(models.Model):
    """Het VAPID-sleutelpaar waarmee de server zich bij Apple en Google
    meldt. Wordt bij het eerste gebruik zelf aangemaakt (versturen.py), zodat
    er geen geheim in de repo of de .env hoeft. Er is er altijd maar één."""

    prive_pem = models.TextField()
    publiek = models.CharField(max_length=100)  # base64url, gaat naar de browser
    aangemaakt = models.DateTimeField(auto_now_add=True)


class Abonnement(models.Model):
    """Eén toestel dat meldingen wil ontvangen. Het endpoint is een adres bij
    de pushdienst van Apple of Google; p256dh en auth versleutelen de inhoud."""

    medewerker = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pushabonnementen"
    )
    endpoint = models.URLField(max_length=1000, unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    aangemaakt = models.DateTimeField(auto_now_add=True)
    # Wanneer de app voor het laatst dicht ging en weer open; de melding gaat
    # alleen als hij na een minuut nog steeds dicht is.
    gesloten_om = models.DateTimeField(null=True, blank=True)
    geopend_om = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.medewerker} · {self.endpoint[:40]}…"
