from django.contrib.auth.models import AbstractUser
from django.db import models


class Medewerker(AbstractUser):
    """Iedereen die inlogt. De rol bepaalt wat je ziet.

    Eigenaar ziet alles; een medewerker ziet alleen zijn eigen uren, maar wel
    het volledige klusdossier.
    """

    class Rol(models.TextChoices):
        MEDEWERKER = "medewerker", "Medewerker"
        EIGENAAR = "eigenaar", "Eigenaar"

    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.MEDEWERKER)
    telefoon = models.CharField(max_length=20, blank=True)
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
    def is_eigenaar(self):
        return self.rol == self.Rol.EIGENAAR
