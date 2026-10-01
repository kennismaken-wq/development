"""Klussen weghalen op dagen dat iemand afwezig staat.

Die combinatie hoort niet te bestaan (zie Aanwezigheid.save en Inzet.save),
maar stond er op develop toch: een rode dag met een klus erop. Eenmalig
opruimen; vanaf nu houdt het model het tegen.
"""

from django.db import migrations
from django.db.models import Exists, OuterRef


def opruimen(apps, schema_editor):
    Aanwezigheid = apps.get_model("uren", "Aanwezigheid")
    Inzet = apps.get_model("uren", "Inzet")
    afwezig = Aanwezigheid.objects.filter(
        medewerker_id=OuterRef("medewerker_id"), datum=OuterRef("datum"), aanwezig=False
    )
    Inzet.objects.filter(Exists(afwezig)).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("uren", "0004_inzet"),
    ]

    operations = [
        migrations.RunPython(opruimen, migrations.RunPython.noop),
    ]
