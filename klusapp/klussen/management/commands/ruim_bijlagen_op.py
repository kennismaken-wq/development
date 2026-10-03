"""Bestanden van verwijderde bijlagen van de schijf halen.

    manage.py ruim_bijlagen_op          laat zien wat er weg zou gaan
    manage.py ruim_bijlagen_op --echt   haalt het ook echt weg

Tot 03-10-2026 bleef bij het verwijderen van een foto of document het bestand
op de schijf staan (stresstest B2). Sindsdien gaat het vanzelf mee
(klussen.models._bestanden_van_bijlage_weg); dit ruimt eenmalig op wat er van
daarvoor nog staat: alles onder bijlagen/ en thumbnails/ waar geen bijlage
meer naar wijst.
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from klussen.models import Bijlage


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
        for map_naam in ("bijlagen", "thumbnails"):
            for pad in sorted((wortel / map_naam).rglob("*")):
                if pad.is_file() and pad.relative_to(wortel).as_posix() not in in_gebruik:
                    wezen.append(pad)

        grootte = sum(pad.stat().st_size for pad in wezen)
        for pad in wezen:
            self.stdout.write(str(pad.relative_to(wortel)))
            if echt:
                pad.unlink()
        actie = "verwijderd" if echt else "zou weg gaan (draai met --echt)"
        self.stdout.write(f"{len(wezen)} bestanden, {grootte / 1024 / 1024:.1f} MB {actie}.")
