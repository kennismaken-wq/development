"""Welke bestanden er in een klusdossier mogen, en welke de browser zelf mag
tonen.

Twee lijsten, en ze zijn bewust kort. De `accept` op het uploadveld
(forms.MeerdereBestandenVeld.TOEGESTAAN) is alleen een hint aan de telefoon;
een nagemaakt formulier stuurt wat het wil. Zonder controle hier kon een
medewerker een .html- of .svg-bestand met een script als "document" bij een
klus zetten, dat de app daarna als pagina van zichzelf uitleverde: wie het
opende, draaide dat script met zijn eigen account (stresstest 03-10-2026, B12).
"""

from pathlib import Path

from .afbeeldingen import AFBEELDING_SUFFIXEN, NIET_ONDERSTEUNDE_SUFFIXEN

DOCUMENT_SUFFIXEN = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".txt"}

TOEGESTANE_SUFFIXEN = AFBEELDING_SUFFIXEN | NIET_ONDERSTEUNDE_SUFFIXEN | DOCUMENT_SUFFIXEN

# Wat media_bestand "inline" mag uitleveren, dus wat de browser zelf opent:
# foto's en pdf's. Al het andere (Word, Excel, txt, en wat er van vóór deze
# controle nog staat) gaat als download de deur uit, zodat de browser het
# nooit als webpagina van deze site behandelt. Geen .svg: dat is een
# afbeelding waar script in kan.
INLINE_SUFFIXEN = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf"}

WEIGERTEKST = "dit soort bestand kan hier niet bij. Wel: foto's, pdf, Word, Excel en tekst."


def suffix(naam):
    return Path(naam).suffix.lower()


def toegestaan(naam):
    return suffix(naam) in TOEGESTANE_SUFFIXEN


def inline(naam):
    return suffix(naam) in INLINE_SUFFIXEN
