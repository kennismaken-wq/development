import uuid
from pathlib import Path

from django.conf import settings
from django.db import models
from django.utils import timezone


class Klus(models.Model):
    """Een aanlegklus (een adres, weken werk) of een onderhoudsklant
    (terugkerend, zonder einddatum). Dat onderscheid bepaalt hoe de klus in
    het planbord en in de overzichten terugkomt."""

    class Soort(models.TextChoices):
        AANLEG = "aanleg", "Aanleg"
        ONDERHOUD = "onderhoud", "Onderhoud"

    naam = models.CharField(max_length=120)
    soort = models.CharField(max_length=20, choices=Soort.choices, default=Soort.AANLEG)
    opdrachtgever = models.CharField(max_length=120, blank=True)
    adres = models.CharField(max_length=200, blank=True)
    plaats = models.CharField(max_length=80, blank=True)
    kleur = models.CharField(
        max_length=7,
        blank=True,
        help_text="Hexkleur van de blokken in het planbord.",
    )
    actief = models.BooleanField(default=True)
    aangemaakt_op = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "klus"
        verbose_name_plural = "klussen"
        ordering = ["-actief", "naam"]

    def __str__(self):
        return self.naam


def bijlage_pad(instance, bestandsnaam):
    """Bewaar op datum, met een eigen naam: telefoons leveren allemaal
    IMG_0001.jpg aan en dat overschrijft elkaar."""
    achtervoegsel = Path(bestandsnaam).suffix.lower()
    # toegevoegd_op is nog niet gezet als het bestand wordt weggeschreven,
    # dus we nemen de klok van nu.
    map_naam = timezone.localdate().strftime("%Y/%m")
    return f"bijlagen/{map_naam}/{uuid.uuid4().hex}{achtervoegsel}"


class Bijlage(models.Model):
    """Een foto of document. Hangt aan een klus, aan een uurblok binnen een
    klus, of aan geen van beide — dat laatste is de fotodropbox."""

    class Soort(models.TextChoices):
        FOTO = "foto", "Foto"
        DOCUMENT = "document", "Document"

    bestand = models.FileField(upload_to=bijlage_pad)
    soort = models.CharField(max_length=20, choices=Soort.choices, default=Soort.FOTO)
    toelichting = models.TextField(blank=True)
    klus = models.ForeignKey(
        Klus,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="bijlagen",
    )
    uurblok = models.ForeignKey(
        "uren.Uurblok",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bijlagen",
    )
    toegevoegd_door = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="bijlagen",
    )
    toegevoegd_op = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "bijlage"
        verbose_name_plural = "bijlagen"
        ordering = ["-toegevoegd_op"]

    def __str__(self):
        return f"{self.get_soort_display()} van {self.toegevoegd_door or 'onbekend'}"

    @property
    def in_dropbox(self):
        return self.klus_id is None
