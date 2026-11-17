"""Wie er bij een klus hoort (Klus.betrokkenen), en zelf meedoen."""

from datetime import date, time

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from medewerkers.models import Medewerker
from uren.forms import UurblokForm
from uren.models import Uurblok

from . import gesprek
from .models import Klus


class BetrokkenenTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.maarten = Medewerker.objects.create_user("maarten", password="x", first_name="Maarten", rol=Medewerker.Rol.EIGENAAR)
        cls.sam = Medewerker.objects.create_user("sam", password="x", first_name="Sam")
        cls.lot = Medewerker.objects.create_user("lot", password="x", first_name="Lot")
        cls.oud = Medewerker.objects.create_user("piet", password="x", first_name="Piet", uit_dienst_sinds=date(2025, 1, 1), is_active=False)
        cls.klus = Klus.objects.create(naam="Tuin Vermeer", opdrachtgever="Fam. Vermeer", startdatum=date(2026, 9, 14))

    def formulier(self, **afwijkend):
        gegevens = {
            "naam": "Tuin Vermeer", "soort": Klus.Soort.AANLEG, "startdatum": "2026-09-14",
            "opdrachtgever": "Fam. Vermeer", "adres": "Dijkweg 12", "plaats": "Maasdijk",
            "kleur": "#95BF1D", "actief": "True",
        }
        gegevens.update(afwijkend)
        return gegevens

    def bewerk(self, **velden):
        adres = reverse("klus_bewerken", args=[self.klus.pk])
        versie = self.client.get(adres).context["formulier"].initial["versie"]
        antwoord = self.client.post(adres, self.formulier(versie=versie, **velden))
        self.assertEqual(antwoord.status_code, 302, antwoord.context and antwoord.context["formulier"].errors)

    def test_nieuwe_klus_met_betrokkenen(self):
        self.client.force_login(self.maarten)
        self.client.post(reverse("klus_nieuw"), self.formulier(naam="Vijver", betrokkenen=[self.sam.pk, self.lot.pk]))
        self.assertEqual(set(Klus.objects.get(naam="Vijver").betrokkenen.all()), {self.sam, self.lot})

    def test_later_iemand_erbij_zetten(self):
        self.client.force_login(self.maarten)
        self.bewerk(betrokkenen=[self.sam.pk])
        self.assertEqual(list(self.klus.betrokkenen.all()), [self.sam])
        self.assertContains(self.client.get(self.klus.get_absolute_url()), "betrokken-persoon")

    def test_uit_dienst_niet_kiesbaar_maar_blijft_staan_als_hij_er_al_bij_was(self):
        self.client.force_login(self.maarten)
        html = self.client.get(reverse("klus_nieuw")).content.decode()
        self.assertNotIn("Piet", html)
        self.klus.betrokkenen.add(self.oud)
        self.bewerk(betrokkenen=[self.oud.pk, self.sam.pk])
        self.assertIn(self.oud, self.klus.betrokkenen.all())

    def test_betrokkene_krijgt_melding_en_teller(self):
        self.klus.betrokkenen.add(self.lot)
        self.assertIn(self.lot, gesprek.betrokkenen(self.klus))
        self.assertIn(self.klus.pk, gesprek.mijn_klus_ids(self.lot))

    def test_alleen_eigenaar_bewerkt_klus(self):
        self.client.force_login(self.sam)
        antwoord = self.client.post(reverse("klus_bewerken", args=[self.klus.pk]), self.formulier(betrokkenen=[self.sam.pk]))
        self.assertEqual(antwoord.status_code, 404)
        self.assertFalse(self.klus.betrokkenen.exists())


class MeedoenTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sam = Medewerker.objects.create_user("sam", password="x", first_name="Sam")
        cls.klus = Klus.objects.create(naam="Tuin Vermeer")
        cls.afgerond = Klus.objects.create(naam="Oud werk", actief=False)

    def setUp(self):
        self.client.force_login(self.sam)

    def test_meedoen_knop_en_meedoen(self):
        self.assertContains(self.client.get(self.klus.get_absolute_url()), "Meedoen met klus")
        self.client.post(reverse("klus_meedoen", args=[self.klus.pk]))
        self.assertIn(self.sam, self.klus.betrokkenen.all())
        self.assertContains(self.client.get(self.klus.get_absolute_url()), "Niet meer meedoen")

    def test_klus_staat_bij_jouw_klussen_op_startscherm(self):
        self.client.post(reverse("klus_meedoen", args=[self.klus.pk]))
        self.assertIn(self.klus, self.client.get(reverse("start")).context["klussen_recent"])

    def test_klussen_met_uren_eerst_dan_meegedaan(self):
        andere = Klus.objects.create(naam="Andere")
        Uurblok.objects.create(medewerker=self.sam, klus=andere, datum=timezone.localdate(), begintijd=time(8), eindtijd=time(9))
        self.client.post(reverse("klus_meedoen", args=[self.klus.pk]))
        self.assertEqual(self.client.get(reverse("start")).context["klussen_recent"], [andere, self.klus])

    def test_bovenaan_bij_uren_schrijven(self):
        Klus.objects.create(naam="Aaa eerst op alfabet")
        self.client.post(reverse("klus_meedoen", args=[self.klus.pk]))
        formulier = UurblokForm(medewerker=self.sam)
        self.assertEqual(list(formulier.fields["klus"].queryset)[0], self.klus)

    def test_stoppen(self):
        self.klus.betrokkenen.add(self.sam)
        self.client.post(reverse("klus_meedoen", args=[self.klus.pk]), {"doe": "stop"})
        self.assertFalse(self.klus.betrokkenen.exists())

    def test_niet_meedoen_met_afgeronde_klus(self):
        self.client.post(reverse("klus_meedoen", args=[self.afgerond.pk]))
        self.assertFalse(self.afgerond.betrokkenen.exists())
        self.assertNotContains(self.client.get(self.afgerond.get_absolute_url()), "Meedoen met klus")

    def test_alleen_post(self):
        self.assertEqual(self.client.get(reverse("klus_meedoen", args=[self.klus.pk])).status_code, 405)


class VersieMetBetrokkenenTests(TestCase):
    """VersieMixin met een veel-op-veel-veld: iemand die intussen "Meedoen"
    tikt, betekent dat het formulier van de eigenaar verouderd is."""

    def test_gelijktijdig_meedoen_wordt_betrapt(self):
        maarten = Medewerker.objects.create_user("maarten", password="x", first_name="Maarten", rol=Medewerker.Rol.EIGENAAR)
        sam = Medewerker.objects.create_user("sam", password="x", first_name="Sam")
        klus = Klus.objects.create(naam="Tuin", opdrachtgever="Fam.", startdatum=date(2026, 9, 14))
        self.client.force_login(maarten)
        adres = reverse("klus_bewerken", args=[klus.pk])
        versie = self.client.get(adres).context["formulier"].initial["versie"]
        klus.betrokkenen.add(sam)
        antwoord = self.client.post(adres, {
            "naam": "Tuin", "soort": Klus.Soort.AANLEG, "startdatum": "2026-09-14", "opdrachtgever": "Fam.",
            "kleur": "#95BF1D", "actief": "True", "versie": versie,
        })
        self.assertEqual(antwoord.status_code, 200)
        self.assertIn(sam, klus.betrokkenen.all())
