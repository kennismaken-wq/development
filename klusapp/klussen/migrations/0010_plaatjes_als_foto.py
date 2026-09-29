"""Plaatjes die als document zijn opgeslagen, eenmalig omzetten naar foto's.

Tot 27-09-2026 bleef een foto die via "Document toevoegen" binnenkwam een
document: onverkleind, met GPS en al, in de documentenlijst. Sindsdien is een
plaatje altijd een foto (klussen.views.bewaar_bijlage). Dit trekt wat er al
stond gelijk: verkleinen, GPS eraf, nieuwe thumbnail, en de oude bestanden weg.

Een bestand dat ontbreekt of niet te openen is, krijgt alleen de soort foto;
aan de bestanden zelf verandert dan niets.

Let op: op 29-09-2026 is die regel teruggedraaid. Sindsdien bepaalt weer de
knop ("Document toevoegen" of de foto-upload) of iets een document of een
foto is, niet het bestandstype — een tekening als png is soms echt een
document. Deze migratie heeft op develop al gedraaid en blijft daarom staan;
wat hij toen omzette, is een foto gebleven.
"""

from io import BytesIO
from pathlib import Path

from django.db import migrations


def omzetten(apps, schema_editor):
    from klussen import afbeeldingen

    Bijlage = apps.get_model("klussen", "Bijlage")
    for bijlage in Bijlage.objects.filter(soort="document"):
        if not afbeeldingen.lijkt_afbeelding(bijlage.bestand.name):
            continue

        oud_bestand = bijlage.bestand.name
        oud_thumbnail = bijlage.thumbnail.name
        try:
            with bijlage.bestand.open("rb") as geopend:
                inhoud = BytesIO(geopend.read())
            hoofd, thumbnail = afbeeldingen.versies_van(inhoud, oud_bestand)
        except (OSError, afbeeldingen.BestandNietLeesbaar):
            bijlage.soort = "foto"
            bijlage.save(update_fields=["soort"])
            continue

        stam = Path(bijlage.originele_naam or oud_bestand).stem
        bijlage.bestand.save(f"{stam}.jpg", hoofd, save=False)
        bijlage.thumbnail.save(f"{stam}.jpg", thumbnail, save=False)
        bijlage.soort = "foto"
        bijlage.save()

        opslag = bijlage.bestand.storage
        for oud in (oud_bestand, oud_thumbnail):
            if oud:
                opslag.delete(oud)


class Migration(migrations.Migration):

    dependencies = [
        ("klussen", "0009_alter_klus_soort"),
    ]

    operations = [
        migrations.RunPython(omzetten, migrations.RunPython.noop),
    ]
