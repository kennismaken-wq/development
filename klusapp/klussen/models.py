import uuid
from pathlib import Path

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Klus(models.Model):
    """Een eenmalige klus (een adres, een begin en een eind) of een
    onderhoudsklant (terugkerend, zonder einddatum). Dat onderscheid bepaalt
    hoe de klus in het planbord en in de overzichten terugkomt.

    De eenheid is bewust "wat je apart wil optellen", niet "ander werk": een
    tweede adres van dezelfde opdrachtgever is een eigen klus, en een aparte
    afspraak op hetzelfde adres ook — maar maaien en snoeien binnen één
    onderhoudsafspraak zijn hetzelfde klus met een andere toelichting op het
    uurblok. Zonder die regel staan er straks vier regels "Dijkweg 12" in de
    keuzelijst waar de medewerker 's avonds uit moet kiezen.
    """

    class Soort(models.TextChoices):
        # Het label was van 22-09 tot 01-10-2026 "Eenmalig" (de as is ritme,
        # geen soort werk). Maarten wil "Aanleg / Onderhoud": zo praten ze er
        # in het bedrijf over (gesprek 01-10-2026). De databasewaarde is
        # altijd "aanleg" gebleven.
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
    # Gezet zodra actief van aan naar uit gaat (zie save() hieronder). Gebruikt
    # om een kleur uit het palet pas na een tijdje vrij te geven voor een
    # nieuwe klus — zie klussen.kleuren.volgende_kleur.
    afgerond_op = models.DateField(null=True, blank=True)
    aangemaakt_op = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "klus"
        verbose_name_plural = "klussen"
        ordering = ["-actief", "naam"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._actief_bij_laden = self.actief

    def save(self, *args, **kwargs):
        # Alleen aanpassen bij een echte overgang naar inactief: anders
        # overschrijft elke opslag van een allang afgeronde klus zijn eigen
        # afgerond_op-datum, en kan er ook geen bestaande datum worden
        # meegegeven (handmatige correctie, testdata).
        if self.actief:
            self.afgerond_op = None
        elif self._actief_bij_laden or (self._state.adding and self.afgerond_op is None):
            self.afgerond_op = timezone.localdate()
        super().save(*args, **kwargs)
        self._actief_bij_laden = self.actief

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


class BijlageQuerySet(models.QuerySet):
    def zichtbaar_voor(self, gebruiker):
        """Wat deze gebruiker mag zien: alles voor de eigenaar; voor een
        medewerker wat voor iedereen is, wat voor hem is opengezet, en wat
        hij zelf heeft toegevoegd. Zie Bijlage.zichtbaar_voor."""
        if gebruiker.is_eigenaar:
            return self
        toegestaan = Bijlage.zichtbaar_voor.through.objects.filter(medewerker=gebruiker)
        beperkt = Bijlage.zichtbaar_voor.through.objects.values("bijlage")
        return self.filter(
            ~models.Q(pk__in=beperkt)
            | models.Q(pk__in=toegestaan.values("bijlage"))
            | models.Q(toegevoegd_door=gebruiker)
        )


class Bijlage(models.Model):
    """Een foto of document. Hangt aan een klus, aan een uurblok binnen een
    klus, of aan geen van beide — dat laatste is de fotodropbox."""

    objects = BijlageQuerySet.as_manager()

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
    # Gezet op alle bijlagen die uit dezelfde upload komen (zie
    # klussen.views.bewaar_bijlage), zodat het fotoraster ze als één post kan
    # tonen in plaats van los tussen andere foto's. Leeg bij een upload van
    # één bestand — daar is niets te groeperen.
    batch = models.UUIDField(null=True, blank=True, editable=False, db_index=True)
    # Leeg: iedereen ziet het bestand. Staan hier mensen in, dan zien alleen
    # zij het (en de eigenaar, en wie het toevoegde). Voor de offerte met
    # prijzen: die heeft de voorman nodig voor de werkbeschrijving, de rest van
    # de ploeg niet (gesprek Maarten, 01-10-2026; VRAGEN-MAARTEN vraag 10).
    # Per persoon en niet per rol, want wie voorman is wisselt per klus.
    zichtbaar_voor = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="zichtbare_bijlagen",
    )

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

    # Wat een browser zelf kan laten zien. HEIC staat er bewust niet bij:
    # alleen Safari kan dat tonen, en een document gaat ongemoeid door (zie
    # hierboven), dus een HEIC-tekening blijft HEIC.
    AFBEELDING_EXTENSIES = (".jpg", ".jpeg", ".png", ".gif", ".webp")

    @property
    def weergave(self):
        """Hoe de bestand-overlay (klussen/_fotopopup.html) dit toont: als
        "foto", als "pdf" (op een computer in de overlay, op een telefoon
        niet), of als "bestand" — alleen downloaden en delen."""
        if self.is_foto:
            return "foto"
        naam = self.bestand.name.lower()
        if naam.endswith(self.AFBEELDING_EXTENSIES):
            return "foto"
        if naam.endswith(".pdf"):
            return "pdf"
        return "bestand"

    @property
    def extensie(self):
        """"XLSX", "DOCX": op de bestandstegel als er geen voorbeeld is."""
        naam = self.originele_naam or self.bestand.name
        return naam.rsplit(".", 1)[-1].upper() if "." in naam else ""

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

    def mag_zien(self, gebruiker):
        """Zelfde regel als BijlageQuerySet.zichtbaar_voor, voor één bijlage."""
        if gebruiker.is_eigenaar or self.toegevoegd_door_id == gebruiker.pk:
            return True
        lijst = self.zichtbaar_voor.all()
        return not lijst or gebruiker in lijst


class Notitie(models.Model):
    """Een korte aantekening in het klusdossier ("hek staat open, sleutel bij
    de buren"). Ze staan onder elkaar, de nieuwste bovenaan, als een logboek:
    wat er eenmaal geschreven is wordt niet bewerkt, hooguit weggehaald en
    opnieuw geschreven. Zo blijft zichtbaar wie wat wanneer meldde."""

    klus = models.ForeignKey(Klus, on_delete=models.CASCADE, related_name="notities")
    tekst = models.TextField(max_length=2000)
    geschreven_door = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="notities",
    )
    geschreven_op = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "notitie"
        verbose_name_plural = "notities"
        ordering = ["-geschreven_op"]

    def __str__(self):
        return f"Notitie bij {self.klus} van {self.geschreven_door or 'onbekend'}"

    def mag_verwijderen(self, gebruiker):
        """Zelfde regel als bij een bijlage: je eigen notitie, of je bent de
        eigenaar."""
        return gebruiker.is_eigenaar or self.geschreven_door_id == gebruiker.pk
