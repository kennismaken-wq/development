import json
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from medewerkers.models import Medewerker

from .models import BesteScore
from .scorebord import ranglijst
from .views import MAX_PUNTEN_PER_SECONDE


class SpelTestBasis(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.maarten = Medewerker.objects.create_user(
            "maarten", password="test1234", first_name="Maarten", rol=Medewerker.Rol.EIGENAAR
        )
        cls.sam = Medewerker.objects.create_user(
            "sam", password="test1234", first_name="Sam", rol=Medewerker.Rol.MEDEWERKER
        )

    def setUp(self):
        self.client.force_login(self.sam)

    def start(self, om=1000.0):
        with patch("spel.views.time.time", return_value=om):
            return self.client.post(reverse("spel_start"))

    def stuur(self, gegevens, om=1100.0):
        with patch("spel.views.time.time", return_value=om):
            return self.client.post(
                reverse("spel_score"),
                gegevens if isinstance(gegevens, str) else json.dumps(gegevens),
                content_type="application/json",
            )

    def speel(self, punten):
        self.start()
        return self.stuur({"punten": punten})

    def beste_van(self, medewerker):
        return BesteScore.objects.get(medewerker=medewerker).punten


class ToegangTest(SpelTestBasis):
    def test_zonder_inloggen_naar_inloggen(self):
        self.client.logout()
        for antwoord in (
            self.client.get(reverse("spel")),
            self.client.post(reverse("spel_start")),
            self.client.post(reverse("spel_score"), "{}", content_type="application/json"),
        ):
            self.assertEqual(antwoord.status_code, 302)
            self.assertIn(reverse("inloggen"), antwoord["Location"])
        self.assertFalse(BesteScore.objects.exists())

    def test_pagina_voor_medewerker_en_eigenaar(self):
        self.assertEqual(self.client.get(reverse("spel")).status_code, 200)
        self.client.force_login(self.maarten)
        self.assertEqual(self.client.get(reverse("spel")).status_code, 200)

    def test_pagina_laat_besturing_kiezen(self):
        antwoord = self.client.get(reverse("spel"))
        self.assertContains(antwoord, 'data-besturing="tikken"')
        self.assertContains(antwoord, 'data-besturing="kantelen"')

    def test_start_en_score_alleen_post(self):
        self.assertEqual(self.client.get(reverse("spel_start")).status_code, 405)
        self.assertEqual(self.client.get(reverse("spel_score")).status_code, 405)


class ScoreOpslaanTest(SpelTestBasis):
    def test_score_komt_op_naam_van_ingelogde(self):
        antwoord = self.speel(120)
        self.assertEqual(antwoord.status_code, 200)
        self.assertEqual(self.beste_van(self.sam), 120)
        self.assertTrue(antwoord.json()["nieuw_record"])

    def test_meegestuurd_id_telt_niet(self):
        self.start()
        self.stuur({"punten": 50, "medewerker": self.maarten.pk})
        self.assertEqual(self.beste_van(self.sam), 50)
        self.assertFalse(BesteScore.objects.filter(medewerker=self.maarten).exists())

    def test_lagere_score_overschrijft_niet(self):
        self.speel(300)
        antwoord = self.speel(100)
        self.assertEqual(self.beste_van(self.sam), 300)
        self.assertFalse(antwoord.json()["nieuw_record"])
        self.assertEqual(antwoord.json()["beste"], 300)

    def test_hogere_score_overschrijft(self):
        self.speel(100)
        antwoord = self.speel(300)
        self.assertEqual(self.beste_van(self.sam), 300)
        self.assertTrue(antwoord.json()["nieuw_record"])

    def test_score_nul_komt_niet_op_het_bord(self):
        antwoord = self.speel(0)
        self.assertEqual(antwoord.status_code, 200)
        self.assertFalse(BesteScore.objects.exists())

    def test_antwoord_bevat_ververst_scorebord(self):
        self.assertIn("Sam", self.speel(77).json()["scorebord"])


class ScoreWeigerenTest(SpelTestBasis):
    def test_zonder_start(self):
        self.assertEqual(self.stuur({"punten": 10}).status_code, 400)
        self.assertFalse(BesteScore.objects.exists())

    def test_een_start_is_een_score(self):
        self.speel(10)
        self.assertEqual(self.stuur({"punten": 20}).status_code, 400)
        self.assertEqual(self.beste_van(self.sam), 10)

    def test_onmogelijke_score(self):
        self.start(om=1000.0)
        te_veel = 10 * MAX_PUNTEN_PER_SECONDE
        self.assertEqual(self.stuur({"punten": te_veel}, om=1001.0).status_code, 400)
        self.assertFalse(BesteScore.objects.exists())

    def test_vlak_onder_de_grens_mag(self):
        self.start(om=1000.0)
        self.assertEqual(self.stuur({"punten": 3 * MAX_PUNTEN_PER_SECONDE}, om=1001.0).status_code, 200)

    def test_ongeldige_waarden(self):
        for waarde in (-1, 1.5, "100", True, None, 10_000_000):
            with self.subTest(waarde=waarde):
                self.start()
                self.assertEqual(self.stuur({"punten": waarde}).status_code, 400)
        self.assertFalse(BesteScore.objects.exists())

    def test_kapotte_json(self):
        for inhoud in ("geen json", "[1]", "{}"):
            with self.subTest(inhoud=inhoud):
                self.start()
                self.assertEqual(self.stuur(inhoud).status_code, 400)


class RanglijstTest(SpelTestBasis):
    def zet(self, medewerker, punten, op=None):
        return BesteScore.objects.create(medewerker=medewerker, punten=punten, behaald_op=op or timezone.now())

    def test_hoogste_eerst_en_eigenaar_doet_mee(self):
        self.zet(self.sam, 10)
        self.zet(self.maarten, 20)
        self.assertEqual([r.medewerker for r in ranglijst()], [self.maarten, self.sam])

    def test_bij_gelijke_stand_wie_het_eerst_was(self):
        nu = timezone.now()
        self.zet(self.sam, 10, nu)
        self.zet(self.maarten, 10, nu - timedelta(days=1))
        self.assertEqual([r.medewerker for r in ranglijst()], [self.maarten, self.sam])

    def test_uit_dienst_niet_op_het_bord(self):
        self.zet(self.sam, 10)
        Medewerker.objects.filter(pk=self.sam.pk).update(is_active=False)
        self.assertFalse(ranglijst().exists())

    def test_uit_dienst_sinds_niet_op_het_bord(self):
        self.zet(self.sam, 10)
        Medewerker.objects.filter(pk=self.sam.pk).update(uit_dienst_sinds=timezone.localdate())
        self.assertFalse(ranglijst().exists())

    def test_verborgen_account_niet_op_het_bord(self):
        verborgen = Medewerker.alle.create_user("admin", password="test1234", verborgen=True)
        self.zet(verborgen, 999)
        self.assertFalse(ranglijst().exists())


class VlaggenTest(SpelTestBasis):
    def test_pagina_bevat_vlaggen_van_collegas_en_jezelf(self):
        BesteScore.objects.create(medewerker=self.maarten, punten=500, behaald_op=timezone.now())
        BesteScore.objects.create(medewerker=self.sam, punten=200, behaald_op=timezone.now())
        vlaggen = self.client.get(reverse("spel")).context["vlaggen"]
        self.assertEqual([(v["naam"], v["punten"], v["ik"]) for v in vlaggen], [("Maarten", 500, False), ("Sam", 200, True)])

    def test_antwoord_op_score_bevat_nieuwe_vlag(self):
        vlaggen = self.speel(150).json()["vlaggen"]
        self.assertEqual([(v["punten"], v["ik"]) for v in vlaggen], [(150, True)])

    def test_uit_dienst_krijgt_geen_vlag(self):
        BesteScore.objects.create(medewerker=self.maarten, punten=500, behaald_op=timezone.now())
        Medewerker.objects.filter(pk=self.maarten.pk).update(is_active=False)
        self.assertEqual(self.client.get(reverse("spel")).context["vlaggen"], [])


class IngangTest(SpelTestBasis):
    def test_icoon_op_startscherm_buiten_de_navigatie(self):
        html = self.client.get(reverse("start")).content.decode()
        self.assertIn('class="spel-ingang"', html)
        navigatie = html[html.index("<nav"):html.index("</nav>")]
        self.assertNotIn(reverse("spel"), navigatie)
