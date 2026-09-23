"""Uren optellen. Losse module omdat meerdere schermen dezelfde som nodig hebben:
het klusdossier en de export (T3).

Waarom in Python en niet met een database-aggregatie: de duur van een uurblok
staat nergens opgeslagen, hij volgt uit begintijd en eindtijd. Dat verschil
uitrekenen in SQL werkt op Postgres anders dan op SQLite, en wij draaien
lokaal op de een en op de server op de ander. Om zes medewerkers met een paar
honderd blokken per klus is het verschil niet te meten.
"""

from .kalender import als_uren, maandraster
from .models import Uurblok


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


def maand_per_dag(medewerker, eerste_van_maand):
    """Minuten per dag voor de weken (ma-zo) die deze maand vullen.

    Twee schermen tekenen dezelfde maand: het maandoverzicht in Mijn uren en
    de widget bovenaan het startscherm. Wat ze ermee doen verschilt, de som
    eronder niet — die staat daarom hier.

    Geeft (weken, minuten_per_dag); de weken bevatten ook de rand-dagen uit de
    vorige en volgende maand, zodat elke week compleet is.
    """
    weken = maandraster(eerste_van_maand.year, eerste_van_maand.month)
    blokken = Uurblok.objects.filter(
        medewerker=medewerker, datum__range=(weken[0][0], weken[-1][-1])
    ).only("datum", "begintijd", "eindtijd")

    minuten_per_dag = {}
    for blok in blokken:
        minuten_per_dag[blok.datum] = minuten_per_dag.get(blok.datum, 0) + blok.duur_minuten
    return weken, minuten_per_dag


# Vier tinten plus leeg, net als een bijdragenkalender. Meer tinten leest niet
# beter op de breedte van een telefoon, minder laat een halve dag en een
# volle dag op elkaar lijken.
HEATMAP_TINTEN = 4


def maand_heatmap(medewerker, vandaag):
    """De maandwidget op het startscherm: elke dag als vakje met een tint van
    0 t/m HEATMAP_TINTEN, plus het totaal van de maand zelf.

    De tint is relatief aan de drukste dag van diezelfde maand en niet aan een
    vast aantal uur: wie zes uur per dag werkt hoort een net zo gevulde maand
    te zien als wie er tien maakt. Bij een lege maand is er niets om aan te
    ijken en blijft alles op 0 staan.
    """
    eerste_van_maand = vandaag.replace(day=1)
    weken, minuten_per_dag = maand_per_dag(medewerker, eerste_van_maand)

    def hoort_bij_maand(datum):
        return (datum.year, datum.month) == (eerste_van_maand.year, eerste_van_maand.month)

    deze_maand = {d: m for d, m in minuten_per_dag.items() if hoort_bij_maand(d)}
    drukste = max(deze_maand.values(), default=0)

    def cel(datum):
        minuten = minuten_per_dag.get(datum, 0)
        if minuten and drukste:
            # -1 zodat de drukste dag zelf precies op de bovenste tint uitkomt
            # in plaats van er net overheen te schieten.
            tint = 1 + (minuten - 1) * HEATMAP_TINTEN // drukste
        else:
            tint = 0
        return {
            "datum": datum,
            "in_maand": hoort_bij_maand(datum),
            "is_vandaag": datum == vandaag,
            "tint": min(tint, HEATMAP_TINTEN),
            "uren": als_uren(minuten) if minuten else None,
        }

    return {
        "maand": eerste_van_maand,
        "weken": [[cel(datum) for datum in week] for week in weken],
        "totaal": als_uren(sum(deze_maand.values())),
        "tinten": range(HEATMAP_TINTEN + 1),
    }
