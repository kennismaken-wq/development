"""Rekenwerk voor de dag/week-kalender en de maandweergave.

De kalender loopt van 06:00 tot 20:00 in vakken van een half uur van 26
pixels hoog — dezelfde maten als in de demo. Een blok wordt absoluut
geplaatst binnen zijn dagkolom, dus alles wat hier wordt uitgerekend is
"hoeveel pixels vanaf de bovenkant" en "hoe hoog". Dat werkt per dag, dus
zowel de dag- als de weekweergave in uren/views.py hergebruiken het
ongewijzigd — alleen het aantal kolommen verschilt.
"""

import calendar

START_MIN = 6 * 60
EIND_MIN = 20 * 60
VAK_MIN = 30
RIJ_H = 26
VAK_AANTAL = (EIND_MIN - START_MIN) // VAK_MIN

# Klussen krijgen een vaste kleur zolang er in het beheer geen kleur is
# gekozen; de kleur draagt op een smal scherm de herkenning, niet de tekst.
PALET = ["#95BF1D", "#5B8FA8", "#E07B5F", "#C9A227", "#7FA88F", "#A5806A"]


def minuten(tijdstip):
    return tijdstip.hour * 60 + tijdstip.minute


def als_uren(totaal_minuten):
    return f"{totaal_minuten // 60}:{totaal_minuten % 60:02d}"


def als_decimaal(totaal_minuten):
    """Uren als getal in plaats van als klok: 8, 8,5, 3,25.

    Op het planbord staat naast elke klusnaam hoeveel uur eraan is gewerkt.
    "8,5" leest daar sneller dan "8:30", dat je makkelijk voor een tijdstip
    aanziet in een rooster vol begintijden.
    """
    uren = totaal_minuten / 60
    tekst = f"{uren:.2f}".rstrip("0").rstrip(".")
    return tekst.replace(".", ",")


def kleur_van(klus):
    return klus.kleur or PALET[(klus.pk - 1) % len(PALET)]


def raster_hoogte():
    return VAK_AANTAL * RIJ_H


def vakken():
    """De klikbare halfuurvakken van één dagkolom."""
    return [{"index": s, "uurlijn": s % 2 == 0} for s in range(VAK_AANTAL)]


def uurlabels():
    """De tijden in de linkerkolom, elk heel uur één."""
    labels = []
    for s in range(0, VAK_AANTAL + 1, 2):
        minuut = START_MIN + s * VAK_MIN
        labels.append({"top": s * RIJ_H, "tekst": f"{minuut // 60:02d}:{minuut % 60:02d}"})
    return labels


def plaats_blokken(blokken):
    """Zet uurblokken om in iets wat de template direct kan tekenen.

    Blokken die elkaar overlappen delen de breedte van de kolom, zodat er
    geen een onzichtbaar achter een ander verdwijnt.
    """
    getekend = []
    for blok in blokken:
        begin, eind = minuten(blok.begintijd), minuten(blok.eindtijd)
        # Buiten de kalendertijden gewerkt? Dan tekenen we de rand ervan,
        # zodat het blok zichtbaar blijft in plaats van weg te vallen.
        zichtbaar_begin = max(begin, START_MIN)
        zichtbaar_eind = min(eind, EIND_MIN)
        if zichtbaar_eind <= zichtbaar_begin:
            continue

        overlappend = [
            ander
            for ander in blokken
            if minuten(ander.begintijd) < eind and minuten(ander.eindtijd) > begin
        ]
        breedte = 100 / len(overlappend)
        positie = overlappend.index(blok)

        # Als tekst, en afgerond: een float wordt in het Nederlands met een
        # komma weergegeven en dan begrijpt de browser de stijlregel niet.
        getekend.append(
            {
                "blok": blok,
                "top": round((zichtbaar_begin - START_MIN) / VAK_MIN * RIJ_H),
                "hoogte": round(max((zichtbaar_eind - zichtbaar_begin) / VAK_MIN * RIJ_H - 2, 18)),
                "links": f"{positie * breedte:.4f}",
                "breedte": f"{breedte:.4f}",
                "kleur": kleur_van(blok.klus),
            }
        )
    return getekend


def tijd_van_vak(index):
    """Van vaknummer naar 'HH:MM', voor de links naar het formulier."""
    minuut = START_MIN + index * VAK_MIN
    return f"{minuut // 60:02d}:{minuut % 60:02d}"


def maandraster(jaar, maand):
    """Weken (ma-zo) die de maand vullen, incl. dagen uit de vorige/volgende
    maand zodat elke week compleet is — zoals een gewone kalender."""
    dagen = list(calendar.Calendar(firstweekday=0).itermonthdates(jaar, maand))
    return [dagen[i : i + 7] for i in range(0, len(dagen), 7)]
