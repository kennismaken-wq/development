"""De chat per klus als WhatsApp (klussen/chat.py), en de bevindingen van de
stresstest van 17-11-2026."""

import os
import shutil
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from medewerkers.models import Medewerker
from medewerkers.views import SESSIE_WISSEL

from . import gesprek
from .models import Bijlage, Klus, Notitie
from .tests import TIJDELIJKE_MEDIA, upload

CHAT = {"HTTP_X_CHAT": "1"}


class ChatBasis(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.maarten = Medewerker.objects.create_user("maarten", password="x", first_name="Maarten", rol=Medewerker.Rol.EIGENAAR)
        cls.sam = Medewerker.objects.create_user("sam", password="x", first_name="Sam")
        cls.lot = Medewerker.objects.create_user("lot", password="x", first_name="Lot")
        cls.klus = Klus.objects.create(naam="Tuin Vermeer")
        cls.klus.betrokkenen.add(cls.sam, cls.lot)

    def setUp(self):
        self.client.force_login(self.sam)
        self.plan = patch("klussen.gesprek.plan_melding").start()
        self.addCleanup(patch.stopall)

    def stuur(self, **velden):
        return self.client.post(reverse("notitie_toevoegen", args=[self.klus.pk]), velden, **CHAT)


class ChatSchermTests(ChatBasis):
    def test_eigen_rechts_anderen_links_met_naam(self):
        Notitie.objects.create(klus=self.klus, tekst="Van Lot", geschreven_door=self.lot)
        Notitie.objects.create(klus=self.klus, tekst="Van Sam", geschreven_door=self.sam)
        html = self.client.get(reverse("klus_chat", args=[self.klus.pk])).content.decode()
        self.assertIn('class="chat-bericht eigen', html)
        self.assertIn('class="chat-naam"', html)
        self.assertIn("Vandaag", html)

    def test_doorloop_bij_zelfde_persoon_kort_na_elkaar(self):
        Notitie.objects.create(klus=self.klus, tekst="een", geschreven_door=self.lot)
        Notitie.objects.create(klus=self.klus, tekst="twee", geschreven_door=self.lot)
        html = self.client.get(reverse("klus_chat", args=[self.klus.pk])).content.decode()
        self.assertEqual(html.count('class="chat-naam"'), 1)
        self.assertIn("doorloop", html)

    def test_dossier_heeft_chatkaart_met_teller(self):
        Notitie.objects.create(klus=self.klus, tekst="Hek staat open", geschreven_door=self.lot)
        antwoord = self.client.get(self.klus.get_absolute_url())
        self.assertContains(antwoord, reverse("klus_chat", args=[self.klus.pk]))
        self.assertContains(antwoord, "Hek staat open")
        self.assertContains(antwoord, "1 nieuwe bericht")

    def test_tekst_wordt_ge_escaped(self):
        Notitie.objects.create(klus=self.klus, tekst="<script>alert(1)</script>", geschreven_door=self.lot)
        self.assertNotContains(self.client.get(reverse("klus_chat", args=[self.klus.pk])), "<script>alert(1)")


class VersturenTests(ChatBasis):
    def test_versturen_geeft_ballon_terug(self):
        antwoord = self.stuur(tekst="Ik ben er om acht", sleutel="abcdef123456")
        self.assertEqual(antwoord.status_code, 200)
        data = antwoord.json()
        self.assertIn("Ik ben er om acht", data["html"])
        self.assertIn("eigen", data["html"])
        self.plan.assert_called_once()

    def test_zelfde_sleutel_is_een_bericht(self):
        eerste = self.stuur(tekst="Hoi", sleutel="abcdef123456").json()
        tweede = self.stuur(tekst="Hoi", sleutel="abcdef123456").json()
        self.assertEqual(eerste["pk"], tweede["pk"])
        self.assertEqual(Notitie.objects.count(), 1)
        self.plan.assert_called_once()

    def test_fout_geeft_400_met_uitleg(self):
        antwoord = self.stuur(tekst="  ", sleutel="abcdef123456")
        self.assertEqual(antwoord.status_code, 400)
        self.assertIn("fout", antwoord.json())

    def test_nieuw_bijladen(self):
        eerste = Notitie.objects.create(klus=self.klus, tekst="oud", geschreven_door=self.lot)
        tweede = Notitie.objects.create(klus=self.klus, tekst="nieuw", geschreven_door=self.lot)
        data = self.client.get(reverse("klus_chat_nieuw", args=[self.klus.pk]), {"na": eerste.pk, "van": eerste.pk}).json()
        self.assertIn("nieuw", data["html"])
        self.assertNotIn(">oud<", data["html"])
        self.assertEqual(data["laatste"], tweede.pk)
        self.assertEqual(data["nog_er"], [eerste.pk, tweede.pk])

    def test_bijladen_markeert_alleen_als_zichtbaar(self):
        Notitie.objects.create(klus=self.klus, tekst="x", geschreven_door=self.lot)
        url = reverse("klus_chat_nieuw", args=[self.klus.pk])
        self.client.get(url, {"na": 0})
        self.assertEqual(gesprek.ongelezen_per_klus(self.sam, [self.klus.pk]), {self.klus.pk: 1})
        self.client.get(url, {"na": 0, "zichtbaar": "1"})
        self.assertEqual(gesprek.ongelezen_per_klus(self.sam, [self.klus.pk]), {})

    def test_verwijderen_via_chat(self):
        notitie = Notitie.objects.create(klus=self.klus, tekst="weg", geschreven_door=self.sam)
        antwoord = self.client.post(reverse("notitie_verwijderen", args=[notitie.pk]), **CHAT)
        self.assertEqual(antwoord.json(), {"weg": notitie.pk})
        self.assertFalse(Notitie.objects.exists())

    def test_onzin_in_na_en_van(self):
        url = reverse("klus_chat_nieuw", args=[self.klus.pk])
        for waarde in ("abc", "-1", "9" * 30):
            self.assertEqual(self.client.get(url, {"na": waarde, "van": waarde}).status_code, 200)


@override_settings(MEDIA_ROOT=TIJDELIJKE_MEDIA)
class FotoTests(ChatBasis):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TIJDELIJKE_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def test_dubbel_versturen_met_foto_is_een_bericht(self):
        # Stresstest 17-11-2026, bevinding 1: met een foto erbij stonden er twee.
        for _ in range(2):
            self.stuur(tekst="Zo staat het nu", fotos=[upload("a.jpg")], sleutel="sleutel-123456")
        self.assertEqual(Notitie.objects.count(), 1)
        self.assertEqual(Bijlage.objects.count(), 1)
        self.plan.assert_called_once()

    def test_heic_krijgt_de_goede_uitleg(self):
        antwoord = self.stuur(tekst="", fotos=[upload("IMG_0421.HEIC", b"x", "image/heic")], sleutel="sleutel-123456")
        self.assertIn("Meest compatibel", antwoord.json()["fout"])

    def test_te_veel_fotos_de_eerste_tien_gaan_mee_met_de_tekst(self):
        fotos = [upload(f"{i}.jpg") for i in range(12)]
        data = self.stuur(tekst="Hele rij", fotos=fotos, sleutel="sleutel-123456").json()
        self.assertEqual(Notitie.objects.get().fotos.count(), 10)
        self.assertTrue(any("hooguit 10" in m for m in data["meldingen"]))

    def test_fout_halverwege_laat_geen_bestanden_achter(self):
        from . import views

        echte = views.bewaar_bijlage
        teller = {"n": 0}

        def soms_kapot(*args, **kwargs):
            teller["n"] += 1
            if teller["n"] == 3:
                raise OSError("schijf vol")
            return echte(*args, **kwargs)

        voor = sum(len(bestanden) for _, _, bestanden in os.walk(TIJDELIJKE_MEDIA))
        with patch("klussen.chat.bewaar_bijlage", side_effect=soms_kapot):
            with self.assertRaises(OSError):
                self.stuur(tekst="x", fotos=[upload(f"{i}.jpg") for i in range(4)], sleutel="sleutel-123456")
        na = sum(len(bestanden) for _, _, bestanden in os.walk(TIJDELIJKE_MEDIA))
        self.assertEqual(na, voor)
        self.assertFalse(Notitie.objects.exists())


class StresstestTellerTests(ChatBasis):
    def test_nieuwe_collega_krijgt_niet_de_hele_geschiedenis(self):
        # Bevinding 2: wie nog nooit keek, telt alleen de laatste 30 dagen.
        oud = Notitie.objects.create(klus=self.klus, tekst="oud", geschreven_door=self.lot)
        Notitie.objects.filter(pk=oud.pk).update(geschreven_op=timezone.now() - timedelta(days=200))
        Notitie.objects.create(klus=self.klus, tekst="vers", geschreven_door=self.lot)
        nieuw = Medewerker.objects.create_user("nieuw", password="x", first_name="Nieuw")
        self.klus.betrokkenen.add(nieuw)
        self.assertEqual(gesprek.ongelezen_per_klus(nieuw, [self.klus.pk]), {self.klus.pk: 1})

    def test_meekijken_wist_het_rondje_niet(self):
        # Bevinding 3: de eigenaar die als medewerker meekijkt.
        Notitie.objects.create(klus=self.klus, tekst="x", geschreven_door=self.lot)
        sessie = self.client.session
        sessie[SESSIE_WISSEL] = self.maarten.pk
        sessie.save()
        self.client.get(reverse("klus_chat", args=[self.klus.pk]))
        self.assertEqual(gesprek.ongelezen_per_klus(self.sam, [self.klus.pk]), {self.klus.pk: 1})

    def test_melding_noemt_nooit_de_gebruikersnaam(self):
        zonder = Medewerker.objects.create_user("sam.inlog", password="x")
        self.assertEqual(gesprek.schrijversnaam(zonder), "Collega")


class StresstestRechtenTests(ChatBasis):
    """Stresstest rechten 17-11-2026 (tweede ronde)."""

    def test_verborgen_account_en_inlognaam_niet_bij_betrokkenen(self):
        beheer = Medewerker.objects.create_user("admin", password="x", rol=Medewerker.Rol.EIGENAAR)
        Medewerker.alle.filter(pk=beheer.pk).update(verborgen=True)
        zonder_naam = Medewerker.objects.create_user("j.devries.inlog", password="x")
        self.klus.betrokkenen.add(beheer, zonder_naam)
        for adres in (reverse("klus_chat", args=[self.klus.pk]), self.klus.get_absolute_url()):
            html = self.client.get(adres).content.decode()
            self.assertNotIn(">admin", html)
            self.assertNotIn("j.devries.inlog", html)

    def test_oud_collega_niet_bij_betrokkenen(self):
        Medewerker.objects.filter(pk=self.lot.pk).update(is_active=False)
        self.assertNotIn(self.lot, self.client.get(self.klus.get_absolute_url()).context["betrokkenen"])

    def test_beheeraccount_ziet_zelf_niet_meer_meedoen(self):
        beheer = Medewerker.objects.create_user("admin", password="x", rol=Medewerker.Rol.EIGENAAR)
        Medewerker.alle.filter(pk=beheer.pk).update(verborgen=True)
        self.klus.betrokkenen.add(beheer)
        self.client.force_login(beheer)
        self.assertContains(self.client.get(self.klus.get_absolute_url()), "Niet meer meedoen")

    def test_zelfde_sleutel_op_andere_klus_is_een_nieuw_bericht(self):
        andere = Klus.objects.create(naam="Vijver")
        self.stuur(tekst="Eerste", sleutel="dezelfde-sleutel-1")
        antwoord = self.client.post(reverse("notitie_toevoegen", args=[andere.pk]), {"tekst": "Tweede", "sleutel": "dezelfde-sleutel-1"}, **CHAT)
        self.assertEqual(antwoord.status_code, 200)
        self.assertEqual(Notitie.objects.get(klus=andere).tekst, "Tweede")
        zonder_js = self.client.post(reverse("notitie_toevoegen", args=[andere.pk]), {"tekst": "Derde", "sleutel": "dezelfde-sleutel-1"})
        self.assertEqual(zonder_js.status_code, 302)
        self.assertTrue(Notitie.objects.filter(klus=andere, tekst="Derde").exists())


class StresstestRegressieTests(ChatBasis):
    def test_leeg_bestand_uitleg_in_de_chat_zelf(self):
        data = self.stuur(tekst="Met een kapotte foto", fotos=[upload("kapot.jpg", b"")], sleutel="sleutel-leeg-1").json()
        self.assertTrue(any("kapot.jpg is leeg" in m for m in data["meldingen"]))
        self.assertNotContains(self.client.get(reverse("start")), "kapot.jpg is leeg")

    def test_alleen_leeg_bestand_is_een_fout(self):
        antwoord = self.stuur(tekst="", fotos=[upload("kapot.jpg", b"")], sleutel="sleutel-leeg-2")
        self.assertEqual(antwoord.status_code, 400)
        self.assertIn("kapot.jpg is leeg", antwoord.json()["fout"])

    def test_betrokken_regel_toont_wie_de_meldingen_krijgt(self):
        from uren.models import Inzet

        piet = Medewerker.objects.create_user("piet", password="x", first_name="Piet")
        Inzet.objects.create(medewerker=piet, klus=self.klus, datum=timezone.localdate())
        self.assertIn(piet, self.client.get(self.klus.get_absolute_url()).context["betrokkenen"])


class StresstestChatTests(ChatBasis):
    """Stresstest chat 17-11-2026."""

    def test_bericht_dat_tijdens_het_lezen_wordt_opgeslagen_blijft_ongelezen(self):
        nu = timezone.now()
        gezien = Notitie.objects.create(klus=self.klus, tekst="al gezien", geschreven_door=self.lot)
        Notitie.objects.filter(pk=gezien.pk).update(geschreven_op=nu - timedelta(minutes=5))
        # Sam kijkt nu; hij ziet alleen "al gezien".
        self.client.get(reverse("klus_chat_nieuw", args=[self.klus.pk]), {"na": 0, "zichtbaar": "1"})
        # Lot was intussen al bezig met een bericht met foto's: het kreeg zijn
        # tijdstip vóór Sam keek, maar werd pas daarna zichtbaar.
        bezig = Notitie.objects.create(klus=self.klus, tekst="met foto's", geschreven_door=self.lot)
        Notitie.objects.filter(pk=bezig.pk).update(geschreven_op=nu - timedelta(minutes=1))
        self.assertEqual(gesprek.ongelezen_per_klus(self.sam, [self.klus.pk]), {self.klus.pk: 1})

    def test_lege_poll_schrijft_niets(self):
        n = Notitie.objects.create(klus=self.klus, tekst="x", geschreven_door=self.lot)
        url = reverse("klus_chat_nieuw", args=[self.klus.pk])
        self.client.get(url, {"na": 0, "zichtbaar": "1"})
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as vastgelegd:
            self.client.get(url, {"na": n.pk, "van": n.pk, "zichtbaar": "1"})
        schrijven = [q["sql"] for q in vastgelegd.captured_queries if "notitiegelezen" in q["sql"].lower() and q["sql"].lstrip().upper().startswith(("UPDATE", "INSERT"))]
        self.assertTrue(all("tijdstip\" <" in s or "tijdstip` <" in s or "< " in s for s in schrijven))

    def test_ongeldige_sleutel_geeft_400(self):
        antwoord = self.stuur(tekst="hoi", sleutel="<script>")
        self.assertEqual(antwoord.status_code, 400)
        self.assertFalse(Notitie.objects.exists())

    def test_zelfde_sleutel_andere_tekst_is_nieuw_bericht(self):
        self.client.post(reverse("notitie_toevoegen", args=[self.klus.pk]), {"tekst": "eerste", "sleutel": "formulier-sleutel-1"})
        self.client.post(reverse("notitie_toevoegen", args=[self.klus.pk]), {"tekst": "tweede", "sleutel": "formulier-sleutel-1"})
        self.assertEqual(sorted(Notitie.objects.values_list("tekst", flat=True)), ["eerste", "tweede"])

    def test_eerdere_berichten_in_blokken(self):
        from . import chat as chatmodule

        Notitie.objects.bulk_create([Notitie(klus=self.klus, tekst=f"b{i}", geschreven_door=self.lot) for i in range(chatmodule.OP_HET_SCHERM + 20)])
        antwoord = self.client.get(reverse("klus_chat", args=[self.klus.pk]))
        self.assertEqual(len(antwoord.context["berichten"]), chatmodule.OP_HET_SCHERM)
        self.assertContains(antwoord, f"?aantal={2 * chatmodule.OP_HET_SCHERM}")
        meer = self.client.get(reverse("klus_chat", args=[self.klus.pk]), {"aantal": 2 * chatmodule.OP_HET_SCHERM})
        self.assertEqual(len(meer.context["berichten"]), chatmodule.OP_HET_SCHERM + 20)

    def test_teller_is_een_query(self):
        for _ in range(5):
            Notitie.objects.create(klus=self.klus, tekst="x", geschreven_door=self.lot)
        with self.assertNumQueries(5):
            # mijn_klus_ids (4) + de telling zelf (1)
            self.assertEqual(gesprek.ongelezen_per_klus(self.sam, [self.klus.pk]), {self.klus.pk: 5})

    def test_melding_vervangt_zich_per_klus(self):
        from pushberichten.models import Abonnement

        Abonnement.objects.create(medewerker=self.lot, endpoint="https://push.example/lot", p256dh="p", auth="a")
        notitie = Notitie.objects.create(klus=self.klus, tekst="hoi", geschreven_door=self.sam)
        with patch("pushberichten.versturen.stuur", return_value=True) as stuur:
            gesprek.meld(notitie.pk)
        self.assertEqual(stuur.call_args.kwargs["tag"], f"klus-{self.klus.pk}")
