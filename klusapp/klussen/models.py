import uuid
from pathlib import Path

from django.conf import settings
from django.db import models
from django.urls import reverse
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
    # Leeg bij onderhoud: een onderhoudsklant is een terugkerende afspraak
    # zonder begin, geen project dat op een dag start.
    startdatum = models.DateField(null=True, blank=True)
    beschrijving = models.TextField(blank=True)
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

    def get_absolute_url(self):
        return reverse("klus_detail", args=[self.pk])


def bijlage_pad(instance, bestandsnaam):
    """Bewaar op datum, met een eigen naam: telefoons leveren allemaal
    IMG_0001.jpg aan en dat overschrijft elkaar."""
    achtervoegsel = Path(bestandsnaam).suffix.lower()
    # toegevoegd_op is nog niet gezet als het bestand wordt weggeschreven,
    # dus we nemen de klok van nu.
    map_naam = timezone.localdate().strftime("%Y/%m")
    return f"bijlagen/{map_naam}/{uuid.uuid4().hex}{achtervoegsel}"


def thumbnail_pad(instance, bestandsnaam):
    """Thumbnails in een eigen map, zodat ze in één keer weg te gooien en
    opnieuw te maken zijn als we ooit een ander formaat willen."""
    achtervoegsel = Path(bestandsnaam).suffix.lower()
    map_naam = timezone.localdate().strftime("%Y/%m")
    return f"thumbnails/{map_naam}/{uuid.uuid4().hex}{achtervoegsel}"


class Bijlage(models.Model):
    """Een foto of document. Hangt aan een klus, aan een uurblok binnen een
    klus, of aan geen van beide — dat laatste is de fotodropbox."""

    class Soort(models.TextChoices):
        FOTO = "foto", "Foto"
        DOCUMENT = "document", "Document"

    # Bij een foto staat hier de verkleinde versie, niet het origineel uit de
    # telefoon: een jaar ruwe foto's loopt richting tientallen gigabytes en
    # niemand kijkt ooit naar die pixels. Documenten gaan ongemoeid door.
    bestand = models.FileField(upload_to=bijlage_pad)
    # Zonder aparte thumbnail laadt een raster van dertig foto's dertig volle
    # bestanden; over 4G in de bus is dat het verschil tussen bruikbaar en niet.
    thumbnail = models.FileField(upload_to=thumbnail_pad, blank=True)
    # bijlage_pad() slaat op onder een uuid, dus zonder dit veld heet een
    # tekening in de documentenlijst "a3f2c1...pdf".
    originele_naam = models.CharField(max_length=255, blank=True)
    soort = models.CharField(max_length=20, choices=Soort.choices, default=Soort.FOTO)
    # De dag waar de foto/het document over gaat — niet per se de dag van
    # uploaden. Iemand fotografeert een klus vaak pas 's avonds thuis, of
    # haalt een tekening pas een dag later van de mail; toegevoegd_op
    # (hieronder) blijft de echte uploadtijd voor de audit trail, datum is
    # wat er in het dossier en het overzicht wordt getoond en wordt
    # gesorteerd op.
    datum = models.DateField(default=timezone.localdate)
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
        ordering = ["-datum", "-toegevoegd_op"]

    def __str__(self):
        return f"{self.get_soort_display()} van {self.toegevoegd_door or 'onbekend'}"

    @property
    def in_dropbox(self):
        return self.klus_id is None

    @property
    def is_foto(self):
        return self.soort == self.Soort.FOTO

    @property
    def toonnaam(self):
        """Wat er in een lijst moet staan. Een foto heeft zelden een zinnige
        bestandsnaam, dus daar wint de toelichting."""
        if self.is_foto:
            return self.toelichting or self.originele_naam or "Foto"
        return self.originele_naam or "Document"

    def mag_verwijderen(self, gebruiker):
        """Je eigen bijlage, of je bent de eigenaar. Een medewerker haalt dus
        niet per ongeluk de tekening van een ander weg."""
        return gebruiker.is_eigenaar or self.toegevoegd_door_id == gebruiker.pk
