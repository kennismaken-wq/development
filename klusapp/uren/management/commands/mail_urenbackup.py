"""Alle uren en de aanwezigheid als Excel mailen: de off-site back-up.

Draait wekelijks via `klusapp-urenbackup.timer` op de server (docs/DEPLOY.md).
Wat er in de mail zit staat in uren/backup.py. De ontvangers zijn de adressen
die eigenaren op Mijn profiel invullen.

Faalt hard als er geen adres is ingesteld of het versturen mislukt, zodat
systemd de run als mislukt markeert in plaats van stil niets te doen.
"""

from django.core.management.base import BaseCommand, CommandError

from uren import backup


class Command(BaseCommand):
    help = "Mail alle uren en de aanwezigheid als Excel naar de back-upadressen van de eigenaren."

    def handle(self, *args, **opties):
        adressen = backup.ontvangers()
        if not adressen:
            raise CommandError(
                "Geen back-upadres ingesteld: een eigenaar moet het invullen op Mijn profiel."
            )

        mail = backup.backup_mail(adressen)
        try:
            mail.send()
        except Exception as fout:
            raise CommandError(f"Versturen mislukt: {fout}") from fout

        self.stdout.write(
            f"Back-up verstuurd naar {', '.join(adressen)}: {mail.aantal_uurblokken} uurblokken."
        )
