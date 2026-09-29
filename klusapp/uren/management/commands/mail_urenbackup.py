"""Alle uren als Excel naar Maarten mailen: de off-site back-up van de uren.

Draait wekelijks via `klusapp-urenbackup.timer` op de server (docs/DEPLOY.md).
Het bestand bevat steeds álle uren sinds het begin, niet alleen die van de
afgelopen week. Zo is de laatste mail op zichzelf compleet en werken de
oudere mails als eerdere versies. Het is dezelfde Excel als de urenexport,
dus ook zonder de app te openen en verder te bewerken.

Faalt hard als er geen adres is ingesteld of het versturen mislukt, zodat
systemd de run als mislukt markeert in plaats van stil niets te doen.
"""

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from uren import export
from uren.models import Uurblok

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class Command(BaseCommand):
    help = "Mail alle uren als Excel naar URENBACKUP_ADRES (wekelijkse back-up)."

    def handle(self, *args, **opties):
        adres = settings.URENBACKUP_ADRES
        if not adres:
            raise CommandError("URENBACKUP_ADRES en EMAIL_HOST_USER zijn allebei leeg; zet ze in .env.")

        blokken = list(
            Uurblok.objects.select_related("medewerker", "klus").order_by(
                "medewerker__first_name", "medewerker__last_name", "medewerker__username", "datum", "begintijd"
            )
        )
        vandaag = timezone.localdate()
        boek = export.werkboek_bouwen(blokken, f"Alle uren t-m {vandaag:%d-%m-%Y}")

        mail = EmailMessage(
            subject=f"Back-up urenregistratie {vandaag:%d-%m-%Y}",
            body=(
                "Bijgevoegd: alle uren uit de klusapp tot en met vandaag, als Excel.\n\n"
                "Dit is de wekelijkse back-up. Bewaar deze mails; de nieuwste bevat steeds "
                "alles, de oudere zijn eerdere versies.\n"
            ),
            to=[adres],
        )
        mail.attach(f"uren-back-up-{vandaag:%Y-%m-%d}.xlsx", export.werkboek_als_bytes(boek), XLSX)
        try:
            mail.send()
        except Exception as fout:
            raise CommandError(f"Versturen mislukt: {fout}") from fout

        self.stdout.write(f"Urenback-up verstuurd naar {adres}: {len(blokken)} uurblokken.")
