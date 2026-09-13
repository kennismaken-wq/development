from datetime import datetime, time

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Uurblok(models.Model):
    """Een blok gewerkte tijd van één medewerker op één klus op één dag.

    Bij onderhoud doet iemand zes tot acht adressen op een dag; dat worden dus
    net zoveel blokken. Bij aanleg is het er meestal één.
    """

    medewerker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="uurblokken",
    )
    klus = models.ForeignKey(
        "klussen.Klus",
        on_delete=models.PROTECT,
        related_name="uurblokken",
    )
    datum = models.DateField()
    begintijd = models.TimeField()
    eindtijd = models.TimeField()
    toelichting = models.TextField(blank=True)
    aangemaakt_op = models.DateTimeField(auto_now_add=True)
    gewijzigd_op = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "uurblok"
        verbose_name_plural = "uurblokken"
        ordering = ["-datum", "begintijd"]
        indexes = [
            models.Index(fields=["datum", "medewerker"]),
            models.Index(fields=["klus", "datum"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(eindtijd__gt=models.F("begintijd")),
                name="eindtijd_na_begintijd",
            )
        ]

    def __str__(self):
        return f"{self.medewerker} · {self.datum:%d-%m-%Y} · {self.klus}"

    def clean(self):
        if self.begintijd and self.eindtijd and self.eindtijd <= self.begintijd:
            raise ValidationError({"eindtijd": "De eindtijd moet na de begintijd liggen."})

    @property
    def duur_minuten(self):
        begin = datetime.combine(self.datum, self.begintijd or time())
        eind = datetime.combine(self.datum, self.eindtijd or time())
        return int((eind - begin).total_seconds() // 60)

    @property
    def duur_uren(self):
        return self.duur_minuten / 60


class Aanwezigheid(models.Model):
    """Per dag bijhouden wie er is. De eigenaar zet dit; medewerkers zien het
    alleen. Groen of rood, met eventueel een reden."""

    medewerker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="aanwezigheid",
    )
    datum = models.DateField()
    aanwezig = models.BooleanField(default=True)
    opmerking = models.CharField(max_length=200, blank=True)
    gewijzigd_op = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "aanwezigheid"
        verbose_name_plural = "aanwezigheid"
        ordering = ["-datum"]
        constraints = [
            models.UniqueConstraint(fields=["medewerker", "datum"], name="een_registratie_per_dag")
        ]

    def __str__(self):
        stand = "aanwezig" if self.aanwezig else "afwezig"
        return f"{self.medewerker} · {self.datum:%d-%m-%Y} · {stand}"
