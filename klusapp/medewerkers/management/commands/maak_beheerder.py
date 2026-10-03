"""Het verborgen HandigerAI-account op een omgeving zetten.

    manage.py maak_beheerder admin

Vraagt twee keer om een wachtwoord (niet zichtbaar tijdens het typen). Het
account is eigenaar en superuser, dus het ziet alles en komt in /beheer/,
maar het staat in geen enkele lijst, telling of rooster (Medewerker.verborgen).
Let op: wat je ermee invoert, zoals uren, is wel gewoon echte data.
"""

from getpass import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from medewerkers.models import Medewerker


class Command(BaseCommand):
    help = "Maak het verborgen HandigerAI-beheeraccount aan."

    def add_arguments(self, parser):
        parser.add_argument("gebruikersnaam")
        parser.add_argument("--email", default="kennismaken@handigerai.nl")

    def handle(self, *args, gebruikersnaam, email, **opties):
        if Medewerker.alle.filter(username__iexact=gebruikersnaam).exists():
            raise CommandError(f"Er is al een account '{gebruikersnaam}'.")

        wachtwoord = getpass("Wachtwoord: ")
        if wachtwoord != getpass("Nog een keer: "):
            raise CommandError("De twee wachtwoorden zijn niet gelijk.")
        try:
            validate_password(wachtwoord)
        except ValidationError as fout:
            raise CommandError(" ".join(fout.messages))

        beheerder = Medewerker(
            username=gebruikersnaam,
            email=email,
            first_name="HandigerAI",
            rol=Medewerker.Rol.EIGENAAR,
            is_superuser=True,
            verborgen=True,
        )
        beheerder.set_password(wachtwoord)
        beheerder.save()
        self.stdout.write(f"Verborgen beheeraccount '{gebruikersnaam}' aangemaakt.")
