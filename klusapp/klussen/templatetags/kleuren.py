"""Dezelfde kleur tonen als het planbord, ook buiten uren/.

uren.kalender.kleur_van() is de bestaande bron van waarheid voor "welke kleur
hoort bij deze klus" (inclusief de terugvalkleur voor het zeldzame geval dat
kleur toch leeg is). Klussenlijst en klusdossier zijn geen onderdeel van
uren/, maar moeten wel dezelfde kleur laten zien — vandaar dit filter in
plaats van de functie los te dupliceren. medewerker_kleur is hetzelfde
verhaal, nu voor het avatarrondje van een medewerker (bijv. medewerkerslijst).
"""

from django import template

from uren.kalender import kleur_van as _kleur_van
from uren.kalender import medewerker_kleur_van as _medewerker_kleur_van

register = template.Library()


@register.filter
def kleur_van(klus):
    return _kleur_van(klus)


@register.filter
def medewerker_kleur(medewerker):
    return _medewerker_kleur_van(medewerker)
