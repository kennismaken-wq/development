"""De notities per klus als gesprek (fase 2): wie hoort bij een klus, hoeveel
berichten heb je gemist, en de melding op je telefoon bij een nieuw bericht.

"Jouw klussen" zijn de klussen waar je de afgelopen tijd mee bezig was of
binnenkort mee bezig bent: ingepland in de werkplanning (Inzet), er uren op
geschreven, of er zelf iets in geschreven. Alleen daar krijg je een teller en
een melding. Meelezen kan op elke klus, net als nu.
"""

import logging
import threading
from datetime import timedelta

from django.db import close_old_connections, transaction
from django.utils import timezone

from medewerkers.models import Medewerker
from uren.models import Inzet, Uurblok

from .models import Notitie, NotitieGelezen

log = logging.getLogger(__name__)

TERUG = timedelta(days=30)  # zo lang na je laatste inzet, uur of bericht hoor je er nog bij
VOORUIT = timedelta(days=60)  # en zo ver vooruit ingepland al


def _mensen_bij(klus_ids=None, medewerker=None):
    """(medewerker_id, klus_id)-paren van wie er bij welke klus hoort."""
    vandaag = timezone.localdate()
    nu = timezone.now()
    inzet = Inzet.objects.filter(datum__range=(vandaag - TERUG, vandaag + VOORUIT))
    uren = Uurblok.objects.filter(datum__gte=vandaag - TERUG)
    berichten = Notitie.objects.filter(geschreven_op__gte=nu - TERUG, geschreven_door__isnull=False)
    if klus_ids is not None:
        inzet, uren, berichten = (q.filter(klus_id__in=klus_ids) for q in (inzet, uren, berichten))
    if medewerker is not None:
        inzet = inzet.filter(medewerker=medewerker)
        uren = uren.filter(medewerker=medewerker)
        berichten = berichten.filter(geschreven_door=medewerker)
    paren = set(inzet.values_list("medewerker_id", "klus_id"))
    paren |= set(uren.values_list("medewerker_id", "klus_id"))
    paren |= set(berichten.values_list("geschreven_door_id", "klus_id"))
    return paren


def betrokkenen(klus):
    """Wie er bij deze klus hoort: actieve, zichtbare medewerkers."""
    ids = {medewerker_id for medewerker_id, _ in _mensen_bij(klus_ids=[klus.pk])}
    return Medewerker.objects.filter(pk__in=ids, is_active=True, uit_dienst_sinds__isnull=True)


def mijn_klus_ids(gebruiker):
    return {klus_id for _, klus_id in _mensen_bij(medewerker=gebruiker)}


def ongelezen_per_klus(gebruiker, klus_ids):
    """{klus_id: aantal} van de notities van anderen die je nog niet zag, voor
    de klussen uit `klus_ids` die bij jou horen. Klussen zonder gemiste
    berichten staan er niet in."""
    klus_ids = set(klus_ids) & mijn_klus_ids(gebruiker)
    if not klus_ids:
        return {}
    gelezen = dict(
        NotitieGelezen.objects.filter(medewerker=gebruiker, klus_id__in=klus_ids).values_list("klus_id", "tijdstip")
    )
    tellers = {}
    for klus_id, geschreven_op in (
        Notitie.objects.filter(klus_id__in=klus_ids).exclude(geschreven_door=gebruiker).values_list("klus_id", "geschreven_op")
    ):
        grens = gelezen.get(klus_id)
        if grens is None or geschreven_op > grens:
            tellers[klus_id] = tellers.get(klus_id, 0) + 1
    return tellers


def zet_tellers(gebruiker, klussen):
    """Zet `klus.ongelezen` op elke klus uit de lijst, voor het groene rondje."""
    tellers = ongelezen_per_klus(gebruiker, [klus.pk for klus in klussen])
    for klus in klussen:
        klus.ongelezen = tellers.get(klus.pk, 0)


def markeer_gelezen(gebruiker, klus):
    NotitieGelezen.objects.update_or_create(klus=klus, medewerker=gebruiker, defaults={"tijdstip": timezone.now()})


def _melding_tekst(notitie, aantal_fotos):
    tekst = " ".join(notitie.tekst.split())
    if len(tekst) > 140:
        tekst = tekst[:139] + "…"
    if aantal_fotos:
        foto = "📷 foto" if aantal_fotos == 1 else f"📷 {aantal_fotos} foto's"
        tekst = f"{tekst} · {foto}" if tekst else foto
    return tekst


def meld(notitie_pk):
    """Stuur de melding naar de telefoons van iedereen die bij de klus hoort,
    behalve de schrijver. Draait in een eigen thread (zie plan_melding)."""
    from pushberichten import versturen
    from pushberichten.models import Abonnement

    close_old_connections()
    try:
        notitie = Notitie.objects.select_related("klus", "geschreven_door").filter(pk=notitie_pk).first()
        if notitie is None:  # binnen een tel weer weggehaald
            return 0
        ontvangers = betrokkenen(notitie.klus).exclude(pk=notitie.geschreven_door_id)
        schrijver = notitie.geschreven_door
        titel = f"{schrijver.first_name or schrijver.naam} · {notitie.klus.naam}" if schrijver else notitie.klus.naam
        tekst = _melding_tekst(notitie, notitie.fotos.count())
        url = f"{notitie.klus.get_absolute_url()}#notities"
        verstuurd = 0
        for abonnement in Abonnement.objects.filter(medewerker__in=ontvangers):
            verstuurd += bool(versturen.stuur(abonnement, titel, tekst, url))
        return verstuurd
    except Exception:  # een melding mag nooit het bericht zelf laten mislukken
        log.exception("Melding bij notitie %s mislukt", notitie_pk)
        return 0
    finally:
        close_old_connections()


def plan_melding(notitie):
    """Na het opslaan, buiten het verzoek om: Apple en Google kunnen traag
    zijn, en wie op Plaatsen tikt hoeft daar niet op te wachten."""
    pk = notitie.pk
    transaction.on_commit(lambda: threading.Thread(target=meld, args=(pk,), daemon=True).start())
