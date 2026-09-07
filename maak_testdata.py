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
    mw.is_staff = mw.is_superuser = staff
    mw.set_password(wachtwoord)
    mw.save()
    print(("aangemaakt" if nieuw else "bijgewerkt"), username, rol)

zorg_voor("maarten", "Maarten", "Morée", Medewerker.Rol.EIGENAAR, "test1234", staff=True)
zorg_voor("sam", "Sam", "de Wit", Medewerker.Rol.MEDEWERKER, "test1234")
