"""Notities als gesprek (fase 2): foto's bij een notitie, het groene rondje
met gemiste berichten, en de melding op de telefoon."""

import shutil
from datetime import time, timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from medewerkers.models import Medewerker
from pushberichten.models import Abonnement
from uren.models import Inzet, Uurblok

from . import gesprek
from .models import Bijlage, Klus, Notitie, NotitieGelezen
from .tests import TIJDELIJKE_MEDIA, upload


class GesprekBasis(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.maarten = Medewerker.objects.create_user("maarten", password="x", first_name="Maarten", rol=Medewerker.Rol.EIGENAAR)
        cls.sam = Medewerker.objects.create_user("sam", password="x", first_name="Sam")
        cls.lot = Medewerker.objects.create_user("lot", password="x", first_name="Lot")
        cls.buiten = Medewerker.objects.create_user("joep", password="x", first_name="Joep")
        cls.klus = Klus.objects.create(naam="Tuin Vermeer")
        cls.andere = Klus.objects.create(naam="Vijver Van Leeuwen")
        vandaag = timezone.localdate()
        # Sam staat ingepland, Lot schreef vorige week uren; Joep heeft niets met deze klus.
        Inzet.objects.create(medewerker=cls.sam, klus=cls.klus, datum=vandaag + timedelta(days=2))
        Uurblok.objects.create(medewerker=cls.lot, klus=cls.klus, datum=vandaag - timedelta(days=7), begintijd=time(8), eindtijd=time(12))
        Uurblok.objects.create(medewerker=cls.buiten, klus=cls.andere, datum=vandaag, begintijd=time(8), eindtijd=time(12))

    def schrijf(self, door, tekst="Hek staat open", klus=None):
        return Notitie.objects.create(klus=klus or self.klus, tekst=tekst, geschreven_door=door)


class WieHoortErbijTests(GesprekBasis):
    def test_ingepland_uren_of_zelf_geschreven(self):
        self.schrijf(self.maarten)
        self.assertEqual(set(gesprek.betrokkenen(self.klus)), {self.sam, self.lot, self.maarten})

    def test_oude_uren_tellen_niet_meer(self):
        Uurblok.objects.filter(medewerker=self.lot).update(datum=timezone.localdate() - timedelta(days=60))
        self.assertNotIn(self.lot, gesprek.betrokkenen(self.klus))

    def test_uit_dienst_hoort_er_niet_bij(self):
        Medewerker.objects.filter(pk=self.sam.pk).update(uit_dienst_sinds=timezone.localdate(), is_active=False)
        self.assertNotIn(self.sam, gesprek.betrokkenen(self.klus))


class OngelezenTests(GesprekBasis):
    def test_telt_berichten_van_anderen_op_jouw_klus(self):
        self.schrijf(self.maarten)
        self.schrijf(self.lot, "Haag is 14 meter")
        self.schrijf(self.sam, "Ik ben er morgen")  # eigen bericht telt niet
        self.assertEqual(gesprek.ongelezen_per_klus(self.sam, [self.klus.pk, self.andere.pk]), {self.klus.pk: 2})

    def test_niet_op_een_klus_waar_je_niet_bij_hoort(self):
        self.schrijf(self.maarten)
        self.assertEqual(gesprek.ongelezen_per_klus(self.buiten, [self.klus.pk]), {})

    def test_chat_openen_zet_teller_op_nul(self):
        self.schrijf(self.maarten)
        self.client.force_login(self.sam)
        self.client.get(self.klus.get_absolute_url())
        self.assertEqual(gesprek.ongelezen_per_klus(self.sam, [self.klus.pk]), {self.klus.pk: 1})
        self.client.get(reverse("klus_chat", args=[self.klus.pk]))
        self.assertEqual(gesprek.ongelezen_per_klus(self.sam, [self.klus.pk]), {})
        nieuw = self.schrijf(self.lot, "Nog iets")
        Notitie.objects.filter(pk=nieuw.pk).update(geschreven_op=timezone.now() + timedelta(seconds=5))
        self.assertEqual(gesprek.ongelezen_per_klus(self.sam, [self.klus.pk]), {self.klus.pk: 1})

    def test_groen_rondje_in_klussenlijst_en_op_startscherm(self):
        self.schrijf(self.maarten)
        self.schrijf(self.lot, "Tweede")
        Uurblok.objects.create(medewerker=self.sam, klus=self.klus, datum=timezone.localdate(), begintijd=time(13), eindtijd=time(14))
        self.client.force_login(self.sam)
        for adres in (reverse("klussen"), reverse("start")):
            antwoord = self.client.get(adres)
            self.assertContains(antwoord, 'class="ongelezen-bol"', count=1)
            self.assertContains(antwoord, "2 nieuwe notities")

    def test_meer_dan_negen(self):
        for i in range(12):
            self.schrijf(self.maarten, f"bericht {i}")
        self.client.force_login(self.sam)
        self.assertContains(self.client.get(reverse("klussen")), ">9+<")


class MeldingTests(GesprekBasis):
    def setUp(self):
        for mw in (self.sam, self.lot, self.maarten, self.buiten):
            Abonnement.objects.create(medewerker=mw, endpoint=f"https://push.example/{mw.username}", p256dh="p", auth="a")

    def test_plaatsen_plant_een_melding(self):
        self.client.force_login(self.maarten)
        with patch("klussen.gesprek.plan_melding") as plan:
            self.client.post(reverse("notitie_toevoegen", args=[self.klus.pk]), {"tekst": "Ik bel haar vanmiddag"})
        plan.assert_called_once()
        self.assertEqual(plan.call_args.args[0].tekst, "Ik bel haar vanmiddag")

    def test_melding_naar_betrokkenen_behalve_de_schrijver(self):
        notitie = self.schrijf(self.sam, "Haag is klaar")
        with patch("pushberichten.versturen.stuur", return_value=True) as stuur:
            self.assertEqual(gesprek.meld(notitie.pk), 1)
        ontvangers = {aanroep.args[0].medewerker for aanroep in stuur.call_args_list}
        self.assertEqual(ontvangers, {self.lot})
        abonnement, titel, tekst, url = stuur.call_args.args
        self.assertEqual(titel, "Sam · Tuin Vermeer")
        self.assertEqual(tekst, "Haag is klaar")
        self.assertEqual(url, reverse("klus_chat", args=[self.klus.pk]))

    def test_fout_bij_versturen_laat_niets_crashen(self):
        notitie = self.schrijf(self.maarten)
        with patch("pushberichten.versturen.stuur", side_effect=RuntimeError("weg")):
            self.assertEqual(gesprek.meld(notitie.pk), 0)


@override_settings(MEDIA_ROOT=TIJDELIJKE_MEDIA)
class FotoInNotitieTests(GesprekBasis):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TIJDELIJKE_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.client.force_login(self.sam)
        self.plan = patch("klussen.gesprek.plan_melding").start()
        self.addCleanup(patch.stopall)

    def plaats(self, **velden):
        return self.client.post(reverse("notitie_toevoegen", args=[self.klus.pk]), velden)

    def test_foto_met_tekst_staat_bij_notitie_en_in_media(self):
        self.plaats(tekst="Zo ziet het er nu uit", fotos=[upload("a.jpg"), upload("b.jpg")])
        notitie = Notitie.objects.get()
        self.assertEqual(notitie.fotos.count(), 2)
        self.assertEqual(Bijlage.objects.filter(klus=self.klus, soort=Bijlage.Soort.FOTO).count(), 2)
        self.assertContains(self.client.get(reverse("klus_chat", args=[self.klus.pk])), "chat-fotos aantal-2")

    def test_alleen_een_foto_mag(self):
        self.plaats(tekst="", fotos=[upload()])
        self.assertEqual(Notitie.objects.get().tekst, "")
        self.plan.assert_called_once()

    def test_niets_is_geen_bericht(self):
        self.plaats(tekst="  ")
        self.assertFalse(Notitie.objects.exists())

    def test_document_wordt_geweigerd(self):
        self.plaats(tekst="offerte", fotos=[upload("offerte.pdf", b"%PDF-1.4", "application/pdf")])
        self.assertFalse(Notitie.objects.exists())
        self.assertFalse(Bijlage.objects.exists())

    def test_notitie_weg_foto_blijft(self):
        self.plaats(tekst="weg ermee", fotos=[upload()])
        notitie = Notitie.objects.get()
        self.client.post(reverse("notitie_verwijderen", args=[notitie.pk]))
        self.assertEqual(Bijlage.objects.count(), 1)


class BeginstandTests(TestCase):
    def test_migratie_maakt_geen_dubbele_rijen(self):
        # De unieke regel per klus en persoon houdt update_or_create eerlijk.
        mw = Medewerker.objects.create_user("a", password="x")
        klus = Klus.objects.create(naam="K")
        Notitie.objects.create(klus=klus, tekst="x", geschreven_door=None)
        self.client.force_login(mw)
        self.client.get(reverse("klus_chat", args=[klus.pk]))
        self.client.get(reverse("klus_chat", args=[klus.pk]))
        self.assertEqual(NotitieGelezen.objects.count(), 1)
