import re
from datetime import date, time, timedelta

from django.test import TestCase
from django.urls import reverse

from klussen.models import Klus
from uren.models import Uurblok

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
        self.assertNotIn("Mijn overzicht", titels)

    def test_medewerker_ziet_geen_beheerderstegels(self):
        self.client.force_login(self.medewerker)
        titels = tegeltitels(self.client.get(reverse("start")).content.decode())
        self.assertIn("Uren schrijven", titels)
        self.assertIn("Mijn overzicht", titels)
        for verboden in ("Planbord", "Aanwezigheid", "Beheer", "Overzichten"):
            self.assertNotIn(verboden, titels)

    def test_loonstrooktegel_gaat_via_de_app_zelf(self):
        # De tegel wijst naar ons eigen adres; daar wordt pas bepaald of
        # iemand naar de app of naar de website moet.
        self.client.force_login(self.medewerker)
        html = self.client.get(reverse("start")).content.decode()
        self.assertIn(f'href="{reverse("loonstrook")}"', html)
        self.assertNotIn("mijn.loondossier.nl", html)

    def test_loonstrook_op_android_direct_naar_loondossier(self):
        self.client.force_login(self.medewerker)
        antwoord = self.client.get(
            reverse("loonstrook"),
            headers={"user-agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8) Chrome/120 Mobile"},
        )
        # Android opent de app zelf bij elk adres van mijn.loondossier.nl
        self.assertEqual(antwoord.status_code, 302)
        self.assertEqual(antwoord.headers["Location"], "https://mijn.loondossier.nl/Aanmelden")

    def test_loonstrook_op_een_computer_direct_naar_de_website(self):
        self.client.force_login(self.medewerker)
        antwoord = self.client.get(
            reverse("loonstrook"),
            headers={"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120"},
        )
        self.assertEqual(antwoord.status_code, 302)
        self.assertEqual(antwoord.headers["Location"], "https://mijn.loondossier.nl/Aanmelden")

    def test_loonstrook_op_iphone_laat_kiezen(self):
        self.client.force_login(self.medewerker)
        antwoord = self.client.get(
            reverse("loonstrook"),
            headers={"user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Safari/604.1"},
        )
        # iOS opent de app alleen als iemand zelf op de link tikt, en alleen
        # voor het pad /open-app/
        self.assertEqual(antwoord.status_code, 200)
        self.assertContains(antwoord, "https://mijn.loondossier.nl/open-app/")
        self.assertContains(antwoord, "https://mijn.loondossier.nl/Aanmelden")

    def test_loonstrook_vereist_inloggen(self):
        antwoord = self.client.get(reverse("loonstrook"))
        self.assertEqual(antwoord.status_code, 302)
        self.assertIn(reverse("inloggen"), antwoord.headers["Location"])

    def test_eigenaar_zonder_beheerrecht_ziet_geen_beheertegel(self):
        # De klant is eigenaar in de app, maar beheert het systeem niet.
        self.client.force_login(self.eigenaar)
        self.assertNotIn("Beheer", tegeltitels(self.client.get(reverse("start")).content.decode()))

    def test_systeembeheerder_ziet_de_beheertegel_wel(self):
        self.eigenaar.is_staff = True
        self.eigenaar.save()
        self.client.force_login(self.eigenaar)
        self.assertIn("Beheer", tegeltitels(self.client.get(reverse("start")).content.decode()))

    def test_beheerder_met_rol_medewerker_ziet_de_tegel_ook(self):
        # createsuperuser geeft geen rol mee; die staat dan op medewerker.
        self.medewerker.is_staff = True
        self.medewerker.save()
        self.client.force_login(self.medewerker)
        self.assertIn("Beheer", tegeltitels(self.client.get(reverse("start")).content.decode()))

    def test_geen_uren_deze_week_toont_lege_staat(self):
        self.client.force_login(self.medewerker)
        self.assertContains(self.client.get(reverse("start")), "Nog geen uren deze week geschreven")

    def test_klus_met_uren_deze_week_staat_op_het_startscherm(self):
        klus = Klus.objects.create(naam="Tuin Vermeer")
        Uurblok.objects.create(
            medewerker=self.medewerker, klus=klus, datum=date.today(), begintijd=time(8), eindtijd=time(12)
        )
        self.client.force_login(self.medewerker)
        self.assertContains(self.client.get(reverse("start")), "Tuin Vermeer")

    def test_klus_van_vorige_week_staat_niet_op_het_startscherm(self):
        klus = Klus.objects.create(naam="Oude klus")
        vorige_week = date.today() - timedelta(days=14)
        Uurblok.objects.create(
            medewerker=self.medewerker, klus=klus, datum=vorige_week, begintijd=time(8), eindtijd=time(12)
        )
        self.client.force_login(self.medewerker)
        self.assertNotContains(self.client.get(reverse("start")), "Oude klus")


class NavigatieTest(TestCase):
    """De zijbalk staat via een context processor op elke pagina, niet
    alleen het startscherm — dat borgen we hier apart van StartschermTest."""

    @classmethod
    def setUpTestData(cls):
        cls.medewerker = Medewerker.objects.create_user(
            "sam", password="test1234", first_name="Sam", rol=Medewerker.Rol.MEDEWERKER
        )

    def test_zijbalk_staat_ook_op_een_andere_pagina(self):
        self.client.force_login(self.medewerker)
        titels = tegeltitels(self.client.get(reverse("klussen")).content.decode())
        self.assertIn("Uren schrijven", titels)
        self.assertIn("Klussen", titels)

    def test_uitgelogd_geen_zijbalk_en_geen_foutmelding(self):
        antwoord = self.client.get(reverse("inloggen"))
        self.assertEqual(antwoord.status_code, 200)
        self.assertNotIn('class="sidebar', antwoord.content.decode())
