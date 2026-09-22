"""Telefoonfoto's klaarmaken voor opslag.

Een ruwe foto uit een telefoon is 3 tot 8 MB. Zes medewerkers die een jaar lang
elke klus fotograferen zitten daarmee richting tientallen gigabytes, terwijl
niemand ooit naar die pixels kijkt: de foto's worden bekeken op een telefoon en
in een raster. Daarom bewaren we het origineel niet — alleen een verkleinde
versie en een thumbnail.

Deze module raakt de database niet, zodat hij los te testen is.
"""

from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

# Lange zijde. 2000px is ruim genoeg om op een laptopscherm schermvullend te
# bekijken en in te zoomen op een detail van de bestrating.
MAX_ZIJDE = 2000
THUMB_ZIJDE = 400
KWALITEIT = 82

AFBEELDING_SUFFIXEN = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff"}

# HEIC is het standaardformaat van een iPhone. Pillow kan het niet zonder
# losse plugin. In de praktijk zet iOS een HEIC om naar JPEG zodra je hem via
# een gewoon <input type=file> uploadt, dus dit is een vangnet en geen hoofdpad —
# maar een 500 met een stacktrace is geen vangnet.
NIET_ONDERSTEUNDE_SUFFIXEN = {".heic", ".heif"}


class BestandNietLeesbaar(Exception):
    """Geüpload bestand ziet eruit als een afbeelding maar is niet te openen."""


def lijkt_afbeelding(bestandsnaam):
    return Path(bestandsnaam).suffix.lower() in AFBEELDING_SUFFIXEN


def is_niet_ondersteund(bestandsnaam):
    return Path(bestandsnaam).suffix.lower() in NIET_ONDERSTEUNDE_SUFFIXEN


def _plat_en_gedraaid(afbeelding):
    """Zet de foto rechtop en maak er een ondoorzichtige RGB-versie van."""
    # Een telefoon slaat staande foto's liggend op, met een EXIF-vlag erbij die
    # zegt hoe je hem moet draaien. Wie die vlag negeert krijgt een raster vol
    # gekantelde tuinen. exif_transpose draait de pixels én haalt de vlag weg.
    rechtop = ImageOps.exif_transpose(afbeelding) or afbeelding

    if rechtop.mode == "RGB":
        return rechtop
    # PNG's met transparantie worden zwart als je ze zomaar naar JPEG schrijft;
    # daarom eerst op wit plakken.
    if "A" in rechtop.getbands():
        wit = Image.new("RGB", rechtop.size, (255, 255, 255))
        wit.paste(rechtop.convert("RGBA"), mask=rechtop.convert("RGBA").getchannel("A"))
        return wit
    return rechtop.convert("RGB")


def _als_jpeg(afbeelding, max_zijde):
    kopie = afbeelding.copy()
    kopie.thumbnail((max_zijde, max_zijde), Image.LANCZOS)
    buffer = BytesIO()
    # exif=b"" is opzet: in de EXIF van een telefoonfoto zitten GPS-coördinaten,
    # en dat is het woonadres van de klant. Dat hoort niet in een bestand dat
    # gedownload en doorgestuurd kan worden.
    kopie.save(buffer, format="JPEG", quality=KWALITEIT, optimize=True, exif=b"")
    return ContentFile(buffer.getvalue())


def versies_van(bestand, bestandsnaam):
    """Geef (hoofdbestand, thumbnail) als JPEG terug.

    Geeft (None, None) als dit geen afbeelding is; de aanroeper slaat het
    bestand dan onbewerkt op als document.
    """
    if is_niet_ondersteund(bestandsnaam):
        raise BestandNietLeesbaar(
            "HEIC-foto's kunnen we nog niet verwerken. Stel je telefoon in op "
            "'Meest compatibel' of stuur de foto als JPEG."
        )
    if not lijkt_afbeelding(bestandsnaam):
        return None, None

    bestand.seek(0)
    try:
        with Image.open(bestand) as geopend:
            geopend.load()
            recht = _plat_en_gedraaid(geopend)
            return _als_jpeg(recht, MAX_ZIJDE), _als_jpeg(recht, THUMB_ZIJDE)
    except (UnidentifiedImageError, OSError, ValueError) as oorzaak:
        raise BestandNietLeesbaar("Dit bestand is niet als afbeelding te openen.") from oorzaak


def thumbnail_van(bestand, bestandsnaam):
    """Voorbeeldplaatje voor een foto die als document is geüpload (zie
    klussen.views.bewaar_bijlage, forceer_document): het bestand zelf blijft
    ongemoeid zoals elk document, dit is alleen voor de documentenlijst.

    Geeft None terug als dit geen afbeelding is of niet te openen valt — dan
    krijgt het document net als een niet-PDF gewoon geen thumbnail, zie
    pdf_thumbnails.thumbnail_van hiernaast.
    """
    if is_niet_ondersteund(bestandsnaam) or not lijkt_afbeelding(bestandsnaam):
        return None

    bestand.seek(0)
    try:
        with Image.open(bestand) as geopend:
            geopend.load()
            return _als_jpeg(_plat_en_gedraaid(geopend), THUMB_ZIJDE)
    except (UnidentifiedImageError, OSError, ValueError):
        return None
