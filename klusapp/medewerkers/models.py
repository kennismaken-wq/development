import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


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

    # ── rijbewijs ─────────────────────────────────────────────────────────
    # Bepaalt wie met de bus, de kipper of de aanhanger met de minigraver weg
    # mag. Alleen de categorie en de aanhanger; certificaten die verlopen
    # houden we er bewust buiten.
    class Rijbewijs(models.TextChoices):
        GEEN = "", "Geen"
        B = "B", "B — personenauto"
        C = "C", "C — vrachtwagen"

    rijbewijs = models.CharField(max_length=2, choices=Rijbewijs.choices, blank=True)
    aanhanger = models.BooleanField(
        "aanhanger (BE)", default=False, help_text="Mag met een zware aanhanger rijden."
    )
    kleur = models.CharField(
        max_length=7,
        blank=True,
        help_text="Hexkleur waarmee deze medewerker in het planbord wordt getoond.",
    )
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
        self.is_staff = self.rol == self.Rol.EIGENAAR or self.is_superuser
        super().save(*args, **kwargs)

    @property
    def is_eigenaar(self):
        return self.rol == self.Rol.EIGENAAR
