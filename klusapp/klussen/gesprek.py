"""De notities per klus als gesprek (fase 2): wie hoort bij een klus, hoeveel
berichten heb je gemist, en de melding op je telefoon bij een nieuw bericht.

"Jouw klussen" zijn de klussen waar je de afgelopen tijd mee bezig was of
binnenkort mee bezig bent: ingepland in de werkplanning (Inzet), er uren op
geschreven, of er zelf iets in geschreven. Alleen daar krijg je een teller en
een melding. Meelezen kan op elke klus, net als nu.

Ook de eigenaar krijgt alleen meldingen van klussen waar hij bij betrokken is,
niet van alles (besluit Thijmen 17-11-2026, docs/VRAGEN-MAARTEN.md vraag 11).
Wie een klus wil volgen, tikt op "Meedoen met klus".
"""

import logging
import threading
from datetime import timedelta

from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.models import Count, F, OuterRef, Q, Subquery
from django.urls import reverse
from django.utils import timezone

from medewerkers.models import Medewerker
from uren.models import Inzet, Uurblok

from .models import Klus, Notitie, NotitieGelezen

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
    # En wie de eigenaar zelf bij de klus heeft gezet (Klus.betrokkenen).
    gekozen = Klus.betrokkenen.through.objects.all()
    if klus_ids is not None:
        gekozen = gekozen.filter(klus_id__in=klus_ids)
    if medewerker is not None:
        gekozen = gekozen.filter(medewerker=medewerker)
    paren |= set(gekozen.values_list("medewerker_id", "klus_id"))
    return paren


def betrokkenen(klus):
    """Wie er bij deze klus hoort: actieve, zichtbare medewerkers."""
    ids = {medewerker_id for medewerker_id, _ in _mensen_bij(klus_ids=[klus.pk])}
    return Medewerker.objects.filter(pk__in=ids, is_active=True, uit_dienst_sinds__isnull=True)


def zichtbare_betrokkenen(klus):
    """Wie er bij Betrokken in beeld staat: precies wie de meldingen van de
    chat krijgt (betrokkenen hierboven: gekozen, meegedaan, ingepland, uren
    of zelf geschreven). Zonder het verborgen beheeraccount en zonder
    oud-collega's (stresstest 17-11-2026)."""
    from django.db.models.functions import Lower

    return list(betrokkenen(klus).order_by(Lower("first_name"), Lower("last_name")))


def mijn_klus_ids(gebruiker):
    return {klus_id for _, klus_id in _mensen_bij(medewerker=gebruiker)}


def ongelezen_per_klus(gebruiker, klus_ids):
    """{klus_id: aantal} van de notities van anderen die je nog niet zag, voor
    de klussen uit `klus_ids` die bij jou horen. Klussen zonder gemiste
    berichten staan er niet in."""
    klus_ids = set(klus_ids) & mijn_klus_ids(gebruiker)
    if not klus_ids:
        return {}
    # Wie de chat van een klus nog nooit opende (net ingepland op een oude
    # klus, nieuw in dienst), telt alleen de berichten van de laatste TERUG
    # dagen, niet de hele geschiedenis. Ouder dan dat telt nooit: het rondje
    # toont boven de 9 toch "9+" (stresstest 17-11-2026).
    # Eén query met GROUP BY, in de database geteld (stresstest 17-11-2026:
    # eerst kwam er een rij per bericht naar Python).
    ondergrens = timezone.now() - TERUG
    grens = NotitieGelezen.objects.filter(klus=OuterRef("klus_id"), medewerker=gebruiker).values("tijdstip")[:1]
    rijen = (
        Notitie.objects.filter(klus_id__in=klus_ids, geschreven_op__gte=ondergrens)
        .exclude(geschreven_door=gebruiker)
        .annotate(grens=Subquery(grens))
        .filter(Q(grens__isnull=True) | Q(geschreven_op__gt=F("grens")))
        .order_by()
        .values("klus_id")
        .annotate(aantal=Count("pk"))
    )
    return {rij["klus_id"]: rij["aantal"] for rij in rijen}


def zet_tellers(gebruiker, klussen):
    """Zet `klus.ongelezen` op elke klus uit de lijst, voor het groene rondje."""
    tellers = ongelezen_per_klus(gebruiker, [klus.pk for klus in klussen])
    for klus in klussen:
        klus.ongelezen = tellers.get(klus.pk, 0)


def markeer_gelezen(request, klus, tot):
    """De chat is bekeken, tot en met het bericht met geschreven_op `tot`
    (het laatste dat op het scherm staat). Schuift alleen vooruit, en
    schrijft niets als er niets nieuws gezien is: de chat vraagt elke paar
    seconden om nieuwe berichten. Niet als de eigenaar meekijkt als
    medewerker (TESTFUNCTIES): dan zou hij het rondje van die medewerker
    wissen."""
    from medewerkers.views import SESSIE_WISSEL

    if SESSIE_WISSEL in request.session:
        return
    bijgewerkt = NotitieGelezen.objects.filter(klus=klus, medewerker=request.user, tijdstip__lt=tot).update(tijdstip=tot)
    if bijgewerkt or NotitieGelezen.objects.filter(klus=klus, medewerker=request.user).exists():
        return
    try:
        with transaction.atomic():
            NotitieGelezen.objects.create(klus=klus, medewerker=request.user, tijdstip=tot)
    except IntegrityError:
        # Twee tabs tegelijk maakten de rij; de ander heeft hem al gezet.
        NotitieGelezen.objects.filter(klus=klus, medewerker=request.user, tijdstip__lt=tot).update(tijdstip=tot)


def schrijversnaam(medewerker):
    """Voornaam, en nooit de gebruikersnaam (die is een inlognaam)."""
    if medewerker is None:
        return "Iemand"
    return medewerker.first_name or medewerker.last_name or "Collega"


def voorbereid(berichten, gebruiker, vorige=None):
    """Zet op elk bericht wat de chat nodig heeft om het als WhatsApp te
    tonen: van jou of niet, een datumkop als er een nieuwe dag begint, en of
    het aan het vorige bericht van dezelfde persoon vastzit (dan geen naam
    en rondje opnieuw). `vorige` is het laatste bericht dat al op het
    scherm staat, bij het bijladen."""
    berichten = list(berichten)
    vandaag = timezone.localdate()
    for bericht in berichten:
        dag = timezone.localdate(bericht.geschreven_op)
        bericht.eigen = bericht.geschreven_door_id == gebruiker.pk
        bericht.dag = dag
        bericht.nieuwe_dag = vorige is None or timezone.localdate(vorige.geschreven_op) != dag
        bericht.doorloop = (
            not bericht.nieuwe_dag
            and vorige is not None
            and vorige.geschreven_door_id == bericht.geschreven_door_id
            and (bericht.geschreven_op - vorige.geschreven_op) < timedelta(minutes=10)
        )
        if dag == vandaag:
            bericht.dagnaam = "Vandaag"
        elif dag == vandaag - timedelta(days=1):
            bericht.dagnaam = "Gisteren"
        else:
            bericht.dagnaam = None
        bericht.naam = schrijversnaam(bericht.geschreven_door)
        vorige = bericht
    return berichten


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
        titel = f"{schrijversnaam(notitie.geschreven_door)} · {notitie.klus.naam}"
        tekst = _melding_tekst(notitie, notitie.fotos.count())
        url = reverse("klus_chat", args=[notitie.klus_id])
        verstuurd = 0
        for abonnement in Abonnement.objects.filter(medewerker__in=ontvangers):
            verstuurd += bool(versturen.stuur(abonnement, titel, tekst, url, tag=f"klus-{notitie.klus_id}", ttl=86400))
        return verstuurd
    except Exception:  # een melding mag nooit het bericht zelf laten mislukken
        log.exception("Melding bij notitie %s mislukt", notitie_pk)
        return 0
    finally:
        # Deze thread heeft zijn eigen verbinding; met CONN_MAX_AGE sluit
        # close_old_connections die niet, dus hier expliciet dicht. (Niet
        # binnen een transactie: dan draaien we in een test, niet in een thread.)
        if not connection.in_atomic_block:
            connection.close()


def plan_melding(notitie):
    """Na het opslaan, buiten het verzoek om: Apple en Google kunnen traag
    zijn, en wie op Plaatsen tikt hoeft daar niet op te wachten."""
    pk = notitie.pk
    transaction.on_commit(lambda: threading.Thread(target=meld, args=(pk,), daemon=True).start())
