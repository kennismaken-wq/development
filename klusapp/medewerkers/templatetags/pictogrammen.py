"""Geeft de binnenkant van een navigatie-icoon terug als veilige HTML.

De markup staat vast in medewerkers/pictogrammen.py — zelf geschreven, geen
gebruikersinvoer — dus mark_safe hier is geen risico.
"""

from django import template
from django.utils.safestring import mark_safe

from medewerkers.pictogrammen import PICTOGRAMMEN

register = template.Library()


@register.filter
def pictogram(naam):
    return mark_safe(PICTOGRAMMEN.get(naam, ""))
