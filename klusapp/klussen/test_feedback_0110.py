"""Feedback uit het gesprek met Maarten van 01-10-2026, voor zover het in de
app klussen landt: afschermen van een document, Aanleg/Onderhoud,
Actief/Afgerond en zoeken op plaats. Los van tests.py zodat dit niet botst met
ander werk aan dat bestand."""

import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from medewerkers.models import Medewerker

from .forms import BijlageForm, KlusForm
from .models import Bijlage, Klus

MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA)
class DocumentAfschermenTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.voorman = Medewerker.objects.create_user("henk", password="x", first_name="Henk")
        cls.sam = Medewerker.objects.create_user("sam", password="x", first_name="Sam")
        cls.maarten = Medewerker.objects.create_user(
            "maarten", password="x", first_name="Maarten", rol=Medewerker.Rol.EIGENAAR
        )
        cls.klus = Klus.objects.create(naam="Tuin Vermeer")

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def upload(self, door, zichtbaar_voor=(), document=True):
        self.client.force_login(door)
        gegevens = {
            "klus": self.klus.pk,
            "bestanden": SimpleUploadedFile("offerte.txt", b"prijs: 1200 euro"),
            "zichtbaar_voor": [m.pk for m in zichtbaar_voor],
        }
        if document:
            gegevens["forceer_document"] = "1"
        self.client.post(reverse("bijlage_toevoegen"), gegevens)
        return Bijlage.objects.latest("pk")

    def test_eigenaar_schermt_offerte_af_voor_de_voorman(self):
        offerte = self.upload(self.maarten, [self.voorman])
        self.assertEqual(list(offerte.zichtbaar_voor.all()), [self.voorman])

        url = reverse("media_bestand", args=[offerte.bestand.name])
        self.client.force_login(self.voorman)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertContains(self.client.get(self.klus.get_absolute_url()), "offerte.txt")

        self.client.force_login(self.sam)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertNotContains(self.client.get(self.klus.get_absolute_url()), "offerte.txt")

    def test_niemand_aangevinkt_is_iedereen(self):
        tekening = self.upload(self.maarten)
        self.client.force_login(self.sam)
        self.assertEqual(self.client.get(reverse("media_bestand", args=[tekening.bestand.name])).status_code, 200)

    def test_medewerker_kan_niet_afschermen(self):
        # Het veld staat bij hem niet in beeld; ook met de hand gepost telt het niet.
        bestand = self.upload(self.sam, [self.voorman])
        self.assertFalse(bestand.zichtbaar_voor.exists())

    def test_eigenaar_ziet_altijd_alles(self):
        offerte = self.upload(self.maarten, [self.voorman])
        self.assertTrue(offerte.mag_zien(self.maarten))
        self.assertIn(offerte, Bijlage.objects.zichtbaar_voor(self.maarten))

    def test_wie_het_toevoegde_ziet_het_ook(self):
        offerte = Bijlage.objects.create(klus=self.klus, soort="document", toegevoegd_door=self.sam)
        offerte.zichtbaar_voor.set([self.voorman])
        self.assertIn(offerte, Bijlage.objects.zichtbaar_voor(self.sam))
        self.assertTrue(offerte.mag_zien(self.sam))

    def test_keuzelijst_alleen_medewerkers_in_dienst(self):
        from datetime import date

        weg = Medewerker.objects.create_user("oud", password="x", uit_dienst_sinds=date(2026, 1, 1))
        keuzes = list(BijlageForm().fields["zichtbaar_voor"].queryset)
        self.assertIn(self.voorman, keuzes)
        self.assertNotIn(self.maarten, keuzes)
        self.assertNotIn(weg, keuzes)

    def test_slotje_met_namen_voor_de_eigenaar(self):
        self.upload(self.maarten, [self.voorman])
        antwoord = self.client.get(self.klus.get_absolute_url())
        self.assertContains(antwoord, "Alleen Henk")


class ZichtbaarVoorBijNieuweKlusTest(TestCase):
    def test_kopje_en_avatars(self):
        Medewerker.objects.create_user("henk", password="x", first_name="Henk", last_name="Bos")
        self.client.force_login(
            Medewerker.objects.create_user("maarten", password="x", rol=Medewerker.Rol.EIGENAAR)
        )
        antwoord = self.client.get(reverse("klus_nieuw"))
        self.assertContains(antwoord, "Technische documenten zichtbaar voor:")
        self.assertContains(antwoord, 'class="zv-bol"')
        self.assertContains(antwoord, ">HB</span>\nHenk Bos")


class AanlegEnStaatTest(TestCase):
    def test_staat_als_keuzepillen_actief_en_afgerond(self):
        html = KlusForm().as_p()
        self.assertIn('type="radio" name="actief" value="True"', html)
        self.assertIn("Afgerond", html)

    def test_bestaande_klus_staat_op_de_goede_pil(self):
        klus = Klus.objects.create(naam="Oud", actief=False)
        html = str(KlusForm(instance=klus)["actief"])
        self.assertIn('value="False" checked', html.replace('\n', ' ').replace('  ', ' ')) if 'value="False" checked' in html else self.assertRegex(html, r'value="False"[^>]*checked')

    def test_afgerond_opslaan_maakt_klus_inactief(self):
        gegevens = {
            "naam": "Tuin", "soort": "onderhoud", "opdrachtgever": "Van E",
            "adres": "", "plaats": "", "beschrijving": "", "kleur": "#95bf1d", "actief": "False",
        }
        klus = Klus.objects.create(naam="Tuin", opdrachtgever="Van E")
        formulier = KlusForm(gegevens, instance=klus)
        self.assertTrue(formulier.is_valid(), formulier.errors)
        self.assertFalse(formulier.save().actief)


class ZoekenOpPlaatsTest(TestCase):
    def test_kiezer_kent_opdrachtgever_adres_en_plaats(self):
        klus = Klus.objects.create(naam="Onderhoud", opdrachtgever="Van E", adres="Kerkstraat 4", plaats="Leiden")
        from uren.forms import UurblokForm

        html = str(UurblokForm()["klus"])
        self.assertIn('data-zoek="Onderhoud Van E Kerkstraat 4, Leiden"', html)
        self.assertIn('data-waar="Kerkstraat 4, Leiden"', html)
        self.assertIn(f'value="{klus.pk}"', html)


class VanEeTest(TestCase):
    """Derde tab naast Aanleg en Onderhoud (gesprek Maarten, 01-10-2026)."""

    def setUp(self):
        self.client.force_login(
            Medewerker.objects.create_user("maarten", password="x", rol=Medewerker.Rol.EIGENAAR)
        )

    def test_keuze_bij_nieuwe_klus(self):
        html = str(KlusForm()["soort"])
        for label in ("Aanleg", "Onderhoud", "Van Ee"):
            self.assertIn(label, html)

    def test_eigen_tab_op_het_klussenoverzicht(self):
        Klus.objects.create(naam="Werkbon Kerkstraat", soort=Klus.Soort.VAN_EE, opdrachtgever="Van Ee")
        Klus.objects.create(naam="Tuin Vermeer", soort=Klus.Soort.AANLEG)
        antwoord = self.client.get(reverse("klussen"), {"soort": "van_ee"})
        self.assertContains(antwoord, "Werkbon Kerkstraat")
        self.assertNotContains(antwoord, "Tuin Vermeer")

    def test_van_ee_vraagt_een_startdatum_zoals_aanleg(self):
        formulier = KlusForm({"naam": "Werkbon", "soort": "van_ee", "opdrachtgever": "Van Ee", "actief": "True"})
        self.assertFalse(formulier.is_valid())
        self.assertIn("startdatum", formulier.errors)

    def test_van_ee_zet_de_opdrachtgever_zelf(self):
        formulier = KlusForm({
            "naam": "Werkbon", "soort": "van_ee", "opdrachtgever": "", "adres": "Kerkstraat 4",
            "startdatum": "2026-10-05", "actief": "True",
        })
        self.assertTrue(formulier.is_valid(), formulier.errors)
        self.assertEqual(formulier.cleaned_data["opdrachtgever"], "Van Ee")

    def test_van_ee_vraagt_een_uitvoeradres(self):
        formulier = KlusForm({
            "naam": "Werkbon", "soort": "van_ee", "startdatum": "2026-10-05", "actief": "True",
        })
        self.assertFalse(formulier.is_valid())
        self.assertEqual(formulier.errors["adres"], ["Vul het uitvoeradres in."])
        self.assertNotIn("opdrachtgever", formulier.errors)

    def test_aanleg_vraagt_nog_steeds_een_opdrachtgever(self):
        formulier = KlusForm({
            "naam": "Tuin", "soort": "aanleg", "startdatum": "2026-10-05", "actief": "True",
        })
        self.assertFalse(formulier.is_valid())
        self.assertIn("opdrachtgever", formulier.errors)
