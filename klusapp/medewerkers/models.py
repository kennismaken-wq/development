import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


# Alle Nederlandse rijbewijscategorieën, per soort voertuig. De volgorde is
# die van het rijbewijs zelf; zo worden ze ook opgeslagen en getoond.
RIJBEWIJS_GROEPEN = [
    ("Bromfiets en motor", ["AM", "A1", "A2", "A"]),
    ("Auto", ["B", "BE"]),
    ("Vrachtwagen", ["C1", "C1E", "C", "CE"]),
    ("Bus", ["D1", "D1E", "D", "DE"]),
    ("Trekker", ["T"]),
]
RIJBEWIJS_VOLGORDE = [code for _, codes in RIJBEWIJS_GROEPEN for code in codes]


WEEKDAGEN = ["ma", "di", "wo", "do", "vr", "za", "zo"]


def standaard_werkdagen():
    """Maandag tot en met vrijdag. Een functie en geen lijst als default: een
    veranderlijke default wordt anders door alle medewerkers gedeeld."""
    return [0, 1, 2, 3, 4]


def profielfoto_pad(instance, bestandsnaam):
    """Eigen bestandsnaam: telefoons leveren allemaal IMG_0001.jpg aan."""
    return f"profielfotos/{uuid.uuid4().hex}.jpg"


class Medewerker(AbstractUser):
    """Iedereen die inlogt. De rol bepaalt wat je ziet.

    Eigenaar ziet alles; een medewerker ziet alleen zijn eigen uren, maar wel
    het volledige klusdossier.
    """

    class Rol(models.TextChoices):
        MEDEWERKER = "medewerker", "Medewerker"
        EIGENAAR = "eigenaar", "Eigenaar"

    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.MEDEWERKER)
    # Wat iemand doet, niet wat hij mag. "Voorman", "hovenier", "leerling" —
    # staat naast zijn naam in het klusdossier. De rol hierboven bepaalt de
    # rechten; dit veld bepaalt niets en is puur ter herkenning.
    functie = models.CharField(max_length=60, blank=True)

    # Eén verkleinde versie, geen origineel: zie klussen/afbeeldingen.py. Een
    # pasfoto van 400px is ruim genoeg voor een rondje van 40 en voor de kop
    # van het profielscherm.
    profielfoto = models.ImageField(upload_to=profielfoto_pad, blank=True)

    # ── contact ───────────────────────────────────────────────────────────
    telefoon = models.CharField("mobiel nummer", max_length=20, blank=True)
    adres = models.CharField(max_length=120, blank=True)
    postcode = models.CharField(max_length=10, blank=True)
    woonplaats = models.CharField(max_length=80, blank=True)

    # Bij wie je belt als er op een klus iets gebeurt. In dit werk wordt met
    # machines gewerkt; dan wil je niet gaan zoeken.
    noodcontact_naam = models.CharField(max_length=80, blank=True)
    noodcontact_relatie = models.CharField(
        max_length=40, blank=True, help_text="Bijvoorbeeld partner, moeder, broer."
    )
    noodcontact_telefoon = models.CharField(max_length=20, blank=True)

    # Waar de wekelijkse back-up van uren en aanwezigheid heen gaat
    # (uren/backup.py). Alleen een eigenaar ziet en zet dit, op Mijn profiel.
    # Los van `email`: dat is het adres voor "wachtwoord vergeten", en de
    # back-up wil Maarten misschien juist in een gedeelde administratiebox.
    backup_email = models.EmailField("back-up naar", blank=True)

    # ── rijbewijs ─────────────────────────────────────────────────────────
    # Bepaalt wie met de bus, de kipper of de aanhanger met de minigraver weg
    # mag. Een lijst categorieën uit RIJBEWIJS_GROEPEN, zoals ["B", "BE", "C"];
    # BE is dus gewoon een categorie en geen los vinkje meer (29-09-2026).
    # Certificaten die verlopen houden we er bewust buiten. Een JSON-lijst en
    # geen ArrayField: dat werkt alleen op Postgres, en lokaal is het SQLite.
    rijbewijzen = models.JSONField(default=list, blank=True)
    kleur = models.CharField(
        max_length=7,
        blank=True,
        help_text="Hexkleur waarmee deze medewerker in het planbord wordt getoond.",
    )
    # De dagen waarop iemand standaard werkt, als weekdagnummers (0 = maandag).
    # De werkplanning zet hem op die dagen vanzelf op aanwezig, zoals Maarten
    # in zijn Excel aan het begin van het jaar iedereen groen maakte; alleen
    # wat daarvan afwijkt wordt als Aanwezigheid opgeslagen. Een lege lijst is
    # een oproep- of seizoenskracht: die staat alleen op dagen die je zelf zet.
    vaste_werkdagen = models.JSONField(default=standaard_werkdagen, blank=True)
    in_dienst_sinds = models.DateField(null=True, blank=True)
    uit_dienst_sinds = models.DateField(
        null=True,
        blank=True,
        help_text="Ingevuld als iemand uit dienst is. Uren en foto's blijven bewaard.",
    )

    class Meta:
        verbose_name = "medewerker"
        verbose_name_plural = "medewerkers"
        ordering = ["first_name", "last_name", "username"]

    def __str__(self):
        return self.naam

    @property
    def naam(self):
        volledig = f"{self.first_name} {self.last_name}".strip()
        return volledig or self.username

    @property
    def initialen(self):
        """Twee letters voor het rondje op het planbord."""
        letters = [deel[0] for deel in (self.first_name, self.last_name) if deel]
        return "".join(letters).upper() or self.username[:2].upper()

    def save(self, *args, **kwargs):
        # TIJDELIJK — september 2026. Er is nog geen superuser aangemaakt, dus
        # zonder dit komt niemand in /beheer/. Een eigenaar krijgt daarom
        # voorlopig toegang tot het Django-beheerscherm. Zodra er een eigen
        # beheeraccount is, moet dit eruit en hangt /beheer/ weer aan een
        # aparte rol; zie de gesprekken over de rol "systeembeheerder".
        # Op degroenem.handigerai.nl staat TESTFUNCTIES uit, en dan geldt
        # dit niet: daar komt alleen een superuser in /beheer/.
        eigenaar_beheert = self.rol == self.Rol.EIGENAAR and settings.TESTFUNCTIES
        self.is_staff = eigenaar_beheert or self.is_superuser
        super().save(*args, **kwargs)

    @property
    def rijbewijzen_tekst(self):
        """Voor de persoonskaart: "B, BE, C", of "Geen"."""
        return ", ".join(self.rijbewijzen) or "Geen"

    @property
    def is_eigenaar(self):
        return self.rol == self.Rol.EIGENAAR
