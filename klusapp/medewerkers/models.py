from django.contrib.auth.models import AbstractUser
from django.db import models


class Medewerker(AbstractUser):
    """Iedereen die inlogt. De rol bepaalt wat je ziet.

    Een medewerker ziet alleen zijn eigen uren, maar wel het volledige
    klusdossier. Een eigenaar ziet alles van het bedrijf. Daarboven staat de
    systeembeheerder: dat zijn wij, en dat is de enige rol die in het
    Django-beheerscherm komt.
    """

    class Rol(models.TextChoices):
        MEDEWERKER = "medewerker", "Medewerker"
        EIGENAAR = "eigenaar", "Eigenaar"
        BEHEERDER = "beheerder", "Systeembeheerder"

    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.MEDEWERKER)
    # Wat iemand doet, niet wat hij mag. "Voorman", "hovenier", "leerling" —
    # staat naast zijn naam in het klusdossier. De rol hierboven bepaalt de
    # rechten; dit veld bepaalt niets en is puur ter herkenning.
    functie = models.CharField(max_length=60, blank=True)

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

    def save(self, *args, **kwargs):
        # createsuperuser kent onze rollen niet en zet alleen de vlaggen van
        # Django; wie superuser is, is bij ons systeembeheerder.
        if self.is_superuser:
            self.rol = self.Rol.BEHEERDER
        # De toegang tot het Django-beheerscherm hangt aan de rol, en nergens
        # anders aan. Zo kunnen die twee niet uit elkaar lopen en kan niemand
        # per ongeluk binnenkomen door een vinkje te zetten.
        self.is_staff = self.rol == self.Rol.BEHEERDER
        super().save(*args, **kwargs)

    @property
    def is_systeembeheerder(self):
        """Alleen deze rol komt in het Django-beheerscherm."""
        return self.rol == self.Rol.BEHEERDER

    @property
    def is_eigenaar(self):
        """Mag alles zien wat het bedrijf aangaat.

        De systeembeheerder valt hier ook onder: die moet kunnen meekijken
        als er iets aan de hand is.
        """
        return self.rol in (self.Rol.EIGENAAR, self.Rol.BEHEERDER)
