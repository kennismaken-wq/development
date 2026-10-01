"""Feedback uit het gesprek met Maarten van 01-10-2026, voor zover het in de
app uren landt: extra werk en de tijdkiezer. Los van tests.py zodat dit niet
botst met ander werk aan dat bestand."""

from datetime import date, time

from django.test import TestCase

from klussen.models import Klus
from medewerkers.models import Medewerker

from . import export
from .forms import UurblokForm
from .models import Uurblok


class ExtraWerkTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sam = Medewerker.objects.create_user("sam", password="x", first_name="Sam")
        cls.klus = Klus.objects.create(naam="Tuin Vermeer")

    def test_extra_werk_gaat_mee_in_de_export(self):
        blok = Uurblok.objects.create(
            medewerker=self.sam, klus=self.klus, datum=date(2026, 10, 1),
            begintijd=time(8), eindtijd=time(12), toelichting="Bestraten",
            extra_werk="Regenpijp vervangen, 40 euro benzine",
        )
        blad = export.werkboek_bouwen([blok], "Uren").active
        koppen = [cel.value for cel in blad[1]]
        self.assertEqual(koppen[-1], "Extra werk")
        self.assertEqual(blad[2][koppen.index("Extra werk")].value, "Regenpijp vervangen, 40 euro benzine")
        self.assertEqual(blad[2][koppen.index("Toelichting")].value, "Bestraten")

    def test_extra_werk_staat_in_het_formulier_en_is_niet_verplicht(self):
        formulier = UurblokForm(
            {"klus": self.klus.pk, "datum": "2026-10-01", "begintijd": "08:00", "eindtijd": "12:00"},
            medewerker=self.sam,
        )
        self.assertIn("extra_werk", formulier.fields)
        self.assertEqual(formulier.fields["extra_werk"].label, "Extra werk")
        self.assertTrue(formulier.is_valid(), formulier.errors)


class TijdkiezerTest(TestCase):
    """De tijdkiezer begon op 00:00; Maarten scrolde zich suf (01-10-2026)."""

    def waarden(self, formulier, veld):
        return [waarde for waarde, _ in formulier.fields[veld].widget.choices if waarde]

    def test_begint_bij_vijf_uur(self):
        formulier = UurblokForm()
        self.assertEqual(self.waarden(formulier, "begintijd")[0], "05:00")
        self.assertNotIn("04:45", self.waarden(formulier, "begintijd"))

    def test_bestaand_vroeg_blok_houdt_zijn_tijd(self):
        sam = Medewerker.objects.create_user("sam", password="x")
        blok = Uurblok.objects.create(
            medewerker=sam, klus=Klus.objects.create(naam="Vroeg"), datum=date(2026, 10, 1),
            begintijd=time(4, 30), eindtijd=time(6),
        )
        html = str(UurblokForm(instance=blok)["begintijd"])
        self.assertRegex(html, r'value="04:30"[^>]*selected')
