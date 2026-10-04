"""Bestanden van verwijderde bijlagen van de schijf halen.

    manage.py ruim_bijlagen_op          laat zien wat er weg zou gaan
    manage.py ruim_bijlagen_op --echt   haalt het ook echt weg

Tot 03-10-2026 bleef bij het verwijderen van een foto of document het bestand
op de schijf staan (stresstest B2). Sindsdien gaat het vanzelf mee
(klussen.models._bestanden_van_bijlage_weg); dit ruimt eenmalig op wat er van
daarvoor nog staat: alles onder bijlagen/ en thumbnails/ waar geen bijlage
meer naar wijst.
"""

import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from klussen.models import Bijlage

# Een bestand dat net is geüpload kan op de schijf staan voordat zijn bijlage
# in de database staat; dat is geen wees.
MINIMALE_LEEFTIJD = 60 * 60
# Ontbreekt meer dan dit deel van de bestanden waar de database naar wijst,
# dan horen database en MEDIA_ROOT niet bij elkaar.
MAX_ONTBREKEND = 0.1


class Command(BaseCommand):
    help = "Haal bestanden van verwijderde bijlagen van de schijf."

    def add_arguments(self, parser):
        parser.add_argument("--echt", action="store_true", help="Echt verwijderen in plaats van alleen tonen.")

    def handle(self, *args, echt, **opties):
        wortel = Path(settings.MEDIA_ROOT)
        in_gebruik = set()
        for bestand, thumbnail in Bijlage.objects.values_list("bestand", "thumbnail"):
            in_gebruik.update(naam for naam in (bestand, thumbnail) if naam)

        wezen = []
        op_schijf = set()
        grens = time.time() - MINIMALE_LEEFTIJD
        for map_naam in ("bijlagen", "thumbnails"):
            for pad in sorted((wortel / map_naam).rglob("*")):
                if not pad.is_file():
                    continue
                naam = pad.relative_to(wortel).as_posix()
                op_schijf.add(naam)
                if naam not in in_gebruik and pad.stat().st_mtime < grens:
                    wezen.append(pad)

        database = settings.DATABASES["default"]["NAME"]
        self.stdout.write(f"Database: {database} · media: {wortel}")
        # Vangnet: tegen een lege of verkeerde database (vergeten DATABASE_URL)
        # lijkt elk bestand een wees, en zou --echt alles weggooien.
        if op_schijf and not in_gebruik:
            raise CommandError(
                "Deze database heeft geen enkele bijlage, maar er staan wel bestanden. "
                "Draai je dit tegen de goede database (DATABASE_URL, MEDIA_ROOT)? Er is niets verwijderd."
            )
        # Tweede vangnet: database van de ene omgeving, MEDIA_ROOT van de andere.
        # Dan is in_gebruik wel gevuld, maar staat bijna niets ervan op deze schijf,
        # en zou --echt de foto's van de andere omgeving weggooien.
        ontbrekend = in_gebruik - op_schijf
        if in_gebruik and len(ontbrekend) > MAX_ONTBREKEND * len(in_gebruik):
            raise CommandError(
                f"{len(ontbrekend)} van de {len(in_gebruik)} bestanden waar deze database naar wijst, "
                f"staan niet onder {wortel}. Horen DATABASE_URL en MEDIA_ROOT bij dezelfde omgeving? "
                "Er is niets verwijderd."
            )

        grootte = sum(pad.stat().st_size for pad in wezen)
        for pad in wezen:
            self.stdout.write(str(pad.relative_to(wortel)))
            if echt:
                try:
                    pad.unlink()
                except OSError as fout:
                    self.stderr.write(f"  kon niet weg: {fout}")
        actie = "verwijderd" if echt else "zou weg gaan (draai met --echt)"
        self.stdout.write(f"{len(wezen)} bestanden, {grootte / 1024 / 1024:.1f} MB {actie}.")
