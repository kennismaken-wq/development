from django.conf import settings
from django.db import models


class BesteScore(models.Model):
    """De hoogste score van één medewerker in het springspel. Eén rij per
    persoon: er is alleen een scorebord aller tijden (offerte 2026-O01)."""

    medewerker = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="beste_score")
    punten = models.PositiveIntegerField()
    behaald_op = models.DateTimeField()

    class Meta:
        verbose_name = "beste score"
        verbose_name_plural = "beste scores"
        indexes = [models.Index(fields=["-punten", "behaald_op"])]

    def __str__(self):
        return f"{self.medewerker}: {self.punten}"
