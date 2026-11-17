import shutil
import tempfile
from datetime import date, time

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from klussen.models import Bijlage, Klus
from medewerkers.models import Medewerker
from spel.models import BesteScore
from uren.models import Uurblok


class OnsTeamTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.maarten = Medewerker.objects.create_user(
            "maarten", password="x", first_name="Maarten", rol=Medewerker.Rol.EIGENAAR
        )
        cls.sam = Medewerker.objects.create_user(
            "sam", password="x", first_name="Sam", functie="Hovenier", telefoon="0612345678",
            geboortedatum=date(1994, 3, 14), in_dienst_sinds=date(2021, 3, 1), adres="Dijkweg 12",
        )
        cls.lot = Medewerker.objects.create_user("lot", password="x", first_name="Lot")
        cls.oud = Medewerker.objects.create_user(
            "piet", password="x", first_name="Piet", uit_dienst_sinds=date(2025, 6, 1), is_active=False
        )
        cls.verborgen = Medewerker.objects.create_user("handigerai", password="x", first_name="Beheer")
        Medewerker.alle.filter(pk=cls.verborgen.pk).update(verborgen=True)

        cls.tuin = Klus.objects.create(naam="Tuin Vermeer")
        cls.terrein = Klus.objects.create(naam="Bedrijfsterrein Noord", soort=Klus.Soort.ONDERHOUD)
        Uurblok.objects.create(medewerker=cls.sam, klus=cls.tuin, datum=date(2026, 11, 2), begintijd=time(8), eindtijd=time(16, 30))
        Uurblok.objects.create(medewerker=cls.sam, klus=cls.terrein, datum=date(2026, 11, 3), begintijd=time(8), eindtijd=time(12))
        Uurblok.objects.create(medewerker=cls.lot, klus=cls.tuin, datum=date(2026, 11, 2), begintijd=time(8), eindtijd=time(10))
        BesteScore.objects.create(medewerker=cls.sam, punten=420, behaald_op=timezone.now())
        BesteScore.objects.create(medewerker=cls.lot, punten=900, behaald_op=timezone.now())

    def test_lijst_toont_collegas_en_oud_collegas_maar_geen_beheeraccount(self):
        self.client.force_login(self.lot)
        html = self.client.get(reverse("team")).content.decode()
        self.assertIn("Sam", html)
        self.assertIn("Oud-collega", html)
        self.assertIn("Piet", html)
        self.assertNotIn("Beheer", html)

    def test_inloggen_verplicht(self):
        antwoord = self.client.get(reverse("team_persoon", args=[self.sam.pk]))
        self.assertEqual(antwoord.status_code, 302)

    def test_persoon_klussen_en_score(self):
        self.client.force_login(self.lot)
        antwoord = self.client.get(reverse("team_persoon", args=[self.sam.pk]))
        self.assertEqual(antwoord.status_code, 200)
        self.assertEqual([r["klus"] for r in antwoord.context["klussen"]], [self.terrein, self.tuin])
        self.assertEqual(antwoord.context["beste"].punten, 420)
        self.assertEqual(antwoord.context["plaats"], 2)

    def test_collega_ziet_geen_uren_van_een_ander(self):
        self.client.force_login(self.lot)
        antwoord = self.client.get(reverse("team_persoon", args=[self.sam.pk]))
        self.assertFalse(antwoord.context["mag_uren_zien"])
        self.assertNotContains(antwoord, "uur gewerkt")
        self.assertNotContains(antwoord, "12,5")

    def test_eigenaar_en_jijzelf_zien_de_uren(self):
        for kijker in (self.maarten, self.sam):
            self.client.force_login(kijker)
            antwoord = self.client.get(reverse("team_persoon", args=[self.sam.pk]))
            self.assertContains(antwoord, "uur gewerkt")
            self.assertContains(antwoord, "12,5")

    def test_mobiel_verjaardag_en_startdatum_zonder_adres_of_geboortejaar(self):
        self.client.force_login(self.lot)
        antwoord = self.client.get(reverse("team_persoon", args=[self.sam.pk]))
        self.assertContains(antwoord, 'href="tel:0612345678"')
        self.assertContains(antwoord, "14 maart")
        self.assertNotContains(antwoord, "1994")
        self.assertContains(antwoord, "sinds 1 maart 2021")
        self.assertNotContains(antwoord, "Dijkweg 12")

    def test_uren_sinds_eerste_invoer(self):
        self.client.force_login(self.sam)
        antwoord = self.client.get(reverse("team_persoon", args=[self.sam.pk]))
        self.assertEqual(antwoord.context["uren_sinds"], date(2026, 11, 2))
        self.assertContains(antwoord, "uur gewerkt sinds 2 nov 2026")

    def test_geboortedatum_invullen_op_eigen_profiel_en_door_eigenaar(self):
        from medewerkers.forms import EigenGegevensForm, MedewerkerForm
        self.assertIn("geboortedatum", EigenGegevensForm.base_fields)
        self.assertIn("geboortedatum", MedewerkerForm.base_fields)

    def test_oud_collega_heeft_een_pagina(self):
        self.client.force_login(self.lot)
        self.assertEqual(self.client.get(reverse("team_persoon", args=[self.oud.pk])).status_code, 200)

    def test_beheeraccount_geen_pagina(self):
        self.client.force_login(self.lot)
        self.assertEqual(self.client.get(reverse("team_persoon", args=[self.verborgen.pk])).status_code, 404)

    def test_tegel_op_startscherm(self):
        self.client.force_login(self.lot)
        self.assertContains(self.client.get(reverse("start")), reverse("team"))


TIJDELIJKE_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TIJDELIJKE_MEDIA)
class OnsTeamMediaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sam = Medewerker.objects.create_user("sam", password="x", first_name="Sam")
        cls.lot = Medewerker.objects.create_user("lot", password="x", first_name="Lot")
        cls.klus = Klus.objects.create(naam="Tuin Vermeer")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TIJDELIJKE_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def foto(self, door, toelichting):
        return Bijlage.objects.create(
            bestand=SimpleUploadedFile("f.jpg", b"x", content_type="image/jpeg"),
            toegevoegd_door=door, klus=self.klus, toelichting=toelichting,
        )

    def test_alleen_fotos_van_die_persoon_en_zonder_uploadknop(self):
        self.foto(self.sam, "haag van sam")
        self.foto(self.lot, "vijver van lot")
        self.client.force_login(self.lot)
        antwoord = self.client.get(reverse("team_persoon", args=[self.sam.pk]))
        self.assertContains(antwoord, "haag van sam")
        self.assertNotContains(antwoord, "vijver van lot")
        self.assertNotContains(antwoord, "fotokaart-nieuw")

    def test_afgeschermde_foto_blijft_afgeschermd(self):
        prive = self.foto(self.sam, "offerte met prijzen")
        prive.zichtbaar_voor.add(self.sam)
        self.client.force_login(self.lot)
        self.assertNotContains(self.client.get(reverse("team_persoon", args=[self.sam.pk])), "offerte met prijzen")
