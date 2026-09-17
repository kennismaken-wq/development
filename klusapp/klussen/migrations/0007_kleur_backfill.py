# Datamigratie: klussen die van vóór de automatische kleurtoewijzing dateren
# (klussen.kleuren.volgende_kleur, zie klussen/views.py:klus_nieuw) hadden nog
# nooit een kleur gekregen. Vult die alsnog aan, elke klus een andere kleur
# uit het palet waar dat kan.
#
# Bewust een eigen kopie van het palet, niet geïmporteerd vanuit
# uren.kalender of klussen.kleuren: een migratie moet blijven werken zoals hij
# draaide op het moment dat hij geschreven is, ook als die modules later
# veranderen.
from django.db import migrations

PALET = ["#95BF1D", "#5B8FA8", "#E07B5F", "#C9A227", "#7FA88F", "#A5806A"]


def kleur_vullen(apps, schema_editor):
    Klus = apps.get_model("klussen", "Klus")
    # .upper(): een kleurkiezer levert kleine letters, PALET staat in
    # hoofdletters — zonder normaliseren ziet "#95bf1d" er als andere kleur
    # uit dan "#95BF1D" en botsen ze alsnog.
    bezet = [kleur.upper() for kleur in Klus.objects.exclude(kleur="").values_list("kleur", flat=True)]

    for klus in Klus.objects.filter(kleur="").order_by("aangemaakt_op", "pk"):
        vrij = next((kleur for kleur in PALET if kleur.upper() not in bezet), None)
        if vrij is None:
            # Palet op: de kleur die tot nu toe het minst is uitgedeeld, in
            # plaats van alles op dezelfde kleur te laten stapelen.
            vrij = min(PALET, key=lambda kleur: bezet.count(kleur.upper()))
        klus.kleur = vrij
        klus.save(update_fields=["kleur"])
        bezet.append(vrij.upper())


def kleur_niet_terug_te_draaien(apps, schema_editor):
    # Welke klus zijn kleur al had vóór deze migratie is niet meer te
    # achterhalen; achteruit draaien zou een lege kolom weer legen die
    # inmiddels ergens (het planbord) al zichtbaar is.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('klussen', '0006_klus_afgerond_op'),
    ]

    operations = [
        migrations.RunPython(kleur_vullen, kleur_niet_terug_te_draaien),
    ]
