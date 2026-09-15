import shutil
import tempfile
from datetime import date, time
from io import BytesIO

from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from medewerkers.models import Medewerker
from uren import totalen
from uren.models import Uurblok

from . import afbeeldingen, views
from .models import Bijlage, Klus

TIJDELIJKE_MEDIA = tempfile.mkdtemp()


def jpeg(breedte=3000, hoogte=2000, orientatie=None, kleur=(90, 140, 60)):
    """Een nepfoto zoals een telefoon 'm aanlevert."""
    afbeelding = Image.new("RGB", (breedte, hoogte), kleur)
    buffer = BytesIO()
    if orientatie:
        exif = Image.Exif()
        exif[0x0112] = orientatie          # Orientation
        exif[0x9003] = "2026:09:13 18:30:00"  # DateTimeOriginal, om te zien of exif wegvalt
        afbeelding.save(buffer, format="JPEG", exif=exif)
    else:
        afbeelding.save(buffer, format="JPEG")
    return buffer.getvalue()


def upload(naam="tuin.jpg", inhoud=None, type_="image/jpeg"):
    return SimpleUploadedFile(naam, inhoud if inhoud is not None else jpeg(), content_type=type_)


@override_settings(MEDIA_ROOT=TIJDELIJKE_MEDIA)
class AfbeeldingenTest(TestCase):
    """De beeldbewerking los, zonder database."""

    def test_foto_wordt_verkleind(self):
        hoofd, thumb = afbeeldingen.versies_van(BytesIO(jpeg(3000, 2000)), "tuin.jpg")
        with Image.open(hoofd) as groot:
            self.assertEqual(max(groot.size), afbeeldingen.MAX_ZIJDE)
        with Image.open(thumb) as klein:
            self.assertEqual(max(klein.size), afbeeldingen.THUMB_ZIJDE)

    def test_exif_rotatie_wordt_toegepast(self):
        # Orientatie 6 = "staand gemaakt, liggend opgeslagen". Zonder
        # exif_transpose staat de tuin op zijn kant in het raster.
        hoofd, _ = afbeeldingen.versies_van(BytesIO(jpeg(1000, 500, orientatie=6)), "staand.jpg")
        with Image.open(hoofd) as gedraaid:
            self.assertLess(gedraaid.width, gedraaid.height)

    def test_exif_gaat_niet_mee_naar_de_opslag(self):
        # In de EXIF van een telefoonfoto zitten GPS-coordinaten: het woonadres
        # van de klant. Dat hoort niet in een bestand dat gedownload kan worden.
        hoofd, _ = afbeeldingen.versies_van(BytesIO(jpeg(800, 600, orientatie=1)), "tuin.jpg")
        with Image.open(hoofd) as bewaard:
            self.assertFalse(dict(bewaard.getexif()))

    def test_document_gaat_ongemoeid(self):
        self.assertEqual(afbeeldingen.versies_van(BytesIO(b"%PDF-1.4"), "tekening.pdf"), (None, None))

    def test_heic_wordt_geweigerd_met_uitleg(self):
        with self.assertRaises(afbeeldingen.BestandNietLeesbaar) as gevangen:
            afbeeldingen.versies_van(BytesIO(b"ftypheic"), "IMG_0042.HEIC")
        self.assertIn("HEIC", str(gevangen.exception))

    def test_kapotte_afbeelding_geeft_geen_serverfout(self):
        with self.assertRaises(afbeeldingen.BestandNietLeesbaar):
            afbeeldingen.versies_van(BytesIO(b"dit is geen plaatje"), "stuk.jpg")


@override_settings(MEDIA_ROOT=TIJDELIJKE_MEDIA)
class BijlageUploadTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sam = Medewerker.objects.create_user("sam", password="x", first_name="Sam")
        cls.joep = Medewerker.objects.create_user("joep", password="x", first_name="Joep")
        cls.maarten = Medewerker.objects.create_user(
            "maarten", password="x", first_name="Maarten", rol=Medewerker.Rol.EIGENAAR
        )
        cls.klus = Klus.objects.create(naam="Tuin Vermeer")
        cls.blok = Uurblok.objects.create(
            medewerker=cls.sam, klus=cls.klus, datum=date(2026, 9, 7),
            begintijd=time(8, 0), eindtijd=time(16, 0),
        )

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TIJDELIJKE_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.client.force_login(self.sam)

    def test_inloggen_vereist(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("fotos")).status_code, 302)
        self.assertEqual(
            self.client.post(reverse("bijlage_toevoegen"), {"bestanden": upload()}).status_code, 302
        )
        self.assertFalse(Bijlage.objects.exists())

    def test_upload_zonder_doel_komt_in_de_dropbox(self):
        self.client.post(reverse("bijlage_toevoegen"), {"bestanden": upload(), "toelichting": "losse foto"})
        bijlage = Bijlage.objects.get()
        self.assertTrue(bijlage.in_dropbox)
        self.assertEqual(bijlage.toegevoegd_door, self.sam)
        self.assertEqual(bijlage.soort, Bijlage.Soort.FOTO)
        self.assertTrue(bijlage.thumbnail)

    def test_upload_aan_een_klus(self):
        self.client.post(reverse("bijlage_toevoegen"), {"bestanden": upload(), "klus": self.klus.pk})
        self.assertEqual(Bijlage.objects.get().klus, self.klus)

    def test_upload_aan_een_uurblok_hangt_ook_aan_de_klus(self):
        # Anders staat de foto wel bij het uurblok maar niet in het klusdossier.
        self.client.post(reverse("bijlage_toevoegen"), {"bestanden": upload(), "uurblok": self.blok.pk})
        bijlage = Bijlage.objects.get()
        self.assertEqual(bijlage.uurblok, self.blok)
        self.assertEqual(bijlage.klus, self.klus)

    def test_meerdere_bestanden_tegelijk(self):
        # Vanaf een telefoon selecteer je zelden een enkele foto.
        self.client.post(
            reverse("bijlage_toevoegen"),
            {"bestanden": [upload("een.jpg"), upload("twee.jpg"), upload("drie.jpg")]},
        )
        self.assertEqual(Bijlage.objects.count(), 3)

    def test_een_kapot_bestand_stopt_de_rest_niet(self):
        # Wie acht foto's uploadt wil niet alles opnieuw doen omdat er een niet deugt.
        antwoord = self.client.post(
            reverse("bijlage_toevoegen"),
            {"bestanden": [upload("goed.jpg"), upload("stuk.jpg", b"geen plaatje")]},
            follow=True,
        )
        self.assertEqual(Bijlage.objects.count(), 1)
        self.assertContains(antwoord, "stuk.jpg")

    def test_document_houdt_zijn_naam_en_krijgt_geen_thumbnail(self):
        self.client.post(
            reverse("bijlage_toevoegen"),
            {"bestanden": upload("Tuinontwerp definitief.pdf", b"%PDF-1.4", "application/pdf")},
        )
        bijlage = Bijlage.objects.get()
        self.assertEqual(bijlage.soort, Bijlage.Soort.DOCUMENT)
        self.assertEqual(bijlage.originele_naam, "Tuinontwerp definitief.pdf")
        self.assertEqual(bijlage.toonnaam, "Tuinontwerp definitief.pdf")
        self.assertFalse(bijlage.thumbnail)

    def test_zonder_bestand_geen_bijlage(self):
        self.client.post(reverse("bijlage_toevoegen"), {"toelichting": "vergeten"})
        self.assertFalse(Bijlage.objects.exists())

    def test_terug_naar_een_andere_site_wordt_genegeerd(self):
        antwoord = self.client.post(
            reverse("bijlage_toevoegen"),
            {"bestanden": upload(), "terug": "https://kwaadaardig.example/pak"},
        )
        self.assertEqual(antwoord.headers["Location"], reverse("fotos"))


@override_settings(MEDIA_ROOT=TIJDELIJKE_MEDIA)
class BijlageVerwijderenTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sam = Medewerker.objects.create_user("sam", password="x")
        cls.joep = Medewerker.objects.create_user("joep", password="x")
        cls.maarten = Medewerker.objects.create_user(
            "maarten", password="x", rol=Medewerker.Rol.EIGENAAR
        )

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TIJDELIJKE_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def bijlage_van_sam(self):
        self.client.force_login(self.sam)
        self.client.post(reverse("bijlage_toevoegen"), {"bestanden": upload()})
        return Bijlage.objects.get()

    def test_ander_mag_mijn_bijlage_niet_verwijderen(self):
        bijlage = self.bijlage_van_sam()
        self.client.force_login(self.joep)
        self.assertEqual(
            self.client.post(reverse("bijlage_verwijderen", args=[bijlage.pk])).status_code, 404
        )
        self.assertTrue(Bijlage.objects.filter(pk=bijlage.pk).exists())

    def test_eigenaar_mag_wel(self):
        bijlage = self.bijlage_van_sam()
        self.client.force_login(self.maarten)
        self.client.post(reverse("bijlage_verwijderen", args=[bijlage.pk]))
        self.assertFalse(Bijlage.objects.filter(pk=bijlage.pk).exists())

    def test_zelf_mag_ook(self):
        bijlage = self.bijlage_van_sam()
        self.client.post(reverse("bijlage_verwijderen", args=[bijlage.pk]))
        self.assertFalse(Bijlage.objects.filter(pk=bijlage.pk).exists())

    def test_verwijderen_kan_niet_met_een_gewone_link(self):
        # Anders haalt een link in een mailtje, of een crawler, bijlagen weg.
        bijlage = self.bijlage_van_sam()
        self.assertEqual(
            self.client.get(reverse("bijlage_verwijderen", args=[bijlage.pk])).status_code, 405
        )
        self.assertTrue(Bijlage.objects.filter(pk=bijlage.pk).exists())


@override_settings(MEDIA_ROOT=TIJDELIJKE_MEDIA)
class MediaTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sam = Medewerker.objects.create_user("sam", password="x")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TIJDELIJKE_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def bijlage(self):
        self.client.force_login(self.sam)
        self.client.post(reverse("bijlage_toevoegen"), {"bestanden": upload()})
        return Bijlage.objects.get()

    def test_bestand_is_niet_openbaar(self):
        bijlage = self.bijlage()
        adres = reverse("media_bestand", args=[bijlage.bestand.name])
        self.client.logout()
        antwoord = self.client.get(adres)
        self.assertEqual(antwoord.status_code, 302)
        self.assertIn(reverse("inloggen"), antwoord.headers["Location"])

    def test_ingelogd_krijg_je_het_bestand_wel(self):
        bijlage = self.bijlage()
        antwoord = self.client.get(reverse("media_bestand", args=[bijlage.bestand.name]))
        self.assertEqual(antwoord.status_code, 200)

    def test_pad_naar_buiten_de_mediamap_geeft_niets(self):
        # Zonder deze controle haalt ../../.env de secret key op.
        verzoek = RequestFactory().get("/media/x")
        verzoek.user = self.sam
        for stiekem in ("../config/settings.py", "../../klusapp/config/settings.py", "..%2F.env"):
            with self.assertRaises(Http404):
                views.media_bestand(verzoek, stiekem)

    def test_onbekend_bestand_geeft_404(self):
        verzoek = RequestFactory().get("/media/x")
        verzoek.user = self.sam
        with self.assertRaises(Http404):
            views.media_bestand(verzoek, "bijlagen/2026/09/bestaatniet.jpg")


class FilterTest(TestCase):
    def test_uitgelogde_bezoeker_mag_niks_verwijderen(self):
        from .templatetags.bijlagen import mag_weg

        self.assertFalse(mag_weg(Bijlage(), AnonymousUser()))


class KlusBeheerTest(TestCase):
    """Klussen aanmaken en bijwerken. Alleen de eigenaar komt hier."""

    @classmethod
    def setUpTestData(cls):
        cls.sam = Medewerker.objects.create_user("sam", password="x", first_name="Sam")
        cls.maarten = Medewerker.objects.create_user(
            "maarten", password="x", first_name="Maarten", rol=Medewerker.Rol.EIGENAAR
        )

    def geldig(self, **afwijkend):
        gegevens = {
            "naam": "Tuin Vermeer",
            "soort": Klus.Soort.AANLEG,
            "startdatum": "2026-09-14",
            "opdrachtgever": "Fam. Vermeer",
            "adres": "Dijkweg 12",
            "plaats": "Maasdijk",
            "beschrijving": "Volledige aanleg achtertuin",
            "kleur": "#95BF1D",
            "actief": "on",
        }
        gegevens.update(afwijkend)
        return gegevens

    def test_eigenaar_maakt_een_klus_aan(self):
        self.client.force_login(self.maarten)
        antwoord = self.client.post(reverse("klus_nieuw"), self.geldig())
        klus = Klus.objects.get()
        self.assertRedirects(antwoord, klus.get_absolute_url())
        self.assertEqual(klus.startdatum, date(2026, 9, 14))
        self.assertEqual(klus.beschrijving, "Volledige aanleg achtertuin")

    def test_medewerker_komt_er_niet_in(self):
        # 404 en geen 403: een medewerker hoeft niet te weten dat het bestaat.
        self.client.force_login(self.sam)
        self.assertEqual(self.client.get(reverse("klus_nieuw")).status_code, 404)
        self.assertEqual(self.client.post(reverse("klus_nieuw"), self.geldig()).status_code, 404)
        self.assertFalse(Klus.objects.exists())

    def test_uitgelogd_naar_inloggen(self):
        antwoord = self.client.get(reverse("klus_nieuw"))
        self.assertEqual(antwoord.status_code, 302)
        self.assertIn(reverse("inloggen"), antwoord.headers["Location"])

    def test_aanlegklus_zonder_startdatum_wordt_geweigerd(self):
        self.client.force_login(self.maarten)
        antwoord = self.client.post(reverse("klus_nieuw"), self.geldig(startdatum=""))
        self.assertEqual(antwoord.status_code, 200)
        self.assertContains(antwoord, "startdatum van de aanlegklus")
        self.assertFalse(Klus.objects.exists())

    def test_onderhoudsklant_heeft_geen_startdatum(self):
        # Een onderhoudsklant is een terugkerende afspraak zonder begin.
        self.client.force_login(self.maarten)
        self.client.post(
            reverse("klus_nieuw"),
            self.geldig(soort=Klus.Soort.ONDERHOUD, startdatum="2026-09-14"),
        )
        self.assertIsNone(Klus.objects.get().startdatum)

    def test_eigenaar_bewerkt_een_klus(self):
        klus = Klus.objects.create(naam="Oude naam", startdatum=date(2026, 9, 14))
        self.client.force_login(self.maarten)
        self.client.post(reverse("klus_bewerken", args=[klus.pk]), self.geldig(naam="Nieuwe naam"))
        klus.refresh_from_db()
        self.assertEqual(klus.naam, "Nieuwe naam")

    def test_medewerker_mag_niet_bewerken(self):
        klus = Klus.objects.create(naam="Tuin Vermeer")
        self.client.force_login(self.sam)
        self.assertEqual(
            self.client.get(reverse("klus_bewerken", args=[klus.pk])).status_code, 404
        )

    def test_alleen_de_eigenaar_ziet_de_knoppen(self):
        klus = Klus.objects.create(naam="Tuin Vermeer")
        self.client.force_login(self.sam)
        self.assertNotContains(self.client.get(reverse("klussen")), "Nieuwe klus")
        self.assertNotContains(self.client.get(klus.get_absolute_url()), "Bewerken")
        self.client.force_login(self.maarten)
        self.assertContains(self.client.get(reverse("klussen")), "Nieuwe klus")
        self.assertContains(self.client.get(klus.get_absolute_url()), "Bewerken")


class GewerkteUrenOpKlusTest(TestCase):
    """Contractpunt 4: wie op welke klus heeft gewerkt."""

    @classmethod
    def setUpTestData(cls):
        cls.sam = Medewerker.objects.create_user(
            "sam", password="x", first_name="Sam", last_name="de Wit", functie="Voorman"
        )
        cls.joep = Medewerker.objects.create_user("joep", password="x", first_name="Joep")
        cls.klus = Klus.objects.create(naam="Tuin Vermeer")
        cls.andere = Klus.objects.create(naam="Andere klus")

    def blok(self, wie, dag, begin, eind, klus=None):
        return Uurblok.objects.create(
            medewerker=wie, klus=klus or self.klus, datum=dag,
            begintijd=time(begin), eindtijd=time(eind),
        )

    def test_uren_worden_per_medewerker_opgeteld(self):
        self.blok(self.sam, date(2026, 9, 7), 8, 16)      # 8:00
        self.blok(self.sam, date(2026, 9, 8), 8, 12)      # 4:00
        self.blok(self.joep, date(2026, 9, 8), 9, 11)     # 2:00
        rijen = totalen.per_medewerker_op_klus(self.klus)
        self.assertEqual([rij["uren"] for rij in rijen], ["12:00", "2:00"])
        self.assertEqual(rijen[0]["medewerker"], self.sam)
        self.assertEqual(rijen[0]["aantal_dagen"], 2)
        self.assertEqual(rijen[0]["eerste_dag"], date(2026, 9, 7))
        self.assertEqual(rijen[0]["laatste_dag"], date(2026, 9, 8))
        self.assertEqual(totalen.totaal_van(rijen)["uren"], "14:00")

    def test_twee_blokken_op_een_dag_tellen_als_een_dag(self):
        # Bij onderhoud doet iemand zes tot acht adressen op een dag.
        self.blok(self.sam, date(2026, 9, 7), 8, 9)
        self.blok(self.sam, date(2026, 9, 7), 10, 11)
        rij = totalen.per_medewerker_op_klus(self.klus)[0]
        self.assertEqual(rij["aantal_dagen"], 1)
        self.assertEqual(rij["uren"], "2:00")

    def test_uren_van_een_andere_klus_tellen_niet_mee(self):
        self.blok(self.sam, date(2026, 9, 7), 8, 16)
        self.blok(self.sam, date(2026, 9, 7), 8, 16, klus=self.andere)
        self.assertEqual(totalen.per_medewerker_op_klus(self.klus)[0]["uren"], "8:00")

    def test_klus_zonder_uren_geeft_lege_lijst(self):
        self.assertEqual(totalen.per_medewerker_op_klus(self.klus), [])
        self.assertEqual(totalen.totaal_van([])["uren"], "0:00")

    def test_medewerker_ziet_de_uren_van_collegas_in_het_dossier(self):
        # SPEC 2: een medewerker ziet het volledige klusdossier. "Wie op welke
        # klus heeft gewerkt" hoort daarbij; zijn eigen urenoverzicht is een
        # ander scherm.
        self.blok(self.joep, date(2026, 9, 7), 8, 16)
        self.client.force_login(self.sam)
        antwoord = self.client.get(self.klus.get_absolute_url())
        self.assertContains(antwoord, "Joep")
        self.assertContains(antwoord, "8:00")

    def test_functie_staat_naast_de_naam(self):
        self.blok(self.sam, date(2026, 9, 7), 8, 16)
        self.client.force_login(self.sam)
        antwoord = self.client.get(self.klus.get_absolute_url())
        self.assertContains(antwoord, "Sam de Wit")
        self.assertContains(antwoord, "Voorman")
