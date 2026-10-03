"""Inloggen zonder op hoofdletters te letten.

Een medewerker krijgt zijn gebruikersnaam mondeling of op een briefje, en
typt dan "Kees" terwijl het account "kees" heet. Dat gaf "gebruikersnaam of
wachtwoord klopt niet" (stresstest 03-10-2026, B11). Nieuwe namen die alleen
in hoofdletters van een bestaande verschillen, weigert MedewerkerForm; voor
de zekerheid wint een exacte match als er toch twee zijn.
"""

from django.contrib.auth.backends import ModelBackend

from .models import Medewerker


class HoofdletterongevoeligInloggen(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username:
            exact = Medewerker.alle.filter(username=username).first()
            if exact is None:
                kandidaten = list(Medewerker.alle.filter(username__iexact=username)[:2])
                if len(kandidaten) == 1:
                    username = kandidaten[0].username
        return super().authenticate(request, username=username, password=password, **kwargs)
