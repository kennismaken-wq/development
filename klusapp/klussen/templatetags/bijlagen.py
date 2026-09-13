"""Zodat de bijlage-partials zelfstandig werken.

`Bijlage.mag_verwijderen()` heeft de ingelogde gebruiker nodig, en een
Django-template kan geen argument aan een methode meegeven. Via dit filter
hoeft wie de partial include't verder niets voor te bereiden.
"""

from django import template

register = template.Library()


@register.filter
def mag_weg(bijlage, gebruiker):
    if not getattr(gebruiker, "is_authenticated", False):
        return False
    return bijlage.mag_verwijderen(gebruiker)
