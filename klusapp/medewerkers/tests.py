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
        self.assertIn("Loonstrook", titels)
        # Weekoverzicht, Urenexport en Beheer staan niet meer in de balk zelf
        # maar op het profielscherm, zie ProfielschermTest hieronder.
        for verplaatst in ("Weekoverzicht", "Urenexport", "Beheer"):
            self.assertNotIn(verplaatst, titels)

    def test_medewerker_ziet_geen_beheerderstegels(self):
        self.client.force_login(self.medewerker)
        titels = tegeltitels(self.client.get(reverse("start")).content.decode())
        self.assertIn("Uren schrijven", titels)
        self.assertIn("Mijn profiel", titels)
        self.assertIn("Loonstrook", titels)
        for verboden in ("Weekoverzicht", "Aanwezigheid", "Beheer", "Urenexport"):
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
        for verboden in ("Urenexport", "Beheer", "Weekoverzicht"):
            self.assertNotIn(verboden, titels)

    def test_eigenaar_ziet_ook_overzichten(self):
        self.client.force_login(self.eigenaar)
        titels = [t["titel"] for t in self.client.get(reverse("start")).context["onderdelen"]]
        self.assertIn("Urenexport", titels)
        self.assertIn("Weekoverzicht", titels)

    def test_loonstrooktegel_gaat_via_de_app_zelf(self):
        # De tegel wijst naar ons eigen adres; daar wordt pas bepaald of
        # iemand naar de app of naar de website moet.
        self.client.force_login(self.medewerker)
        html = self.client.get(reverse("start")).content.decode()
        self.assertIn(f'href="{reverse("loonstrook")}"', html)
        self.assertNotIn("mijn.loondossier.nl", html)

    def test_geen_beheertegel_maar_het_adres_werkt_nog(self):
        # Sinds 29-09-2026 geen tegel meer; het adres blijft voor wie het kent.
        # Tijdelijk mag een eigenaar er nog in, zie Medewerker.save().
        for persoon in (self.eigenaar, self.medewerker):
            self.client.force_login(persoon)
            html = self.client.get(reverse("start")).content.decode()
            self.assertNotIn('href="/beheer/"', html)
        self.client.force_login(self.eigenaar)
        self.assertEqual(self.client.get("/beheer/").status_code, 200)
        self.client.force_login(self.medewerker)
        self.assertNotEqual(self.client.get("/beheer/").status_code, 200)

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

    def test_eigenaar_kan_geen_wachtwoord_van_een_ander_zetten(self):
        # Sinds 28-09-2026: een wachtwoord wijzigt ieder alleen zelf, op Mijn
        # profiel. Geen knop op het medewerkersscherm, en ook het oude adres
        # bestaat niet meer.
        html = self.client.get(reverse("medewerker_bewerken", args=[self.sam.pk])).content.decode()
        self.assertNotIn("Nieuw wachtwoord instellen", html)
        self.assertNotIn(f"/medewerkers/{self.sam.pk}/wachtwoord/", html)
        antwoord = self.client.post(f"/medewerkers/{self.sam.pk}/wachtwoord/", {"wachtwoord": "nieuwezomer26"})
        self.assertEqual(antwoord.status_code, 404)
        self.sam.refresh_from_db()
        self.assertTrue(self.sam.check_password("test1234"))

    def test_te_zwak_tijdelijk_wachtwoord_wordt_geweigerd(self):
        self.client.post(
            reverse("medewerker_nieuw"),
            {"first_name": "Joep", "username": "joep", "rol": "medewerker",
             "kleur": "#5B8FA8", "wachtwoord": "1234"},
        )
        self.assertFalse(Medewerker.objects.filter(username="joep").exists())

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
        html = self.client.get(reverse("medewerker_nieuw")).content.decode()
        self.assertIn("Minstens 8 tekens", html)
        self.assertIn("Niet alleen cijfers", html)



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
        for alleen_voor_de_baas in ("Aanwezigheid", "Urenexport", "Medewerkers"):
            self.assertNotIn(alleen_voor_de_baas, html)

    def test_eigenaar_ziet_ook_zijn_eigen_schermen(self):
        # Sinds 22-09 staan de tegels als compacte app-iconen zonder cijfer
        # erbij (zie templates/start.html); alleen de titel is nog te checken.
        self.client.force_login(self.eigenaar)
        html = self.client.get(reverse("start")).content.decode()
        self.assertIn("Medewerkers", html)

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

    def test_weekoverzicht_staat_vooraan_voor_de_eigenaar(self):
        self.client.force_login(self.eigenaar)
        titels = [t["titel"] for t in self.client.get(reverse("start")).context["onderdelen"]]
        self.assertEqual(titels[:2], ["Uren schrijven", "Weekoverzicht"])

    def test_medewerker_krijgt_geen_weekoverzicht(self):
        self.client.force_login(self.sam)
        titels = [t["titel"] for t in self.client.get(reverse("start")).context["onderdelen"]]
        self.assertNotIn("Weekoverzicht", titels)

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
             "kleur": "#5B8FA8", "rijbewijzen": ["BE", "B"]},
        )
        self.assertEqual(antwoord.status_code, 302)
        self.assertEqual(antwoord.headers["Location"], reverse("mijn_profiel"))
        self.sam.refresh_from_db()
        self.assertEqual(self.sam.telefoon, "0687654321")
        # in de volgorde van het rijbewijs, niet in die van het aanvinken
        self.assertEqual(self.sam.rijbewijzen, ["B", "BE"])

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

    def test_bewerkstand_is_zichtbaar_aan_het_formulier(self):
        op_slot = self.client.get(reverse("mijn_profiel")).content.decode()
        self.assertNotIn('class="bewerkt"', op_slot)

        open_ = self.client.get(reverse("mijn_profiel") + "?bewerken=1").content.decode()
        self.assertIn('class="bewerkt"', open_)


class ProfielfotoTest(TestCase):
    """Een pasfoto uploaden, verkleind opslaan en overal tonen."""

    @staticmethod
    def _foto(breedte=1600, hoogte=1200, naam="pasfoto.jpg"):
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        buffer = BytesIO()
        Image.new("RGB", (breedte, hoogte), (90, 140, 70)).save(buffer, format="JPEG")
        return SimpleUploadedFile(naam, buffer.getvalue(), content_type="image/jpeg")

    def setUp(self):
        self.sam = Medewerker.objects.create_user(
            "sam", password="tuinbaas2026", first_name="Sam", last_name="de Wit"
        )
        self.client.force_login(self.sam)

    def _formuliervelden(self, **extra):
        velden = {"first_name": "Sam", "last_name": "de Wit", "kleur": "#5B8FA8"}
        velden.update(extra)
        return velden

    def test_uploaden_slaat_een_verkleinde_versie_op(self):
        from PIL import Image

        self.client.post(
            reverse("mijn_profiel"), self._formuliervelden(profielfoto=self._foto())
        )
        self.sam.refresh_from_db()
        self.assertTrue(self.sam.profielfoto)

        with Image.open(self.sam.profielfoto) as opgeslagen:
            # THUMB_ZIJDE is 400: het origineel van 1600px wordt niet bewaard
            self.assertLessEqual(max(opgeslagen.size), 400)

    def test_een_bestand_dat_geen_foto_is_wordt_geweigerd(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        nep = SimpleUploadedFile("cv.pdf", b"%PDF-1.4 geen foto", content_type="application/pdf")
        self.client.post(reverse("mijn_profiel"), self._formuliervelden(profielfoto=nep))
        self.sam.refresh_from_db()
        self.assertFalse(self.sam.profielfoto)

    def test_opslaan_zonder_nieuwe_foto_laat_de_bestaande_staan(self):
        self.client.post(
            reverse("mijn_profiel"), self._formuliervelden(profielfoto=self._foto())
        )
        self.sam.refresh_from_db()
        eerste = self.sam.profielfoto.name

        self.client.post(reverse("mijn_profiel"), self._formuliervelden(telefoon="0612345678"))
        self.sam.refresh_from_db()
        self.assertEqual(self.sam.profielfoto.name, eerste)
        self.assertEqual(self.sam.telefoon, "0612345678")

    def test_zonder_foto_blijven_de_initialen_staan(self):
        html = self.client.get(reverse("mijn_profiel")).content.decode()
        self.assertIn("SD", html)
        # let op: het woord bolfoto staat ook in het script dat een gekozen
        # foto alvast toont, dus zoeken op de <img> zelf
        self.assertNotIn('<img class="bolfoto"', html)

    def test_met_foto_verschijnt_die_op_het_profiel(self):
        self.client.post(
            reverse("mijn_profiel"), self._formuliervelden(profielfoto=self._foto())
        )
        html = self.client.get(reverse("mijn_profiel")).content.decode()
        self.assertIn('<img class="bolfoto"', html)

    def test_de_foto_staat_ook_op_het_planbord_en_bij_de_aanwezigheid(self):
        self.client.post(
            reverse("mijn_profiel"), self._formuliervelden(profielfoto=self._foto())
        )
        baas = Medewerker.objects.create_user(
            "maarten", password="x", first_name="Maarten", rol=Medewerker.Rol.EIGENAAR
        )
        self.client.force_login(baas)
        for adres in ("/planbord/", "/aanwezigheid/", reverse("medewerkers")):
            self.assertIn('<img class="bolfoto"', self.client.get(adres).content.decode(), adres)

    def test_geen_bestandsknop_tussen_de_gegevens(self):
        # De foto wissel je via het pennetje op de foto, niet via een
        # "Bestand kiezen"-knop in de lijst met gegevens.
        html = self.client.get(reverse("mijn_profiel")).content.decode()
        self.assertIn("fotowissel", html)
        self.assertIn("buiten-beeld", html)
        # het veld zit wél in het formulier
        self.assertIn('name="profielfoto"', html)

    def test_foto_is_niet_te_wijzigen_zolang_je_niet_aan_het_wijzigen_bent(self):
        # Op slot: een tik op de foto mag de fotokiezer niet openen.
        op_slot = self.client.get(reverse("mijn_profiel")).context["formulier"]
        self.assertTrue(op_slot.fields["profielfoto"].widget.attrs.get("disabled"))

        bewerken = self.client.get(reverse("mijn_profiel") + "?bewerken=1").context["formulier"]
        self.assertFalse(bewerken.fields["profielfoto"].widget.attrs.get("disabled"))

    def test_het_fotoveld_staat_niet_in_de_veldgroepen(self):
        velden = [
            veld.name
            for _kop, groep in self.client.get(reverse("mijn_profiel")).context["formulier"].groepen()
            for veld in groep
        ]
        self.assertNotIn("profielfoto", velden)

    def test_pennetje_staat_er_pas_in_de_bewerkstand(self):
        op_slot = self.client.get(reverse("mijn_profiel")).content.decode()
        self.assertIn('class="fotowissel"', op_slot)

        bewerken = self.client.get(reverse("mijn_profiel") + "?bewerken=1").content.decode()
        self.assertIn('class="fotowissel aan"', bewerken)


class WisselenTest(TestCase):
    """TIJDELIJK: als eigenaar met één tik meekijken als medewerker."""

    def setUp(self):
        self.maarten = Medewerker.objects.create_user(
            "maarten", password="x", first_name="Maarten", rol=Medewerker.Rol.EIGENAAR
        )
        self.sam = Medewerker.objects.create_user("sam", password="x", first_name="Sam")

    def ingelogd(self):
        return self.client.get(reverse("start")).context["user"]

    def test_eigenaar_ziet_de_knoppen_medewerker_niet(self):
        self.client.force_login(self.maarten)
        html = self.client.get(reverse("start")).content.decode()
        self.assertIn(reverse("wissel_naar", args=[self.sam.pk]), html)

        self.client.force_login(self.sam)
        html = self.client.get(reverse("start")).content.decode()
        self.assertNotIn("Bekijk als medewerker", html)

    def test_wisselen_en_terug(self):
        self.client.force_login(self.maarten)
        self.client.post(reverse("wissel_naar", args=[self.sam.pk]))
        self.assertEqual(self.ingelogd(), self.sam)
        html = self.client.get(reverse("start")).content.decode()
        self.assertIn("Terug naar Maarten", html)

        self.client.post(reverse("wissel_terug"))
        self.assertEqual(self.ingelogd(), self.maarten)
        html = self.client.get(reverse("start")).content.decode()
        self.assertNotIn('class="wisselbalk"', html)

    def test_medewerker_kan_niet_wisselen(self):
        self.client.force_login(self.sam)
        antwoord = self.client.post(reverse("wissel_naar", args=[self.maarten.pk]))
        self.assertEqual(antwoord.status_code, 404)
        self.assertEqual(self.ingelogd(), self.sam)

    def test_niet_naar_een_andere_eigenaar_of_iemand_uit_dienst(self):
        tweede = Medewerker.objects.create_user("els", password="x", rol=Medewerker.Rol.EIGENAAR)
        weg = Medewerker.objects.create_user(
            "piet", password="x", is_active=False, uit_dienst_sinds=date(2026, 1, 1)
        )
        self.client.force_login(self.maarten)
        for persoon in (tweede, weg):
            antwoord = self.client.post(reverse("wissel_naar", args=[persoon.pk]))
            self.assertEqual(antwoord.status_code, 404)
        self.assertEqual(self.ingelogd(), self.maarten)

    def test_alleen_met_post(self):
        self.client.force_login(self.maarten)
        antwoord = self.client.get(reverse("wissel_naar", args=[self.sam.pk]))
        self.assertEqual(antwoord.status_code, 405)
        self.assertEqual(self.ingelogd(), self.maarten)

    def test_terug_zonder_te_hebben_gewisseld_doet_niets(self):
        # Een medewerker die zelf "terug" post, wordt niet ineens eigenaar.
        self.client.force_login(self.sam)
        self.client.post(reverse("wissel_terug"))
        self.assertEqual(self.ingelogd(), self.sam)

    def test_testaccounts_zonder_wachtwoord_zijn_ook_te_bekijken(self):
        # Juist die hebben uren, dus daar wil je in kunnen kijken.
        self.client.force_login(self.maarten)
        self.client.post(reverse("testgegevens"), {"week": "2026-09-16"})
        nep = Medewerker.objects.filter(username__startswith="demo-").first()
        self.client.post(reverse("wissel_naar", args=[nep.pk]))
        self.assertEqual(self.ingelogd(), nep)


class PersoonskaartTest(TestCase):
    """De gegevens van één medewerker als venster op het weekoverzicht."""

    @classmethod
    def setUpTestData(cls):
        cls.maarten = Medewerker.objects.create_user(
            "maarten", password="x", first_name="Maarten", rol=Medewerker.Rol.EIGENAAR
        )
        cls.sam = Medewerker.objects.create_user(
            "sam", password="x", first_name="Sam", last_name="de Wit",
            telefoon="06 12345678", noodcontact_naam="Anne", noodcontact_relatie="partner",
            noodcontact_telefoon="06 87654321", rijbewijzen=["B", "BE"],
        )

    def test_eigenaar_ziet_de_gegevens(self):
        self.client.force_login(self.maarten)
        html = self.client.get(reverse("medewerker_kaart", args=[self.sam.pk])).content.decode()
        self.assertIn("Sam de Wit", html)
        self.assertIn('href="tel:06 12345678"', html)
        self.assertIn("Anne (partner)", html)
        self.assertIn("B, BE", html)
        self.assertIn(reverse("medewerker_bewerken", args=[self.sam.pk]), html)

    def test_medewerker_niet(self):
        self.client.force_login(self.sam)
        antwoord = self.client.get(reverse("medewerker_kaart", args=[self.maarten.pk]))
        self.assertEqual(antwoord.status_code, 404)

    def test_naam_op_het_weekoverzicht_opent_de_kaart(self):
        self.client.force_login(self.maarten)
        html = self.client.get(reverse("planbord")).content.decode()
        self.assertIn(f'data-paneel-url="{reverse("medewerker_kaart", args=[self.sam.pk])}"', html)
        self.assertIn('id="persoon-detail"', html)


class MedewerkerZoalsProfielTest(TestCase):
    """Het medewerkersscherm werkt als Mijn profiel (medewerkers/_gegevens.html)."""

    @classmethod
    def setUpTestData(cls):
        cls.maarten = Medewerker.objects.create_user(
            "maarten", password="x", first_name="Maarten", rol=Medewerker.Rol.EIGENAAR
        )
        cls.sam = Medewerker.objects.create_user("sam", password="x", first_name="Sam", telefoon="0612")

    def setUp(self):
        self.client.force_login(self.maarten)
        self.adres = reverse("medewerker_bewerken", args=[self.sam.pk])

    def test_eerst_op_slot(self):
        html = self.client.get(self.adres).content.decode()
        self.assertIn('id="wijzig-knop"', html)
        self.assertRegex(html, r'<input[^>]*name="telefoon"[^>]*disabled')
        self.assertRegex(html, r'id="opslaanrij" hidden')
        # geen "Bestand kiezen" in beeld: de foto zit achter het pennetje,
        # en staat er dus maar één keer (niet ook nog tussen de velden)
        self.assertIn('class="buiten-beeld"', html)
        self.assertEqual(html.count('name="profielfoto"'), 1)

    def test_bewerken_zet_de_velden_open(self):
        html = self.client.get(self.adres + "?bewerken=1").content.decode()
        self.assertNotRegex(html, r'<input[^>]*name="telefoon"[^>]*disabled')
        self.assertIn('class="bewerkt"', html)

    def test_opslaan_blijft_op_dezelfde_pagina(self):
        gegevens = {
            "first_name": "Sam", "last_name": "de Wit", "username": "sam",
            "rol": Medewerker.Rol.MEDEWERKER, "telefoon": "06 99", "kleur": "#5B8FA8",
        }
        antwoord = self.client.post(self.adres, gegevens)
        self.assertRedirects(antwoord, self.adres)
        self.sam.refresh_from_db()
        self.assertEqual(self.sam.telefoon, "06 99")

    def test_fout_houdt_het_formulier_open(self):
        antwoord = self.client.post(self.adres, {"first_name": "", "username": "sam", "rol": "medewerker"})
        html = antwoord.content.decode()
        self.assertIn('class="bewerkt"', html)
        self.assertNotRegex(html, r'id="opslaanrij" hidden')

    def test_nieuwe_medewerker_meteen_open(self):
        html = self.client.get(reverse("medewerker_nieuw")).content.decode()
        self.assertIn('class="bewerkt"', html)
        self.assertIn("Medewerker toevoegen", html)
        self.assertIn("leeg-bol", html)


class KlikbareGegevensTest(TestCase):
    """Telefoon en e-mail zijn in de leesstand een link (_gegevens.html)."""

    def test_tel_en_mailto_op_profiel_en_medewerkersscherm(self):
        maarten = Medewerker.objects.create_user(
            "maarten", password="x", first_name="Maarten", rol=Medewerker.Rol.EIGENAAR,
            telefoon="06 11", email="m@voorbeeld.nl",
        )
        sam = Medewerker.objects.create_user(
            "sam", password="x", first_name="Sam", telefoon="06 22", noodcontact_telefoon="06 33"
        )
        self.client.force_login(maarten)
        for adres, verwacht in (
            (reverse("mijn_profiel"), ['href="tel:06 11"', 'href="mailto:m@voorbeeld.nl"']),
            (reverse("medewerker_bewerken", args=[sam.pk]), ['href="tel:06 22"', 'href="tel:06 33"']),
        ):
            html = self.client.get(adres).content.decode()
            for stuk in verwacht:
                self.assertIn(stuk, html, adres)
        # een leeg veld wordt geen link
        html = self.client.get(reverse("medewerker_bewerken", args=[sam.pk])).content.decode()
        self.assertNotIn('href="mailto:', html)


class LeegDatumveldTest(TestCase):
    """Een lege datum op slot toont een streepje, geen dd/mm/jjjj."""

    def test_leeg_en_gevuld(self):
        maarten = Medewerker.objects.create_user("maarten", password="x", rol=Medewerker.Rol.EIGENAAR)
        leeg = Medewerker.objects.create_user("sam", password="x", first_name="Sam")
        gevuld = Medewerker.objects.create_user(
            "joep", password="x", first_name="Joep", in_dienst_sinds=date(2022, 4, 1)
        )
        self.client.force_login(maarten)
        html = self.client.get(reverse("medewerker_bewerken", args=[leeg.pk])).content.decode()
        self.assertRegex(html, r'<input type="text" name="in_dienst_sinds"[^>]*data-type="date"[^>]*placeholder="—"|<input type="text" name="in_dienst_sinds"[^>]*placeholder="—"[^>]*data-type="date"')
        html = self.client.get(reverse("medewerker_bewerken", args=[gevuld.pk])).content.decode()
        self.assertRegex(html, r'<input type="date" name="in_dienst_sinds" value="2022-04-01"')
        # in de bewerkstand gewoon een datumveld
        html = self.client.get(reverse("medewerker_bewerken", args=[leeg.pk]) + "?bewerken=1").content.decode()
        self.assertRegex(html, r'<input type="date" name="in_dienst_sinds"')



class RijbewijzenEnKleurTest(TestCase):
    """Rijbewijs als aanvinkbare categorieën, "Kleur" zonder eigen kopje en
    geen uitleg meer onder "Relatie" (29-09-2026)."""

    @classmethod
    def setUpTestData(cls):
        cls.sam = Medewerker.objects.create_user("sam", password="x", first_name="Sam")

    def setUp(self):
        self.client.force_login(self.sam)

    def test_alle_categorieen_aan_te_vinken(self):
        html = self.client.get(reverse("mijn_profiel") + "?bewerken=1").content.decode()
        for code in ("AM", "A1", "A2", "A", "B", "BE", "C1", "C1E", "C", "CE", "D1", "D1E", "D", "DE", "T"):
            self.assertIn(f'value="{code}"', html, code)
        self.assertEqual(html.count('name="rijbewijzen"'), 15)
        for groep in ("Bromfiets en motor", "Auto", "Vrachtwagen", "Bus", "Trekker"):
            self.assertIn(groep, html)

    def test_kleurvlak_toont_de_kleur_van_je_rondje(self):
        # Nog nooit een kleur gekozen: het vlakje toont de uitgerekende kleur
        # van je rondje, niet een vaste blauwe.
        from uren.kalender import medewerker_kleur_van
        html = self.client.get(reverse("mijn_profiel")).content.decode()
        self.assertIn(f'name="kleur" value="{medewerker_kleur_van(self.sam)}"', html)

    def test_onbekende_categorie_wordt_geweigerd(self):
        self.client.post(reverse("mijn_profiel"), {"first_name": "Sam", "kleur": "#5B8FA8", "rijbewijzen": ["X"]})
        self.sam.refresh_from_db()
        self.assertEqual(self.sam.rijbewijzen, [])

    def test_geen_in_de_app_en_geen_relatie_uitleg(self):
        html = self.client.get(reverse("mijn_profiel")).content.decode()
        self.assertNotIn("In de app", html)
        self.assertNotIn("Bijvoorbeeld partner", html)
        self.assertIn(">Kleur</label>", html)

    def test_migratie_zet_de_oude_velden_over(self):
        import importlib
        from types import SimpleNamespace
        overzetten = importlib.import_module("medewerkers.migrations.0005_rijbewijzen").overzetten
        opgeslagen = []

        class Nep(SimpleNamespace):
            def save(self, update_fields):
                opgeslagen.append((self.username, self.rijbewijzen))

        mensen = [Nep(username="piet", rijbewijs="B", aanhanger=False),
                  Nep(username="kees", rijbewijs="C", aanhanger=True),
                  Nep(username="jan", rijbewijs="", aanhanger=False)]
        apps = SimpleNamespace(get_model=lambda *a: SimpleNamespace(objects=SimpleNamespace(all=lambda: mensen)))
        overzetten(apps, None)
        self.assertEqual(opgeslagen, [("piet", ["B"]), ("kees", ["B", "BE", "C"])])


class OpslaanRechtsbovenTest(TestCase):
    """Tijdens het wijzigen staan Opslaan en Annuleren ook rechtsboven."""

    def test_alleen_in_de_bewerkstand_en_aan_het_formulier_gekoppeld(self):
        sam = Medewerker.objects.create_user("sam", password="x", first_name="Sam")
        self.client.force_login(sam)
        html = self.client.get(reverse("mijn_profiel")).content.decode()
        self.assertIn('id="bewerkacties" hidden', html)
        html = self.client.get(reverse("mijn_profiel") + "?bewerken=1").content.decode()
        self.assertNotIn('id="bewerkacties" hidden', html)
        self.assertIn('<button type="submit" form="gegevensformulier"', html)
        # en de knop rechtsboven slaat echt op
        antwoord = self.client.post(reverse("mijn_profiel"), {"first_name": "Samuel", "kleur": "#5B8FA8"})
        self.assertRedirects(antwoord, reverse("mijn_profiel"))


class WachtwoordVergetenTest(TestCase):
    """"Wachtwoord vergeten" op de inlogpagina (config/urls.py)."""

    @classmethod
    def setUpTestData(cls):
        cls.sam = Medewerker.objects.create_user(
            "sam", password="oudwachtwoord26", first_name="Sam", email="sam@voorbeeld.nl"
        )

    def aanvragen(self, adres):
        return self.client.post(reverse("wachtwoord_vergeten"), {"email": adres})

    def link_uit_mail(self):
        from django.core import mail
        return re.search(r"https?://[^/\s]+(/wachtwoord-herstellen/\S+/)", mail.outbox[-1].body).group(1)

    def test_inlogpagina_heeft_de_link(self):
        html = self.client.get(reverse("inloggen")).content.decode()
        self.assertIn(f'href="{reverse("wachtwoord_vergeten")}"', html)

    def test_mail_met_link_en_gebruikersnaam_naar_het_profieladres(self):
        from django.core import mail
        antwoord = self.aanvragen("sam@voorbeeld.nl")
        self.assertRedirects(antwoord, reverse("wachtwoord_verstuurd"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["sam@voorbeeld.nl"])
        self.assertIn("Je gebruikersnaam is: sam", mail.outbox[0].body)
        self.assertIn("/wachtwoord-herstellen/", mail.outbox[0].body)
        self.assertNotIn("\n", mail.outbox[0].subject)

    def test_nieuw_wachtwoord_zetten_en_inloggen(self):
        self.aanvragen("sam@voorbeeld.nl")
        link = self.link_uit_mail()
        # Django stuurt eerst door naar een adres zonder token in de url
        antwoord = self.client.get(link, follow=True)
        self.assertContains(antwoord, "Nieuw wachtwoord")
        formulieradres = antwoord.redirect_chain[-1][0]
        antwoord = self.client.post(
            formulieradres, {"new_password1": "zomertuin2026", "new_password2": "zomertuin2026"}
        )
        self.assertRedirects(antwoord, reverse("wachtwoord_klaar"))
        self.assertTrue(self.client.login(username="sam", password="zomertuin2026"))
        self.assertFalse(self.client.login(username="sam", password="oudwachtwoord26"))

    def test_link_werkt_maar_een_keer(self):
        self.aanvragen("sam@voorbeeld.nl")
        link = self.link_uit_mail()
        formulieradres = self.client.get(link, follow=True).redirect_chain[-1][0]
        self.client.post(formulieradres, {"new_password1": "zomertuin2026", "new_password2": "zomertuin2026"})
        self.client.logout()
        antwoord = self.client.get(link, follow=True)
        self.assertContains(antwoord, "Deze link werkt niet meer")

    def test_te_zwak_wachtwoord_wordt_geweigerd(self):
        self.aanvragen("sam@voorbeeld.nl")
        formulieradres = self.client.get(self.link_uit_mail(), follow=True).redirect_chain[-1][0]
        antwoord = self.client.post(formulieradres, {"new_password1": "1234", "new_password2": "1234"})
        self.assertEqual(antwoord.status_code, 200)
        self.sam.refresh_from_db()
        self.assertTrue(self.sam.check_password("oudwachtwoord26"))
        self.assertContains(antwoord, "Minstens 8 tekens")

    def test_onbekend_adres_zelfde_pagina_geen_mail(self):
        from django.core import mail
        antwoord = self.aanvragen("niemand@voorbeeld.nl")
        self.assertRedirects(antwoord, reverse("wachtwoord_verstuurd"))
        self.assertEqual(len(mail.outbox), 0)

    def test_uit_dienst_krijgt_geen_mail(self):
        from django.core import mail
        self.sam.is_active = False
        self.sam.save()
        self.aanvragen("sam@voorbeeld.nl")
        self.assertEqual(len(mail.outbox), 0)
