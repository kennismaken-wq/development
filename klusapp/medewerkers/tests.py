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
    """Wie welk onderdeel ziet. De lijst staat sinds 22-09 op het startscherm
    (zie medewerkers/tegels.py: TEGELS en PROFIEL_TEGELS); het profielscherm
    gaat alleen nog over je eigen gegevens."""

    @classmethod
    def setUpTestData(cls):
        cls.eigenaar = Medewerker.objects.create_user(
            "maarten", password="test1234", first_name="Maarten", rol=Medewerker.Rol.EIGENAAR
        )
        cls.medewerker = Medewerker.objects.create_user(
            "sam", password="test1234", first_name="Sam", rol=Medewerker.Rol.MEDEWERKER
        )

    def test_medewerker_ziet_loonstrook_niet_overzichten_of_beheer(self):
        # De onderdelen staan sinds 22-09 op het startscherm, niet meer als
        # "Meer"-lijst op het profiel.
        self.client.force_login(self.medewerker)
        titels = [t["titel"] for t in self.client.get(reverse("start")).context["onderdelen"]]
        self.assertIn("Loonstrook", titels)
        for verboden in ("Overzichten", "Beheer", "Planbord"):
            self.assertNotIn(verboden, titels)

    def test_eigenaar_ziet_ook_overzichten(self):
        self.client.force_login(self.eigenaar)
        titels = [t["titel"] for t in self.client.get(reverse("start")).context["onderdelen"]]
        self.assertIn("Overzichten", titels)
        self.assertIn("Planbord", titels)

    def test_loonstrooktegel_gaat_via_de_app_zelf(self):
        # De tegel wijst naar ons eigen adres; daar wordt pas bepaald of
        # iemand naar de app of naar de website moet.
        self.client.force_login(self.medewerker)
        html = self.client.get(reverse("start")).content.decode()
        self.assertIn(f'href="{reverse("loonstrook")}"', html)
        self.assertNotIn("mijn.loondossier.nl", html)

    def test_eigenaar_ziet_de_beheertegel_en_een_medewerker_niet(self):
        # Tijdelijk: zolang er geen apart beheeraccount is, komt de eigenaar
        # in /beheer/. Zie de opmerking bij Medewerker.save().
        self.client.force_login(self.eigenaar)
        titels = [t["titel"] for t in self.client.get(reverse("start")).context["onderdelen"]]
        self.assertIn("Beheer", titels)

        self.client.force_login(self.medewerker)
        titels = [t["titel"] for t in self.client.get(reverse("start")).context["onderdelen"]]
        self.assertNotIn("Beheer", titels)

    def test_uitloggen_staat_op_het_profielscherm(self):
        self.client.force_login(self.medewerker)
        html = self.client.get(reverse("mijn_profiel")).content.decode()
        self.assertIn(f'action="{reverse("uitloggen")}"', html)

    def test_vereist_inloggen(self):
        antwoord = self.client.get(reverse("mijn_profiel"))
        self.assertEqual(antwoord.status_code, 302)
        self.assertIn(reverse("inloggen"), antwoord.headers["Location"])

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



    def test_volgorde_eerst_eigenaars_dan_op_voornaam(self):
        Medewerker.objects.create_user("zoe", password="x", first_name="Zoë", rol=Medewerker.Rol.EIGENAAR)
        Medewerker.objects.create_user("anna", password="x", first_name="anna")
        Medewerker.objects.create_user("bram", password="x", first_name="Bram")
        namen = [mw.first_name for mw in self.client.get(reverse("medewerkers")).context["in_dienst"]]
        # Maarten is eigenaar en Sam medewerker (zie setUp); "anna" met kleine
        # letter hoort gewoon tussen de rest, niet er los voor of achter.
        self.assertEqual(namen, ["Maarten", "Zoë", "anna", "Bram", "Sam"])


class StarttegelsTest(TestCase):
    """De onderdelen als tegels bovenaan het startscherm."""

    def setUp(self):
        self.eigenaar = Medewerker.objects.create_user(
            "maarten", password="x", first_name="Maarten", rol=Medewerker.Rol.EIGENAAR
        )
        self.sam = Medewerker.objects.create_user("sam", password="x", first_name="Sam")

    def test_medewerker_ziet_zijn_eigen_onderdelen(self):
        self.client.force_login(self.sam)
        html = self.client.get(reverse("start")).content.decode()
        self.assertIn("Uren schrijven", html)
        self.assertIn("Klussen", html)
        for alleen_voor_de_baas in ("Aanwezigheid", "Overzichten", "Medewerkers"):
            self.assertNotIn(alleen_voor_de_baas, html)

    def test_eigenaar_ziet_ook_zijn_eigen_schermen_met_cijfers(self):
        Klus.objects.create(naam="Tuin Vermeer")
        self.client.force_login(self.eigenaar)
        html = self.client.get(reverse("start")).content.decode()
        self.assertIn("Medewerkers", html)
        self.assertIn("2 in dienst", html)
        self.assertIn("1 lopend", html)

    def test_vereist_inloggen(self):
        antwoord = self.client.get(reverse("start"))
        self.assertEqual(antwoord.status_code, 302)


class TestgegevensTest(TestCase):
    """Tijdelijke knop die nepmedewerkers met uren aanmaakt."""

    def setUp(self):
        self.eigenaar = Medewerker.objects.create_user(
            "maarten", password="x", first_name="Maarten", rol=Medewerker.Rol.EIGENAAR
        )
        self.sam = Medewerker.objects.create_user("sam", password="x", first_name="Sam")

    def test_medewerker_komt_er_niet_bij(self):
        self.client.force_login(self.sam)
        self.client.post(reverse("testgegevens"), {"week": "2026-09-14"})
        self.assertFalse(Medewerker.objects.filter(username__startswith="demo-").exists())

    def test_aanmaken_geeft_een_week_vol_uren(self):
        self.client.force_login(self.eigenaar)
        self.client.post(reverse("testgegevens"), {"week": "2026-09-16"})

        nep = Medewerker.objects.filter(username__startswith="demo-")
        self.assertEqual(nep.count(), 5)
        blokken = Uurblok.objects.filter(medewerker__in=nep)
        self.assertGreater(blokken.count(), 15)
        # allemaal binnen die ene week, en nooit in het weekend
        for blok in blokken:
            self.assertGreaterEqual(blok.datum, date(2026, 9, 14))
            self.assertLessEqual(blok.datum, date(2026, 9, 20))
            self.assertLess(blok.datum.weekday(), 5)

    def test_testaccounts_kunnen_niet_inloggen(self):
        self.client.force_login(self.eigenaar)
        self.client.post(reverse("testgegevens"), {"week": "2026-09-16"})
        for nep in Medewerker.objects.filter(username__startswith="demo-"):
            self.assertFalse(nep.has_usable_password())

    def test_twee_keer_draaien_verdubbelt_de_uren_niet(self):
        self.client.force_login(self.eigenaar)
        self.client.post(reverse("testgegevens"), {"week": "2026-09-16"})
        eerste = Uurblok.objects.count()
        self.client.post(reverse("testgegevens"), {"week": "2026-09-16"})
        self.assertEqual(Uurblok.objects.count(), eerste)

    def test_opruimen_haalt_alles_weg_maar_laat_de_rest_staan(self):
        self.client.force_login(self.eigenaar)
        self.client.post(reverse("testgegevens"), {"week": "2026-09-16"})
        self.client.post(reverse("testgegevens"), {"actie": "opruimen"})

        self.assertFalse(Medewerker.objects.filter(username__startswith="demo-").exists())
        self.assertFalse(Uurblok.objects.exists())
        # de echte accounts blijven
        self.assertTrue(Medewerker.objects.filter(username="maarten").exists())
        self.assertTrue(Medewerker.objects.filter(username="sam").exists())

    def test_geen_broncommentaar_op_het_scherm(self):
        # Een {# #}-commentaar over meerdere regels is geen commentaar en
        # belandt zichtbaar op de pagina.
        self.client.force_login(self.sam)
        html = self.client.get(
            reverse("loonstrook"),
            headers={"user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Safari/604.1"},
        ).content.decode()
        self.assertNotIn("{#", html)
        self.assertNotIn("automatische doorverwijzing", html)

    def test_planbord_staat_vooraan_voor_de_eigenaar(self):
        self.client.force_login(self.eigenaar)
        titels = [t["titel"] for t in self.client.get(reverse("start")).context["onderdelen"]]
        self.assertEqual(titels[:2], ["Uren schrijven", "Planbord"])

    def test_medewerker_krijgt_geen_planbord(self):
        self.client.force_login(self.sam)
        titels = [t["titel"] for t in self.client.get(reverse("start")).context["onderdelen"]]
        self.assertNotIn("Planbord", titels)

    def test_geen_aanmaakformulier_meer_op_het_startscherm(self):
        self.client.force_login(self.eigenaar)
        html = self.client.get(reverse("start")).content.decode()
        self.assertNotIn("Testgegevens aanmaken", html)

    def test_opruimknop_verschijnt_en_verdwijnt_vanzelf(self):
        self.client.force_login(self.eigenaar)
        self.assertNotIn("Testgegevens verwijderen", self.client.get(reverse("start")).content.decode())

        self.client.post(reverse("testgegevens"), {"week": "2026-09-16"})
        self.assertIn("Testgegevens verwijderen", self.client.get(reverse("start")).content.decode())

        self.client.post(reverse("testgegevens"), {"actie": "opruimen"})
        self.assertNotIn("Testgegevens verwijderen", self.client.get(reverse("start")).content.decode())


class MijnProfielTest(TestCase):
    """Je eigen gegevens bekijken en wijzigen, zonder het scherm te verlaten."""

    def setUp(self):
        self.sam = Medewerker.objects.create_user(
            "sam", password="tuinbaas2026", first_name="Sam", last_name="de Wit",
            functie="Hovenier", rol=Medewerker.Rol.MEDEWERKER,
        )
        self.client.force_login(self.sam)

    def test_toont_je_eigen_gegevens_op_slot(self):
        self.sam.telefoon = "0612345678"
        self.sam.save()
        html = self.client.get(reverse("mijn_profiel")).content.decode()
        self.assertIn("Sam de Wit", html)
        self.assertIn("0612345678", html)
        # dezelfde velden, maar niet bewerkbaar tot je op de knop klikt
        self.assertIn("disabled", html)
        self.assertIn("Gegevens wijzigen", html)

    def test_zonder_javascript_openen_de_velden_via_de_link(self):
        html = self.client.get(reverse("mijn_profiel") + "?bewerken=1").content.decode()
        self.assertIn('name="telefoon"', html)
        self.assertNotIn('name="telefoon" disabled', html)
        self.assertIn("Opslaan", html)

    def test_meer_lijst_staat_er_niet_meer(self):
        # die onderdelen staan op het startscherm
        html = self.client.get(reverse("mijn_profiel")).content.decode()
        self.assertNotIn("profiellijst", html)

    def test_wijzigen_blijft_op_hetzelfde_adres(self):
        antwoord = self.client.post(
            reverse("mijn_profiel"),
            {"first_name": "Sam", "last_name": "de Wit", "telefoon": "0687654321",
             "kleur": "#5B8FA8", "rijbewijs": "B"},
        )
        self.assertEqual(antwoord.status_code, 302)
        self.assertEqual(antwoord.headers["Location"], reverse("mijn_profiel"))
        self.sam.refresh_from_db()
        self.assertEqual(self.sam.telefoon, "0687654321")
        self.assertEqual(self.sam.rijbewijs, "B")

    def test_je_kunt_jezelf_geen_andere_rol_geven(self):
        self.client.post(
            reverse("mijn_profiel"),
            {"first_name": "Sam", "kleur": "#5B8FA8",
             "rol": Medewerker.Rol.EIGENAAR, "username": "baas", "functie": "Directeur"},
        )
        self.sam.refresh_from_db()
        self.assertEqual(self.sam.rol, Medewerker.Rol.MEDEWERKER)
        self.assertEqual(self.sam.username, "sam")
        self.assertEqual(self.sam.functie, "Hovenier")

    def test_eigen_wachtwoord_wijzigen(self):
        antwoord = self.client.post(
            reverse("mijn_profiel"),
            {"actie": "wachtwoord", "huidig": "tuinbaas2026", "nieuw": "nieuwezomer26"},
        )
        self.assertEqual(antwoord.status_code, 302)
        self.sam.refresh_from_db()
        self.assertTrue(self.sam.check_password("nieuwezomer26"))
        # je blijft ingelogd na het wijzigen
        self.assertEqual(self.client.get(reverse("mijn_profiel")).status_code, 200)

    def test_verkeerd_huidig_wachtwoord_wijzigt_niets(self):
        antwoord = self.client.post(
            reverse("mijn_profiel"),
            {"actie": "wachtwoord", "huidig": "fout", "nieuw": "nieuwezomer26"},
        )
        self.assertContains(antwoord, "niet je huidige wachtwoord")
        self.sam.refresh_from_db()
        self.assertTrue(self.sam.check_password("tuinbaas2026"))

    def test_te_zwak_nieuw_wachtwoord_wordt_geweigerd(self):
        self.client.post(
            reverse("mijn_profiel"),
            {"actie": "wachtwoord", "huidig": "tuinbaas2026", "nieuw": "1234"},
        )
        self.sam.refresh_from_db()
        self.assertTrue(self.sam.check_password("tuinbaas2026"))
