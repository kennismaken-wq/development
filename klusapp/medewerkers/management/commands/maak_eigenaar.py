"""Een eigenaarsaccount aanmaken op een lege omgeving, zonder dat wij zijn
wachtwoord ooit kennen.

    manage.py maak_eigenaar maarten maarten@voorbeeld.nl --voornaam Maarten

Het account krijgt een willekeurig wachtwoord dat nergens getoond wordt. De
eigenaar kiest daarna zelf een wachtwoord via "Wachtwoord vergeten" op de
inlogpagina; daarvoor moet de mail op de server werken (docs/DEPLOY.md).
Geen "onbruikbaar" wachtwoord: Django stuurt aan zo'n account geen resetmail.
"""

import secrets

from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from medewerkers.models import Medewerker


class Command(BaseCommand):
    help = "Maak een eigenaarsaccount met een willekeurig wachtwoord; reset daarna via de mail."

    def add_arguments(self, parser):
        parser.add_argument("gebruikersnaam")
        parser.add_argument("email")
        parser.add_argument("--voornaam", default="")
        parser.add_argument("--achternaam", default="")

    def handle(self, *args, gebruikersnaam, email, voornaam, achternaam, **opties):
        try:
            validate_email(email)
        except ValidationError:
            raise CommandError(f"Geen geldig e-mailadres: {email}")
        if Medewerker.objects.filter(username=gebruikersnaam).exists():
            raise CommandError(f"Er is al een account '{gebruikersnaam}'.")

        Medewerker.objects.create_user(
            gebruikersnaam,
            email=email,
            password=secrets.token_urlsafe(32),
            first_name=voornaam,
            last_name=achternaam,
            rol=Medewerker.Rol.EIGENAAR,
            # Ook de back-up gaat dan meteen naar hem; aan te passen op Mijn profiel.
            backup_email=email,
        )
        self.stdout.write(
            f"Eigenaar '{gebruikersnaam}' aangemaakt. Laat hem 'Wachtwoord vergeten' "
            f"gebruiken met {email} om zelf een wachtwoord te kiezen."
        )
