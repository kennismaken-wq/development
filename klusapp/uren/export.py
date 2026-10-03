"""Uren omzetten naar een Excel-bestand voor de boekhouder.

Maarten wil de uren in Excel aangeleverd krijgen, niet als CSV: de
administratie draait nu op Excel en het bestand moet na het downloaden
gewoon verder te bewerken zijn (antwoord 15-09-2026, zie
docs/VRAGEN-MAARTEN.md). Wat er daarna met de uren gebeurt — omzetten naar
een factuur in Exact Online — is een los vervolg en geen onderdeel van fase 1
(SPEC: "de app maakt geen facturen").

Deze module raakt de database niet, zodat hij los te testen is: hij krijgt
een lijst uurblokken binnen (al gesorteerd op medewerker, dan datum) en geeft
een openpyxl-werkboek terug.
"""

import re
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font

# "Extra werk" als laatste kolom en niet in de toelichting: dat is wat er
# doorbelast moet worden bovenop de offerte, en de administratie moet het in
# één oogopslag kunnen vinden (gesprek Maarten, 01-10-2026).
KOPPEN = ["Medewerker", "Datum", "Klus", "Opdrachtgever", "Adres", "Van", "Tot", "Uren", "Toelichting", "Extra werk"]
KOLOMBREEDTES = [22, 12, 26, 22, 32, 8, 8, 8, 45, 45]
LEGE_REGEL = [""] * len(KOPPEN)


def _vet(blad, rijnummer):
    for cel in blad[rijnummer]:
        cel.font = Font(bold=True)


def _subtotaal_schrijven(blad, naam, minuten):
    blad.append([f"Totaal {naam}", "", "", "", "", "", "", round(minuten / 60, 2), "", ""])
    _vet(blad, blad.max_row)


def _namen_per_medewerker(uurblokken):
    """Naam per medewerker-id, met de gebruikersnaam erachter als twee
    mensen in deze export dezelfde naam hebben: "Kees de Vries (kees2)"."""
    mensen = {blok.medewerker_id: blok.medewerker for blok in uurblokken}
    hoe_vaak = {}
    for persoon in mensen.values():
        hoe_vaak[persoon.naam] = hoe_vaak.get(persoon.naam, 0) + 1
    return {
        pk: f"{persoon.naam} ({persoon.username})" if hoe_vaak[persoon.naam] > 1 else persoon.naam
        for pk, persoon in mensen.items()
    }


def _als_tekst(rij):
    """Tekst die met "=" begint, maakt openpyxl een formule. Een medewerker die
    als werkzaamheden "=3 palen" of erger een =HYPERLINK(...) intikt, zette zo
    een werkende formule in het bestand voor de boekhouder (B8). Gewoon tekst
    van maken."""
    for cel in rij:
        if cel.data_type == "f":
            cel.data_type = "s"


def werkboek_bouwen(uurblokken, bladtitel):
    """Eén werkblad, gegroepeerd per medewerker met een totaalregel erna.

    `uurblokken` moet al gesorteerd zijn op medewerker en dan op datum — die
    volgorde bepaalt hier waar een groep eindigt en de totaalregel komt.
    """
    boek = Workbook()
    blad = boek.active
    # Excel staat geen langere bladnamen toe, en geen / \ : ? * [ ] erin:
    # een klus "Dijkweg 12/14" gaf een foutpagina (stresstest 03-10-2026, B14).
    blad.title = re.sub(r"[\\/:?*\[\]]", "-", bladtitel)[:31].strip() or "Uren"

    blad.append(KOPPEN)
    _vet(blad, 1)
    for kolom, breedte in zip("ABCDEFGHIJ", KOLOMBREEDTES):
        blad.column_dimensions[kolom].width = breedte

    uurblokken = list(uurblokken)
    namen = _namen_per_medewerker(uurblokken)
    huidige_medewerker = None
    subtotaal_minuten = 0
    totaal_minuten = 0

    for blok in uurblokken:
        # Op de medewerker zelf en niet op zijn naam: twee mensen met dezelfde
        # naam (vader en zoon) werden anders één subtotaal (B15).
        naam = namen[blok.medewerker_id]
        if huidige_medewerker is not None and blok.medewerker_id != huidige_medewerker:
            _subtotaal_schrijven(blad, namen[huidige_medewerker], subtotaal_minuten)
            subtotaal_minuten = 0
        huidige_medewerker = blok.medewerker_id

        adres = blok.klus.adres
        if blok.klus.adres and blok.klus.plaats:
            adres += f", {blok.klus.plaats}"
        elif blok.klus.plaats:
            adres = blok.klus.plaats

        blad.append(
            [
                naam,
                blok.datum,
                blok.klus.naam,
                blok.klus.opdrachtgever,
                adres,
                blok.begintijd.strftime("%H:%M"),
                blok.eindtijd.strftime("%H:%M"),
                round(blok.duur_minuten / 60, 2),
                blok.toelichting,
                blok.extra_werk,
            ]
        )
        blad.cell(row=blad.max_row, column=2).number_format = "DD-MM-YYYY"
        _als_tekst(blad[blad.max_row])
        subtotaal_minuten += blok.duur_minuten
        totaal_minuten += blok.duur_minuten

    if huidige_medewerker is None:
        blad.append(["Geen uren geschreven in deze periode."] + LEGE_REGEL[1:])
        return boek

    _subtotaal_schrijven(blad, namen[huidige_medewerker], subtotaal_minuten)
    blad.append(["Totaal alle medewerkers", "", "", "", "", "", "", round(totaal_minuten / 60, 2), "", ""])
    _vet(blad, blad.max_row)
    return boek


def werkboek_als_bytes(boek):
    buffer = BytesIO()
    boek.save(buffer)
    return buffer.getvalue()
