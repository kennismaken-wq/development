from django.test import TestCase
from django.urls import reverse

from medewerkers.models import Medewerker

from .models import Idee, Like


class IdeeenbusTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.maarten = Medewerker.objects.create_user("maarten", password="x", first_name="Maarten", rol=Medewerker.Rol.EIGENAAR)
        cls.sam = Medewerker.objects.create_user("sam", password="x", first_name="Sam")
        cls.lot = Medewerker.objects.create_user("lot", password="x", first_name="Lot")

    def setUp(self):
        self.client.force_login(self.sam)

    def test_inloggen_verplicht(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("ideeen")).status_code, 302)

    def test_idee_insturen_met_naam(self):
        self.client.post(reverse("idee_nieuw"), {"tekst": "Koffieapparaat in de bus"})
        idee = Idee.objects.get()
        self.assertEqual(idee.door, self.sam)
        self.assertContains(self.client.get(reverse("ideeen")), "Koffieapparaat in de bus")

    def test_anoniem_bewaart_geen_naam(self):
        self.client.post(reverse("idee_nieuw"), {"tekst": "Vaker pizza", "anoniem": "1"})
        idee = Idee.objects.get()
        self.assertIsNone(idee.door)
        html = self.client.get(reverse("ideeen")).content.decode()
        self.assertIn("Anoniem", html)

    def test_leeg_of_te_lang_niet(self):
        self.client.post(reverse("idee_nieuw"), {"tekst": "   "})
        self.client.post(reverse("idee_nieuw"), {"tekst": "x" * 1001})
        self.assertFalse(Idee.objects.exists())

    def test_dubbel_tikken_een_idee(self):
        for _ in range(3):
            self.client.post(reverse("idee_nieuw"), {"tekst": "Nieuwe bladblazer"})
        self.assertEqual(Idee.objects.count(), 1)

    def test_liken_en_weer_uit(self):
        idee = Idee.objects.create(tekst="x", door=self.lot)
        data = self.client.post(reverse("idee_like", args=[idee.pk]), HTTP_X_IDEE="1").json()
        self.assertEqual(data, {"geliket": True, "aantal": 1})
        data = self.client.post(reverse("idee_like", args=[idee.pk]), HTTP_X_IDEE="1").json()
        self.assertEqual(data, {"geliket": False, "aantal": 0})

    def test_meeste_likes_bovenaan(self):
        weinig = Idee.objects.create(tekst="weinig", door=self.lot)
        veel = Idee.objects.create(tekst="veel", door=self.lot)
        for mw in (self.sam, self.lot, self.maarten):
            Like.objects.create(idee=veel, medewerker=mw)
        lijst = list(self.client.get(reverse("ideeen"), {"op": "likes"}).context["ideeen"])
        self.assertEqual(lijst, [veel, weinig])
        self.assertEqual(lijst[0].aantal_likes, 3)

    def test_alleen_eigenaar_zet_stand(self):
        idee = Idee.objects.create(tekst="x", door=self.lot)
        self.assertEqual(self.client.post(reverse("idee_stand", args=[idee.pk]), {"stand": "gedaan"}).status_code, 404)
        self.client.force_login(self.maarten)
        self.client.post(reverse("idee_stand", args=[idee.pk]), {"stand": "doen_we", "reactie": "Goed plan!"})
        idee.refresh_from_db()
        self.assertEqual((idee.stand, idee.reactie), ("doen_we", "Goed plan!"))

    def test_verwijderen_eigen_of_eigenaar(self):
        van_lot = Idee.objects.create(tekst="lot", door=self.lot)
        anoniem = Idee.objects.create(tekst="anoniem", door=None)
        eigen = Idee.objects.create(tekst="eigen", door=self.sam)
        self.assertEqual(self.client.post(reverse("idee_verwijderen", args=[van_lot.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("idee_verwijderen", args=[anoniem.pk])).status_code, 404)
        self.client.post(reverse("idee_verwijderen", args=[eigen.pk]))
        self.assertFalse(Idee.objects.filter(pk=eigen.pk).exists())
        self.client.force_login(self.maarten)
        self.client.post(reverse("idee_verwijderen", args=[anoniem.pk]))
        self.assertFalse(Idee.objects.filter(pk=anoniem.pk).exists())

    def test_tekst_wordt_ge_escaped(self):
        Idee.objects.create(tekst="<img src=x onerror=alert(1)>", door=self.lot)
        self.assertNotContains(self.client.get(reverse("ideeen")), "<img src=x")

    def test_tegel_op_startscherm(self):
        self.assertContains(self.client.get(reverse("start")), reverse("ideeen"))
