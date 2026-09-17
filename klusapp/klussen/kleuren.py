"""Automatische kleurtoewijzing voor een nieuwe klus.

Een klus krijgt bij aanmaken een kleur uit uren.kalender.PALET — hetzelfde
palet dat het planbord gebruikt (SPEC §5: de kleur draagt de klusidentiteit).
Welke kleur, bepaalt deze module: een kleur die geen actieve klus en geen
onlangs afgeronde klus al draagt, zodat twee klussen die tegelijk op het bord
kunnen staan niet in dezelfde kleur getekend worden.
"""

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from uren.kalender import PALET

from .models import Klus

# Hoe lang een kleur van een afgeronde klus nog "bezet" blijft, zodat een net
# opgeleverde tuin niet meteen dezelfde kleur krijgt als de volgende klus.
RECENT_AFGEROND_DAGEN = 30


def volgende_kleur():
    vandaag = timezone.localdate()
    in_gebruik = list(
        Klus.objects.filter(
            Q(actief=True) | Q(afgerond_op__gte=vandaag - timedelta(days=RECENT_AFGEROND_DAGEN))
        )
        .exclude(kleur="")
        .values_list("kleur", flat=True)
    )
    for kleur in PALET:
        if kleur not in in_gebruik:
            return kleur
    # Palet op (meer actieve klussen dan kleuren, bijvoorbeeld bij veel
    # onderhoudsklanten): kies de kleur die het minst vaak voorkomt, zodat de
    # botsing zo klein mogelijk blijft in plaats van alles op één kleur te stapelen.
    return min(PALET, key=in_gebruik.count)
