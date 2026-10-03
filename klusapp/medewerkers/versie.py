"""Niet stilletjes overschrijven wat iemand anders intussen veranderde.

Een formulier slaat alle velden op, ook de velden die je niet aanraakte. Had
Maarten de gegevens van Sam al open terwijl Sam zelf zijn telefoonnummer
aanpaste, dan zette Maartens opslaan het oude nummer terug, zonder dat
iemand het merkte (stresstest 03-10-2026, B17).

Daarom krijgt het formulier een verborgen "versie": een vingerafdruk van de
velden zoals ze in de database stonden toen het formulier werd getoond. Bij
opslaan rekent de server die opnieuw uit; zijn ze anders, dan wordt er niets
opgeslagen en komt er een melding. Een vingerafdruk van de velden zelf en
geen "laatst gewijzigd"-tijd: die verandert bij een medewerker ook bij elke
keer inloggen, en dan kreeg je de melding voor niets.
"""

import hashlib

from django import forms

VEROUDERD = (
    "Iemand anders heeft dit intussen aangepast. Ververs de pagina; "
    "dan zie je de nieuwe gegevens en kun je het opnieuw doen."
)


class VersieMixin:
    """Voor een ModelForm. De template moet `{{ formulier.versie }}` tonen
    (het is een verborgen veld)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["versie"] = forms.CharField(widget=forms.HiddenInput, required=False)
        self._versie_nu = self._versie_van(self.instance) if self.instance.pk else ""
        self.initial["versie"] = self._versie_nu

    def _versie_van(self, instance):
        waarden = [repr(getattr(instance, naam, None)) for naam in self._meta.fields]
        return hashlib.sha256("|".join(waarden).encode()).hexdigest()[:20]

    def clean(self):
        gegevens = super().clean()
        gestuurd = self.data.get(self.add_prefix("versie"))
        if self.instance.pk and gestuurd and gestuurd != self._versie_nu:
            raise forms.ValidationError(VEROUDERD, code="verouderd")
        return gegevens
