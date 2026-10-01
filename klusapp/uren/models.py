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
    # Wat er bovenop de afspraak bij kwam: materiaal, kosten, werk dat niet in
    # de offerte staat ("regenpijp vervangen, 3 palen, 40 euro benzine"). Los
    # van de toelichting omdat dit doorbelast wordt: het gaat mee in de
    # urenexport, zodat de administratie het niet uit de werkzaamheden hoeft
    # te vissen. Gewoon tekst, geen bedrag — de prijs zet de administratie
    # erbij (gesprek Maarten, 01-10-2026).
    extra_werk = models.TextField(blank=True)
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

    def save(self, *args, **kwargs):
        """Geen klus op een dag dat iemand afwezig staat. Weigeren in plaats
        van stil overslaan: wie dit probeert, moet het merken."""
        if Aanwezigheid.objects.filter(medewerker_id=self.medewerker_id, datum=self.datum, aanwezig=False).exists():
            raise ValidationError("Op een dag dat iemand afwezig is, kan hij niet op een klus staan.")
        super().save(*args, **kwargs)

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
    """Een afwijking van het vaste rooster: op deze dag wél of juist níet.

    Geen rij betekent "volgens rooster" — de vaste werkdagen van de
    medewerker, met feestdagen vrij (zie uren/bezetting.py). Zo hoeft de
    eigenaar alleen vakantie, ziekte en losse dagen in te vullen, net als in
    zijn Excel waar het hele jaar al groen stond. Alleen de eigenaar ziet en
    zet dit."""

    class Reden(models.TextChoices):
        VAKANTIE = "vakantie", "Vakantie"
        ZIEK = "ziek", "Ziek"
        VRIJ = "vrij", "Vrij"
        ANDERS = "anders", "Anders"

    medewerker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="aanwezigheid",
    )
    datum = models.DateField()
    aanwezig = models.BooleanField(default=True)
    # Alleen bij afwezig. Los van de opmerking, zodat "ziek" telbaar blijft en
    # de opmerking vrij blijft voor "tandarts 12.30–15.00" of "Van Ee".
    reden = models.CharField(max_length=20, choices=Reden.choices, blank=True)
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

    def save(self, *args, **kwargs):
        """Wie afwezig is, gaat nergens heen: zijn klussen voor die dag gaan
        mee weg. Hier en niet alleen in de view, zodat het ook geldt voor
        het beheerscherm, een script of een import."""
        super().save(*args, **kwargs)
        if not self.aanwezig:
            Inzet.objects.filter(medewerker_id=self.medewerker_id, datum=self.datum).delete()


class Dagnotitie(models.Model):
    """Eén regel tekst bij een dag in de werkplanning, voor iedereen tegelijk:
    "Zeevissen", "op tijd weg", "MT-overleg". In de Excel stond dit in een
    losse rij en tussen de getallen in de rij van Maarten."""

    datum = models.DateField(unique=True)
    tekst = models.CharField(max_length=120)
    gewijzigd_op = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "dagnotitie"
        verbose_name_plural = "dagnotities"
        ordering = ["datum"]

    def __str__(self):
        return f"{self.datum:%d-%m-%Y} · {self.tekst}"


class Inzet(models.Model):
    """Wie op welke dag naar welke klus gaat, vooruit gepland in de
    werkplanning. Los van Aanwezigheid: een klus inplannen is geen afwijking
    van het rooster, en wie volgens rooster werkt krijgt er geen stip van.
    Meer klussen op één dag mag — bij onderhoud doe je er zes."""

    medewerker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="inzet",
    )
    datum = models.DateField()
    klus = models.ForeignKey("klussen.Klus", on_delete=models.CASCADE, related_name="inzet")
    aangemaakt_op = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "inzet"
        verbose_name_plural = "inzet"
        ordering = ["datum", "aangemaakt_op"]
        constraints = [
            models.UniqueConstraint(fields=["medewerker", "datum", "klus"], name="een_klus_eenmaal_per_dag")
        ]

    def __str__(self):
        return f"{self.medewerker} · {self.datum:%d-%m-%Y} · {self.klus}"

    def save(self, *args, **kwargs):
        """Geen klus op een dag dat iemand afwezig staat. Weigeren in plaats
        van stil overslaan: wie dit probeert, moet het merken."""
        if Aanwezigheid.objects.filter(medewerker_id=self.medewerker_id, datum=self.datum, aanwezig=False).exists():
            raise ValidationError("Op een dag dat iemand afwezig is, kan hij niet op een klus staan.")
        super().save(*args, **kwargs)
