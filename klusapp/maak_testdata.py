"""Lokale testgebruikers. Alleen voor ontwikkelen; niet op de server draaien."""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from medewerkers.models import Medewerker  # noqa: E402

def zorg_voor(username, voornaam, achternaam, rol, wachtwoord, staff=False):
    mw, nieuw = Medewerker.objects.get_or_create(
        username=username,
        defaults={"first_name": voornaam, "last_name": achternaam, "rol": rol},
    )
    mw.first_name, mw.last_name, mw.rol = voornaam, achternaam, rol
    # is_staff volgt automatisch uit de rol; zie Medewerker.save()
    mw.is_superuser = staff
    mw.set_password(wachtwoord)
    mw.save()
    print(("aangemaakt" if nieuw else "bijgewerkt"), username, rol)

# Een eigenaar komt voorlopig ook in /beheer/; zie Medewerker.save().
zorg_voor("maarten", "Maarten", "Morée", Medewerker.Rol.EIGENAAR, "test1234")
zorg_voor("sam", "Sam", "de Wit", Medewerker.Rol.MEDEWERKER, "test1234")

from klussen.models import Klus  # noqa: E402

for naam, soort, plaats in [
    ("Tuin Vermeer", Klus.Soort.AANLEG, "Maasdijk"),
    ("Nieuwbouw Van Dijk", Klus.Soort.AANLEG, "Naaldwijk"),
    ("Onderhoud vaste klanten", Klus.Soort.ONDERHOUD, ""),
]:
    klus, nieuw = Klus.objects.get_or_create(naam=naam, defaults={"soort": soort, "plaats": plaats})
    print(("aangemaakt" if nieuw else "bestond al"), klus)
