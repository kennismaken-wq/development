"""Een voorbeeldplaatje van een PDF, net als bij foto's.

Alleen de eerste pagina: een tekening of offerte is vrijwel altijd één
pagina, en de documentenlijst hoeft niet meer te tonen dan een voorbeeld om
te herkennen welk bestand het is — net als het bijlage-icoontje in WhatsApp.

Deze module raakt de database niet, zodat hij los te testen is (zie
afbeeldingen.py, waar dezelfde opzet voor foto's staat).
"""

from pathlib import Path

import pymupdf
from django.core.files.base import ContentFile

from .afbeeldingen import KWALITEIT, THUMB_ZIJDE

PDF_SUFFIX = ".pdf"


def lijkt_pdf(bestandsnaam):
    return Path(bestandsnaam).suffix.lower() == PDF_SUFFIX


def thumbnail_van(bestand, bestandsnaam):
    """Geef een JPEG-thumbnail van de eerste pagina, of None.

    None komt voor bij een bestand dat geen PDF is, een PDF met een
    wachtwoord erop, of een PDF die MuPDF niet kan lezen — de aanroeper
    slaat het document dan gewoon op zonder thumbnail, precies zoals een
    document er tot nu toe altijd uitzag.
    """
    if not lijkt_pdf(bestandsnaam):
        return None

    bestand.seek(0)
    try:
        with pymupdf.open(stream=bestand.read(), filetype="pdf") as document:
            if document.needs_pass or document.page_count == 0:
                return None
            pagina = document.load_page(0)
            lange_zijde = max(pagina.rect.width, pagina.rect.height) or 1
            zoom = THUMB_ZIJDE / lange_zijde
            pixmap = pagina.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
            return ContentFile(pixmap.tobytes("jpeg", jpg_quality=KWALITEIT))
    except pymupdf.FileDataError:
        return None
