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

    def test_eigenaar_ziet_aanwezigheid_als_extra_navigatietegel(self):
        # Aanwezigheid is de enige tegel die naast de vaste vijf nog in de
        # balk zelf staat; de eigenaar checkt dat scherm dagelijks.
        self.client.force_login(self.eigenaar)
        titels = tegeltitels(self.client.get(reverse("start")).content.decode())
        self.assertIn("Aanwezigheid", titels)
        # Planbord, Overzichten, Loonstrook en Beheer staan niet meer in de
        # balk zelf maar op het profielscherm, zie ProfielschermTest hieronder.
        for verplaatst in ("Planbord", "Overzichten", "Loonstrook", "Beheer"):
            self.assertNotIn(verplaatst, titels)

    def test_medewerker_ziet_geen_beheerderstegels(self):
        self.client.force_login(self.medewerker)
        titels = tegeltitels(self.client.get(reverse("start")).content.decode())
        self.assertIn("Uren schrijven", titels)
        self.assertIn("Mijn profiel", titels)
        for verboden in ("Planbord", "Aanwezigheid", "Beheer", "Overzichten"):
            self.assertNotIn(verboden, titels)

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

    def test_geen_uren_toont_lege_staat(self):
        self.client.force_login(self.medewerker)
        self.assertContains(self.client.get(reverse("start")), "Nog geen uren geschreven")

    def test_klus_met_uren_staat_op_het_startscherm(self):
        klus = Klus.objects.create(naam="Tuin Vermeer")
        Uurblok.objects.create(
            medewerker=self.medewerker, klus=klus, datum=date.today(), begintijd=time(8), eindtijd=time(12)
        )
        self.client.force_login(self.medewerker)
        self.assertContains(self.client.get(reverse("start")), "Tuin Vermeer")

    def test_klus_van_weken_terug_staat_ook_nog_op_het_startscherm(self):
        # Niet beperkt tot deze week: de klussenslider toont elke klus waar
        # je ooit uren op hebt geschreven, met de meest recente vooraan.
        klus = Klus.objects.create(naam="Oude klus")
        weken_terug = date.today() - timedelta(days=14)
        Uurblok.objects.create(
            medewerker=self.medewerker, klus=klus, datum=weken_terug, begintijd=time(8), eindtijd=time(12)
        )
        self.client.force_login(self.medewerker)
        self.assertContains(self.client.get(reverse("start")), "Oude klus")

    def test_klus_met_recentste_uren_staat_vooraan(self):
        oude_klus = Klus.objects.create(naam="Klus A")
        nieuwe_klus = Klus.objects.create(naam="Klus B")
        Uurblok.objects.create(
            medewerker=self.medewerker,
            klus=oude_klus,
            datum=date.today() - timedelta(days=10),
            begintijd=time(8),
            eindtijd=time(12),
        )
        Uurblok.objects.create(
            medewerker=self.medewerker, klus=nieuwe_klus, datum=date.today(), begintijd=time(8), eindtijd=time(12)
        )
        self.client.force_login(self.medewerker)
        html = self.client.get(reverse("start")).content.decode()
        self.assertLess(html.index("Klus B"), html.index("Klus A"))


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


class ProfielschermTest(TestCase):
    """De schermen die niet in de navigatiebalk passen staan als knoppenlijst
    op /mijn-profiel/ — zie medewerkers/tegels.py: PROFIEL_TEGELS."""

    @classmethod
    def setUpTestData(cls):
        cls.eigenaar = Medewerker.objects.create_user(
            "maarten", password="test1234", first_name="Maarten", rol=Medewerker.Rol.EIGENAAR
        )
        cls.medewerker = Medewerker.objects.create_user(
            "sam", password="test1234", first_name="Sam", rol=Medewerker.Rol.MEDEWERKER
        )

    def test_medewerker_ziet_loonstrook_niet_overzichten_of_beheer(self):
        self.client.force_login(self.medewerker)
        titels = tegeltitels(self.client.get(reverse("mijn_profiel")).content.decode())
        self.assertIn("Loonstrook", titels)
        for verboden in ("Overzichten", "Beheer", "Planbord"):
            self.assertNotIn(verboden, titels)

    def test_eigenaar_ziet_ook_overzichten(self):
        self.client.force_login(self.eigenaar)
        titels = tegeltitels(self.client.get(reverse("mijn_profiel")).content.decode())
        self.assertIn("Overzichten", titels)
        self.assertNotIn("Planbord", titels)

    def test_loonstrooktegel_gaat_via_de_app_zelf(self):
        # De tegel wijst naar ons eigen adres; daar wordt pas bepaald of
        # iemand naar de app of naar de website moet.
        self.client.force_login(self.medewerker)
        html = self.client.get(reverse("mijn_profiel")).content.decode()
        self.assertIn(f'href="{reverse("loonstrook")}"', html)
        self.assertNotIn("mijn.loondossier.nl", html)

    def test_eigenaar_zonder_beheerrecht_ziet_geen_beheertegel(self):
        # De klant is eigenaar in de app, maar beheert het systeem niet.
        self.client.force_login(self.eigenaar)
        self.assertNotIn("Beheer", tegeltitels(self.client.get(reverse("mijn_profiel")).content.decode()))

    def test_systeembeheerder_ziet_de_beheertegel_wel(self):
        # De rol bepaalt de toegang; een vinkje zetten doet niets meer.
        self.eigenaar.rol = Medewerker.Rol.BEHEERDER
        self.eigenaar.save()
        self.client.force_login(self.eigenaar)
        self.assertIn("Beheer", tegeltitels(self.client.get(reverse("mijn_profiel")).content.decode()))

    def test_uitloggen_staat_op_het_profielscherm(self):
        self.client.force_login(self.medewerker)
        html = self.client.get(reverse("mijn_profiel")).content.decode()
        self.assertIn(f'action="{reverse("uitloggen")}"', html)

    def test_vereist_inloggen(self):
        antwoord = self.client.get(reverse("mijn_profiel"))
        self.assertEqual(antwoord.status_code, 302)
        self.assertIn(reverse("inloggen"), antwoord.headers["Location"])

class SysteembeheerderTest(TestCase):
    """De rol boven de eigenaar: die van ons, en de enige die in het
    Django-beheerscherm komt."""

    def maak(self, naam, rol):
        return Medewerker.objects.create_user(naam, password="test1234", rol=rol)

    def test_alleen_de_beheerder_komt_in_het_beheerscherm(self):
        beheerder = self.maak("floris", Medewerker.Rol.BEHEERDER)
        eigenaar = self.maak("maarten", Medewerker.Rol.EIGENAAR)
        medewerker = self.maak("sam", Medewerker.Rol.MEDEWERKER)

        self.client.force_login(beheerder)
        self.assertEqual(self.client.get("/beheer/").status_code, 200)

        for geweigerd in (eigenaar, medewerker):
            self.client.force_login(geweigerd)
            antwoord = self.client.get("/beheer/")
            # Django stuurt wie niet binnen mag terug naar zijn eigen inlog
            self.assertNotEqual(antwoord.status_code, 200)

    def test_beheerrecht_volgt_de_rol(self):
        mw = self.maak("floris", Medewerker.Rol.BEHEERDER)
        self.assertTrue(mw.is_staff)

        # en verdwijnt weer zodra de rol verandert
        mw.rol = Medewerker.Rol.EIGENAAR
        mw.save()
        self.assertFalse(mw.is_staff)

    def test_vinkje_zetten_geeft_geen_toegang(self):
        # Wie geen beheerder is, komt er ook niet in door is_staff aan te zetten.
        mw = self.maak("maarten", Medewerker.Rol.EIGENAAR)
        mw.is_staff = True
        mw.save()
        self.assertFalse(mw.is_staff)

    def test_superuser_wordt_beheerder(self):
        # createsuperuser kent onze rollen niet en zet alleen de vlaggen.
        mw = Medewerker.objects.create_superuser("floris", password="test1234")
        self.assertEqual(mw.rol, Medewerker.Rol.BEHEERDER)
        self.assertTrue(mw.is_staff)

    def test_beheerder_ziet_de_beheertegel(self):
        beheerder = self.maak("floris", Medewerker.Rol.BEHEERDER)
        self.client.force_login(beheerder)
        self.assertIn("Beheer", tegeltitels(self.client.get(reverse("mijn_profiel")).content.decode()))

    def test_eigenaar_ziet_de_beheertegel_niet(self):
        eigenaar = self.maak("maarten", Medewerker.Rol.EIGENAAR)
        self.client.force_login(eigenaar)
        self.assertNotIn("Beheer", tegeltitels(self.client.get(reverse("mijn_profiel")).content.decode()))


class MedewerkersBeherenTest(TestCase):
    """Het eigen beheerscherm voor medewerkers, zodat de klant niet in het
    Django-beheerscherm hoeft."""

    def setUp(self):
        self.eigenaar = Medewerker.objects.create_user(
            "maarten", password="test1234", first_name="Maarten", rol=Medewerker.Rol.EIGENAAR
        )
        self.sam = Medewerker.objects.create_user(
            "sam", password="test1234", first_name="Sam", rol=Medewerker.Rol.MEDEWERKER
        )
        self.client.force_login(self.eigenaar)

    def test_medewerker_komt_er_niet_in(self):
        self.client.force_login(self.sam)
        for adres in (
            reverse("medewerkers"),
            reverse("medewerker_nieuw"),
            reverse("medewerker_bewerken", args=[self.eigenaar.pk]),
        ):
            self.assertEqual(self.client.get(adres).status_code, 404, adres)

    def test_eigenaar_maakt_een_medewerker_aan(self):
        antwoord = self.client.post(
            reverse("medewerker_nieuw"),
            {
                "first_name": "Joep", "last_name": "Bakker", "username": "joep",
                "functie": "Hovenier", "telefoon": "", "rol": Medewerker.Rol.MEDEWERKER,
                "kleur": "#5B8FA8", "in_dienst_sinds": "2026-09-01",
                "wachtwoord": "tuinbaas2026",
            },
        )
        self.assertEqual(antwoord.status_code, 302)
        joep = Medewerker.objects.get(username="joep")
        self.assertEqual(joep.rol, Medewerker.Rol.MEDEWERKER)
        # en kan er meteen mee inloggen
        self.assertTrue(self.client.login(username="joep", password="tuinbaas2026"))

    def test_eigenaar_kan_geen_systeembeheerder_maken(self):
        # Anders geeft hij zichzelf via een nieuw account toegang tot het
        # Django-beheerscherm.
        self.client.post(
            reverse("medewerker_nieuw"),
            {
                "first_name": "Stiekem", "username": "stiekem",
                "rol": Medewerker.Rol.BEHEERDER, "kleur": "#5B8FA8",
                "wachtwoord": "tuinbaas2026",
            },
        )
        self.assertFalse(Medewerker.objects.filter(username="stiekem").exists())

    def test_systeembeheerders_zijn_onzichtbaar_voor_de_eigenaar(self):
        beheerder = Medewerker.objects.create_user(
            "floris", password="test1234", first_name="Floris", rol=Medewerker.Rol.BEHEERDER
        )
        html = self.client.get(reverse("medewerkers")).content.decode()
        self.assertNotIn("Floris", html)
        self.assertEqual(
            self.client.get(reverse("medewerker_bewerken", args=[beheerder.pk])).status_code, 404
        )

    def test_wachtwoord_opnieuw_instellen(self):
        self.client.post(
            reverse("medewerker_wachtwoord", args=[self.sam.pk]), {"wachtwoord": "nieuwezomer26"}
        )
        self.assertTrue(self.client.login(username="sam", password="nieuwezomer26"))

    def test_te_zwak_wachtwoord_wordt_geweigerd(self):
        self.client.post(reverse("medewerker_wachtwoord", args=[self.sam.pk]), {"wachtwoord": "1234"})
        self.sam.refresh_from_db()
        self.assertTrue(self.sam.check_password("test1234"))

    def test_uit_dienst_bewaart_de_persoon(self):
        self.client.post(reverse("medewerker_dienst", args=[self.sam.pk]))
        self.sam.refresh_from_db()
        self.assertIsNotNone(self.sam.uit_dienst_sinds)
        self.assertFalse(self.sam.is_active)
        # de persoon zelf blijft bestaan, met zijn uren en foto's
        self.assertTrue(Medewerker.objects.filter(pk=self.sam.pk).exists())

        # en kan weer terug
        self.client.post(reverse("medewerker_dienst", args=[self.sam.pk]))
        self.sam.refresh_from_db()
        self.assertIsNone(self.sam.uit_dienst_sinds)
        self.assertTrue(self.sam.is_active)

    def test_jezelf_uit_dienst_zetten_kan_niet(self):
        self.client.post(reverse("medewerker_dienst", args=[self.eigenaar.pk]))
        self.eigenaar.refresh_from_db()
        self.assertIsNone(self.eigenaar.uit_dienst_sinds)
        self.assertTrue(self.eigenaar.is_active)

    def test_de_wachtwoordeisen_staan_bij_het_veld(self):
        # Een eis die je pas leest nadat je hem overtreedt is geen hulp.
        for adres in (reverse("medewerker_nieuw"), reverse("medewerker_wachtwoord", args=[self.sam.pk])):
            html = self.client.get(adres).content.decode()
            self.assertIn("Minstens 8 tekens", html, adres)
            self.assertIn("Niet alleen cijfers", html, adres)

    def test_wachtwoord_dat_lijkt_op_de_naam_wordt_geweigerd(self):
        self.client.post(reverse("medewerker_wachtwoord", args=[self.sam.pk]), {"wachtwoord": "sam"})
        self.sam.refresh_from_db()
        self.assertTrue(self.sam.check_password("test1234"))
