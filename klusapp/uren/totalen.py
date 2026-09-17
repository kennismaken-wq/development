"""Uren optellen. Losse module omdat drie schermen dezelfde som nodig hebben:
het klusdossier, het overzicht per medewerker (F2) en de export (T3).

Waarom in Python en niet met een database-aggregatie: de duur van een uurblok
staat nergens opgeslagen, hij volgt uit begintijd en eindtijd. Dat verschil
uitrekenen in SQL werkt op Postgres anders dan op SQLite, en wij draaien
lokaal op de een en op de server op de ander. Om zes medewerkers met een paar
honderd blokken per klus is het verschil niet te meten.
"""

from .kalender import als_uren
from .models import Uurblok


def blokken_van(medewerker, begin, eind):
    """De uurblokken van één medewerker in een periode, nieuwste dag onderaan.

    Het canonieke queryset voor het overzicht (F2) en de export (T3): beide
    tellen dezelfde uren op, dus ze horen ook dezelfde blokken op te halen.
    """
    return (
        Uurblok.objects.filter(medewerker=medewerker, datum__range=(begin, eind))
        .select_related("klus", "medewerker")
        .order_by("datum", "begintijd")
    )


def per_klus(blokken):
    """Hoeveel er in deze periode op elke klus is geschreven, meeste uren eerst."""
    verzameld = {}
    for blok in blokken:
        rij = verzameld.setdefault(blok.klus_id, {"klus": blok.klus, "minuten": 0})
        rij["minuten"] += blok.duur_minuten

    rijen = [
        {"klus": rij["klus"], "minuten": rij["minuten"], "uren": als_uren(rij["minuten"])}
        for rij in verzameld.values()
    ]
    rijen.sort(key=lambda rij: (-rij["minuten"], rij["klus"].naam))
    return rijen


def per_dag(blokken):
    """Per dag het totaal, op datum gesorteerd. Dagen zonder uren komen niet
    voor — een overzicht van een maand met twintig lege regels leest slechter
    dan een lijst van de dagen waarop echt gewerkt is."""
    verzameld = {}
    for blok in blokken:
        verzameld[blok.datum] = verzameld.get(blok.datum, 0) + blok.duur_minuten
    return [
        {"datum": datum, "minuten": minuten, "uren": als_uren(minuten)}
        for datum, minuten in sorted(verzameld.items())
    ]


def per_medewerker_op_klus(klus):
    """Wie heeft er op deze klus gewerkt, en hoeveel.

    Contractpunt 4 vraagt "wie op welke klus heeft gewerkt". Er is geen veld
    waarin staat wie aan een klus is toegewezen; dat leiden we af uit de
    geschreven uren. Iemand verschijnt dus pas zodra hij zijn eerste uur heeft
    geschreven, en dat is precies de vraag die hier beantwoord wordt.

    Geeft een lijst van dicts, de meeste uren eerst.
    """
    blokken = klus.uurblokken.select_related("medewerker").all()

    verzameld = {}
    for blok in blokken:
        rij = verzameld.setdefault(
            blok.medewerker_id,
            {"medewerker": blok.medewerker, "minuten": 0, "dagen": set()},
        )
        rij["minuten"] += blok.duur_minuten
        rij["dagen"].add(blok.datum)

    rijen = []
    for rij in verzameld.values():
        rijen.append(
            {
                "medewerker": rij["medewerker"],
                "minuten": rij["minuten"],
                "uren": als_uren(rij["minuten"]),
                "aantal_dagen": len(rij["dagen"]),
                "eerste_dag": min(rij["dagen"]),
                "laatste_dag": max(rij["dagen"]),
            }
        )
    rijen.sort(key=lambda rij: (-rij["minuten"], rij["medewerker"].naam))
    return rijen


def totaal_van(rijen):
    """Het klustotaal, uit wat per_medewerker_op_klus al heeft uitgerekend —
    zodat er niet twee keer door dezelfde blokken wordt gelopen."""
    minuten = sum(rij["minuten"] for rij in rijen)
    return {"minuten": minuten, "uren": als_uren(minuten)}


def totaal_en_week(medewerker, week_begin, week_eind):
    """Voor het startscherm: al-time totaal en het totaal van deze week, in één
    keer door de blokken van een medewerker heen."""
    blokken = Uurblok.objects.filter(medewerker=medewerker).only("datum", "begintijd", "eindtijd")
    totaal_minuten = week_minuten = 0
    for blok in blokken:
        totaal_minuten += blok.duur_minuten
        if week_begin <= blok.datum <= week_eind:
            week_minuten += blok.duur_minuten
    return {"totaal": als_uren(totaal_minuten), "week": als_uren(week_minuten)}
