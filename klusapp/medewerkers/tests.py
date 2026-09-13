import re

from django.test import TestCase
from django.urls import reverse

from .models import Medewerker


def tegeltitels(html):
    return re.findall(r'class="titel">([^<]+)<', html)


class StartschermTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.eigenaar = Medewerker.objects.create_user(
            "maarten", password="test1234", first_name="Maarten", rol=Medewerker.Rol.EIGENAAR
        )
        cls.medewerker = Medewerker.objects.create_user(
            "sam", password="test1234", first_name="Sam", rol=Medewerker.Rol.MEDEWERKER
        )

    def test_uitgelogd_naar_inloggen(self):
        antwoord = self.client.get(reverse("start"))
        self.assertEqual(antwoord.status_code, 302)
        self.assertIn(reverse("inloggen"), antwoord.headers["Location"])

    def test_eigenaar_ziet_beheerderstegels(self):
        self.client.force_login(self.eigenaar)
        titels = tegeltitels(self.client.get(reverse("start")).content.decode())
        self.assertIn("Planbord", titels)
        self.assertIn("Aanwezigheid", titels)
        self.assertIn("Beheer", titels)
        self.assertNotIn("Mijn overzicht", titels)

    def test_medewerker_ziet_geen_beheerderstegels(self):
        self.client.force_login(self.medewerker)
        titels = tegeltitels(self.client.get(reverse("start")).content.decode())
        self.assertIn("Uren schrijven", titels)
        self.assertIn("Mijn overzicht", titels)
        for verboden in ("Planbord", "Aanwezigheid", "Beheer", "Overzichten"):
            self.assertNotIn(verboden, titels)

    def test_loonstrook_wijst_naar_het_aanmeldscherm(self):
        self.client.force_login(self.medewerker)
        html = self.client.get(reverse("start")).content.decode()
        self.assertIn('href="https://mijn.loondossier.nl/Aanmelden"', html)
        # een andere site hoort in een eigen tabblad te openen
        self.assertIn('target="_blank" rel="noopener"', html)
