"""Dezelfde kleur tonen als het planbord, ook buiten uren/.

uren.kalender.kleur_van() is de bestaande bron van waarheid voor "welke kleur
hoort bij deze klus" (inclusief de terugvalkleur voor het zeldzame geval dat
kleur toch leeg is). Klussenlijst en klusdossier zijn geen onderdeel van
uren/, maar moeten wel dezelfde kleur laten zien — vandaar dit filter in
plaats van de functie los te dupliceren.
"""

from django import template

from uren.kalender import kleur_van as _kleur_van

register = template.Library()


@register.filter
def kleur_van(klus):
    return _kleur_van(klus)
