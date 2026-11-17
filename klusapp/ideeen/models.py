"""De ideeënbus (fase 2): iedereen kan een idee intypen, de anderen kunnen het
liken, en de eigenaar zet er een stand bij met eventueel een korte reactie.

Anoniem insturen kan. Dan bewaart de app geen naam: `door` blijft leeg. De
serverlogs bewaren wel tijd en IP-adres, dus we beloven "anoniem in de app",
niet meer (fase2-plan, 05-11-2026). Een anoniem idee is ook voor de schrijver
niet meer aan hem te koppelen; weghalen kan dan alleen de eigenaar.
"""

from django.conf import settings
from django.db import models


class Idee(models.Model):
    class Stand(models.TextChoices):
        NIEUW = "nieuw", "Nieuw"
        DOEN_WE = "doen_we", "Doen we"
        GEDAAN = "gedaan", "Gedaan"
        NIET = "niet", "Niet"

    tekst = models.TextField(max_length=1000)
    # Leeg = anoniem ingestuurd (of het account is verwijderd).
    door = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="ideeen"
    )
    stand = models.CharField(max_length=10, choices=Stand.choices, default=Stand.NIEUW)
    reactie = models.CharField("reactie van de eigenaar", max_length=300, blank=True)
    gemaakt_op = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "idee"
        verbose_name_plural = "ideeën"
        ordering = ["-gemaakt_op"]

    def __str__(self):
        return self.tekst[:60]

    def mag_verwijderen(self, gebruiker):
        """Je eigen idee (met naam), of je bent de eigenaar."""
        return gebruiker.is_eigenaar or (self.door_id is not None and self.door_id == gebruiker.pk)


class Like(models.Model):
    idee = models.ForeignKey(Idee, on_delete=models.CASCADE, related_name="likes")
    medewerker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="idee_likes")
    gemaakt_op = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "like"
        verbose_name_plural = "likes"
        constraints = [models.UniqueConstraint(fields=["idee", "medewerker"], name="een_like_per_persoon")]
