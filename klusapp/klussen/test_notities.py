"""Notities in het klusdossier. Los van tests.py zodat dit niet botst met
ander werk aan dat bestand."""

from django.test import TestCase
from django.urls import reverse

from medewerkers.models import Medewerker

from .models import Klus, Notitie


class NotitieTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sam = Medewerker.objects.create_user("sam", password="x", first_name="Sam")
        cls.joep = Medewerker.objects.create_user("joep", password="x", first_name="Joep")
        cls.maarten = Medewerker.objects.create_user(
            "maarten", password="x", first_name="Maarten", rol=Medewerker.Rol.EIGENAAR
        )
        cls.klus = Klus.objects.create(naam="Tuin Vermeer")

    def setUp(self):
        self.client.force_login(self.sam)

    def test_medewerker_schrijft_notitie(self):
        antwoord = self.client.post(
            reverse("notitie_toevoegen", args=[self.klus.pk]), {"tekst": "  Hek staat open  "}
        )
        self.assertRedirects(antwoord, reverse("klus_chat", args=[self.klus.pk]) + "#onder", fetch_redirect_response=False)
        notitie = Notitie.objects.get()
        self.assertEqual(notitie.tekst, "Hek staat open")
        self.assertEqual(notitie.geschreven_door, self.sam)

    def test_lege_notitie_wordt_niet_opgeslagen(self):
        self.client.post(reverse("notitie_toevoegen", args=[self.klus.pk]), {"tekst": "   "})
        self.assertFalse(Notitie.objects.exists())

    def test_te_lange_notitie_wordt_niet_opgeslagen(self):
        self.client.post(reverse("notitie_toevoegen", args=[self.klus.pk]), {"tekst": "x" * 2001})
        self.assertFalse(Notitie.objects.exists())

    def test_alleen_post(self):
        self.assertEqual(self.client.get(reverse("notitie_toevoegen", args=[self.klus.pk])).status_code, 405)

    def test_inloggen_vereist(self):
        self.client.logout()
        antwoord = self.client.post(reverse("notitie_toevoegen", args=[self.klus.pk]), {"tekst": "x"})
        self.assertEqual(antwoord.status_code, 302)
        self.assertFalse(Notitie.objects.exists())

    def test_nieuwste_onderaan_in_de_chat(self):
        # Sinds 17-11-2026 een chat zoals WhatsApp: oudste boven, nieuwste onder.
        Notitie.objects.create(klus=self.klus, tekst="Eerste", geschreven_door=self.sam)
        Notitie.objects.create(klus=self.klus, tekst="Tweede", geschreven_door=self.joep)
        html = self.client.get(reverse("klus_chat", args=[self.klus.pk])).content.decode()
        self.assertLess(html.index("Eerste"), html.index("Tweede"))

    def test_andermans_notitie_niet_verwijderen(self):
        notitie = Notitie.objects.create(klus=self.klus, tekst="Van Joep", geschreven_door=self.joep)
        antwoord = self.client.post(reverse("notitie_verwijderen", args=[notitie.pk]))
        self.assertEqual(antwoord.status_code, 404)
        self.assertTrue(Notitie.objects.filter(pk=notitie.pk).exists())

    def test_eigen_notitie_verwijderen(self):
        notitie = Notitie.objects.create(klus=self.klus, tekst="Van Sam", geschreven_door=self.sam)
        self.client.post(reverse("notitie_verwijderen", args=[notitie.pk]))
        self.assertFalse(Notitie.objects.exists())

    def test_ook_eigenaar_verwijdert_alleen_eigen_berichten(self):
        # Sinds 17-11-2026: alleen je eigen bericht, ook als eigenaar.
        notitie = Notitie.objects.create(klus=self.klus, tekst="Van Joep", geschreven_door=self.joep)
        self.client.force_login(self.maarten)
        antwoord = self.client.post(reverse("notitie_verwijderen", args=[notitie.pk]))
        self.assertEqual(antwoord.status_code, 404)
        self.assertTrue(Notitie.objects.filter(pk=notitie.pk).exists())
        html = self.client.get(reverse("klus_chat", args=[self.klus.pk])).content.decode()
        self.assertNotIn(reverse("notitie_verwijderen", args=[notitie.pk]), html)

    def test_bericht_zonder_schrijver_kan_niemand_weghalen(self):
        notitie = Notitie.objects.create(klus=self.klus, tekst="Van niemand", geschreven_door=None)
        self.client.force_login(self.maarten)
        self.assertEqual(self.client.post(reverse("notitie_verwijderen", args=[notitie.pk])).status_code, 404)
