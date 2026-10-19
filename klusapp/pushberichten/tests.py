import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from pywebpush import WebPushException

from medewerkers.models import Medewerker

from . import versturen
from .models import Abonnement, Sleutelpaar

ENDPOINT = "https://web.push.apple.com/abc123"


class PushTestBasis(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sam = Medewerker.objects.create_user(
            "sam", password="test1234", first_name="Sam", rol=Medewerker.Rol.MEDEWERKER
        )

    def setUp(self):
        self.client.force_login(self.sam)

    def abonnement(self, **velden):
        return Abonnement.objects.create(medewerker=self.sam, endpoint=ENDPOINT, p256dh="p", auth="a", **velden)


class AanmeldenTest(PushTestBasis):
    def test_sleutel_wordt_eenmalig_gemaakt(self):
        eerste = self.client.get(reverse("push_sleutel")).json()["sleutel"]
        tweede = self.client.get(reverse("push_sleutel")).json()["sleutel"]
        self.assertEqual(eerste, tweede)
        self.assertEqual(Sleutelpaar.objects.count(), 1)
        self.assertEqual(len(eerste), 87)  # 65 bytes, base64url zonder =

    def test_aanmelden_bewaart_toestel(self):
        antwoord = self.client.post(
            reverse("push_aanmelden"),
            json.dumps({"endpoint": ENDPOINT, "keys": {"p256dh": "p", "auth": "a"}}),
            content_type="application/json",
        )
        self.assertEqual(antwoord.status_code, 204)
        self.assertEqual(Abonnement.objects.get().medewerker, self.sam)

    def test_geen_vreemd_adres(self):
        antwoord = self.client.post(
            reverse("push_aanmelden"),
            json.dumps({"endpoint": "http://ergens/", "keys": {"p256dh": "p", "auth": "a"}}),
            content_type="application/json",
        )
        self.assertEqual(antwoord.status_code, 400)
        self.assertFalse(Abonnement.objects.exists())

    def test_inloggen_verplicht(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("push_sleutel")).status_code, 302)

    @override_settings(TESTFUNCTIES=False)
    def test_uit_op_maartens_omgeving(self):
        self.assertEqual(self.client.get(reverse("push_sleutel")).status_code, 404)
        html = self.client.get(reverse("start")).content.decode()
        self.assertNotIn('id="testmelding"', html)
        self.assertNotIn("pushmelding.js", html)

    def test_knop_en_script_op_develop(self):
        html = self.client.get(reverse("start")).content.decode()
        self.assertIn('id="testmelding"', html)
        self.assertIn("pushmelding.js", html)
        self.assertNotIn('id="testmelding"', self.client.get(reverse("klussen")).content.decode())

    def test_service_worker_toont_meldingen(self):
        js = self.client.get("/sw.js").content.decode()
        self.assertIn('addEventListener("push"', js)
        self.assertIn('addEventListener("notificationclick"', js)


class DichtEnOpenTest(PushTestBasis):
    @patch("pushberichten.versturen.plan_na_sluiten")
    def test_dicht_plant_een_melding(self, plan):
        abo = self.abonnement()
        self.client.post(reverse("push_status"), {"endpoint": ENDPOINT, "stand": "dicht"})
        abo.refresh_from_db()
        self.assertIsNotNone(abo.gesloten_om)
        plan.assert_called_once()

    @patch("pushberichten.versturen.plan_na_sluiten")
    def test_open_plant_niets(self, plan):
        abo = self.abonnement()
        self.client.post(reverse("push_status"), {"endpoint": ENDPOINT, "stand": "open"})
        abo.refresh_from_db()
        self.assertIsNotNone(abo.geopend_om)
        plan.assert_not_called()

    @patch("pushberichten.versturen.plan_na_sluiten")
    def test_andermans_toestel_telt_niet(self, plan):
        ander = Medewerker.objects.create_user("joep", password="x", rol=Medewerker.Rol.MEDEWERKER)
        Abonnement.objects.create(medewerker=ander, endpoint=ENDPOINT, p256dh="p", auth="a")
        self.client.post(reverse("push_status"), {"endpoint": ENDPOINT, "stand": "dicht"})
        plan.assert_not_called()


class EchteVersleutelingTest(PushTestBasis):
    """webpush écht laten versleutelen en ondertekenen met ons opgeslagen
    sleutelpaar; alleen het verzoek naar Apple/Google wordt onderschept."""

    def test_versleutelt_en_ondertekent(self):
        import base64

        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec

        toestel = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
        b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()  # noqa: E731
        abo = Abonnement.objects.create(
            medewerker=self.sam, endpoint=ENDPOINT, p256dh=b64(toestel), auth=b64(b"0123456789abcdef")
        )
        with patch("pywebpush.requests.post") as post:
            post.return_value = MagicMock(status_code=201)
            self.assertTrue(versturen.stuur(abo, "Titel", "Tekst"))
        url = post.call_args.args[0]
        kop = post.call_args.kwargs["headers"]
        self.assertEqual(url, ENDPOINT)
        self.assertIn("vapid", kop["Authorization"].lower())
        self.assertIn(versturen.sleutelpaar().publiek, kop["Authorization"])
        self.assertEqual(kop["Content-Encoding"], "aes128gcm")


@patch("pushberichten.versturen.webpush")
class NaEenMinuutTest(PushTestBasis):
    def test_nog_dicht_dan_melding(self, webpush):
        dicht = timezone.now()
        abo = self.abonnement(gesloten_om=dicht)
        self.assertTrue(versturen.stuur_als_nog_dicht(abo.pk, dicht))
        webpush.assert_called_once()
        self.assertEqual(webpush.call_args.kwargs["subscription_info"]["endpoint"], ENDPOINT)
        self.assertIn("Testmelding", json.loads(webpush.call_args.kwargs["data"])["tekst"])

    def test_weer_geopend_dan_niets(self, webpush):
        dicht = timezone.now()
        abo = self.abonnement(gesloten_om=dicht, geopend_om=dicht + timedelta(seconds=20))
        self.assertFalse(versturen.stuur_als_nog_dicht(abo.pk, dicht))
        webpush.assert_not_called()

    def test_later_opnieuw_gesloten_dan_alleen_die_laatste(self, webpush):
        dicht = timezone.now()
        abo = self.abonnement(gesloten_om=dicht + timedelta(seconds=30))
        self.assertFalse(versturen.stuur_als_nog_dicht(abo.pk, dicht))
        webpush.assert_not_called()

    def test_opgezegd_toestel_wordt_opgeruimd(self, webpush):
        webpush.side_effect = WebPushException("weg", response=MagicMock(status_code=410))
        dicht = timezone.now()
        abo = self.abonnement(gesloten_om=dicht)
        self.assertFalse(versturen.stuur_als_nog_dicht(abo.pk, dicht))
        self.assertFalse(Abonnement.objects.exists())
