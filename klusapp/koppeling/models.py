"""De koppeling met Claude (offerte 2026-O01, onderdeel 2).

Claude logt in via OAuth 2.1, zoals een app die "Inloggen met..." doet: de
eigenaar ziet in de klusapp een scherm "Claude wil meelezen", tikt op
Toestaan, en Claude krijgt een sleutel die alleen kan lezen. Die sleutel is
een `Koppeling`. Intrekken = de koppeling op ingetrokken zetten; elke
volgende vraag van Claude stuit dan op een 401.

Tokens staan hier nooit leesbaar in de database, alleen hun SHA-256. Wie de
database in handen krijgt, kan er dus niet mee bij de app.
"""

import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

# Een access token is kort geldig; Claude haalt met de refresh token zelf een
# nieuwe. Intrekken werkt hoe dan ook meteen (er wordt per verzoek gekeken),
# dit beperkt alleen de schade van een token dat ergens in een log belandt.
ACCESS_GELDIG = timedelta(hours=1)
# Een refresh token die zo lang niet is gebruikt, vervalt: een vergeten
# koppeling blijft niet eeuwig open. Bij elk gebruik schuift dit op.
REFRESH_GELDIG = timedelta(days=90)
# Twee keer tegelijk vernieuwen (een dubbele klik, een herhaald verzoek) is
# onschuldig. Wie een oude refresh token pas later nog eens aanbiedt, heeft
# hem ergens vandaan: dan trekken we de hele koppeling in (OAuth 2.1).
HERGEBRUIK_MARGE = timedelta(seconds=60)
# Een autorisatiecode is eenmalig en hoort binnen seconden te worden ingewisseld.
CODE_GELDIG = timedelta(minutes=5)


def nieuw_token():
    return secrets.token_urlsafe(32)


def vingerafdruk(token):
    return hashlib.sha256(token.encode()).hexdigest()


class Client(models.Model):
    """Een programma dat zich heeft aangemeld (dynamische registratie,
    RFC 7591). Voor Claude gebeurt dat vanzelf bij het toevoegen van de
    connector. Aanmelden geeft nog geen enkele toegang: dat doet pas het
    toestemmingsscherm, en alleen voor een eigenaar."""

    client_id = models.CharField(max_length=64, unique=True, default=nieuw_token)
    naam = models.CharField(max_length=120, blank=True)
    redirect_uris = models.JSONField(default=list)
    # Voor de rem op aanmelden (oauth.registreren).
    ip = models.GenericIPAddressField(null=True, blank=True)
    aangemaakt_op = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "OAuth-client"
        verbose_name_plural = "OAuth-clients"

    def __str__(self):
        return self.naam or self.client_id


class Autorisatiecode(models.Model):
    """De eenmalige code tussen "Toestaan" en het ophalen van de tokens."""

    code_hash = models.CharField(max_length=64, unique=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    medewerker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    redirect_uri = models.CharField(max_length=500)
    # PKCE (S256): alleen wie de code aanvroeg kent het geheim dat erbij hoort.
    code_challenge = models.CharField(max_length=128)
    verloopt_op = models.DateTimeField()

    def verlopen(self):
        return timezone.now() >= self.verloopt_op


class KoppelingQuerySet(models.QuerySet):
    def actief(self):
        return self.filter(ingetrokken_op__isnull=True)


class Koppeling(models.Model):
    """Eén keer "Toestaan": de toegang van één Claude-account voor één
    eigenaar. Staat op het scherm Koppeling met Claude, met een knop om hem
    in te trekken."""

    objects = KoppelingQuerySet.as_manager()

    medewerker = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="claudekoppelingen"
    )
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="koppelingen")
    access_hash = models.CharField(max_length=64, unique=True)
    access_verloopt_op = models.DateTimeField()
    # Wisselt bij elk gebruik (rotatie): een uitgelekte oude refresh token
    # doet daarna niets meer.
    refresh_hash = models.CharField(max_length=64, unique=True)
    refresh_verloopt_op = models.DateTimeField()
    # De refresh token van één ronde terug, om hergebruik te herkennen.
    vorige_refresh_hash = models.CharField(max_length=64, blank=True, db_index=True)
    geroteerd_op = models.DateTimeField(null=True, blank=True)
    aangemaakt_op = models.DateTimeField(auto_now_add=True)
    laatst_gebruikt_op = models.DateTimeField(null=True, blank=True)
    ingetrokken_op = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "koppeling met Claude"
        verbose_name_plural = "koppelingen met Claude"
        ordering = ["-aangemaakt_op"]

    def __str__(self):
        return f"{self.client} voor {self.medewerker}"

    def nieuwe_tokens(self):
        """Zet een vers paar en geeft ze leesbaar terug, één keer. Slaat niet op."""
        access, refresh = nieuw_token(), nieuw_token()
        nu = timezone.now()
        if self.refresh_hash:
            self.vorige_refresh_hash = self.refresh_hash
            self.geroteerd_op = nu
        self.access_hash = vingerafdruk(access)
        self.refresh_hash = vingerafdruk(refresh)
        self.access_verloopt_op = nu + ACCESS_GELDIG
        self.refresh_verloopt_op = nu + REFRESH_GELDIG
        return access, refresh

    def mag_lezen(self):
        """Ook een koppeling die nooit is ingetrokken, werkt niet meer zodra
        het account geen eigenaar meer is of is uitgezet."""
        m = self.medewerker
        return self.ingetrokken_op is None and m.is_active and m.is_eigenaar
