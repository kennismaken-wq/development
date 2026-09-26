"""Een geüploade profielfoto klaarmaken voor opslag.

Hergebruikt de verwerking van klusfoto's (klussen/afbeeldingen.py): rechtop
zetten, naar JPEG, EXIF eraf — daar zitten GPS-coördinaten in, en dat is bij
een pasfoto iemands woonadres. We bewaren alleen de kleine versie; een
profielfoto wordt nooit groter getoond dan de kop van het profielscherm.
"""

from klussen.afbeeldingen import BestandNietLeesbaar, versies_van  # noqa: F401  (doorgeven)


def verkleind(bestand):
    """Geef het bestand terug zoals het opgeslagen moet worden.

    Gooit BestandNietLeesbaar als het geen te openen afbeelding is; de
    aanroeper vertaalt dat naar een nette foutmelding in het formulier.
    """
    _groot, klein = versies_van(bestand, bestand.name)
    if klein is None:
        raise BestandNietLeesbaar("Kies een foto: jpg, png of webp.")
    return klein
