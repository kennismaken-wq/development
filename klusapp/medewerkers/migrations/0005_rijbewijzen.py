"""Rijbewijs: van één keuze (B of C) plus een los aanhangervinkje naar een
lijst categorieën (29-09-2026).

Wat er al stond gaat mee: B blijft B, C wordt B en C (een C-rijbewijs haal
je niet zonder B), en het aanhangervinkje wordt BE.
"""

from django.db import migrations, models


def overzetten(apps, schema_editor):
    Medewerker = apps.get_model("medewerkers", "Medewerker")
    for mw in Medewerker.objects.all():
        codes = []
        if mw.rijbewijs in ("B", "C"):
            codes.append("B")
        if mw.aanhanger:
            codes.append("BE")
        if mw.rijbewijs == "C":
            codes.append("C")
        if codes:
            mw.rijbewijzen = codes
            mw.save(update_fields=["rijbewijzen"])


class Migration(migrations.Migration):

    dependencies = [
        ("medewerkers", "0004_medewerker_profielfoto"),
    ]

    operations = [
        migrations.AddField(
            model_name="medewerker",
            name="rijbewijzen",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(overzetten, migrations.RunPython.noop),
        migrations.RemoveField(model_name="medewerker", name="rijbewijs"),
        migrations.RemoveField(model_name="medewerker", name="aanhanger"),
    ]
