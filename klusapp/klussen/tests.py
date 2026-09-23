import shutil
import tempfile
import uuid
from datetime import date, time, timedelta
from io import BytesIO

import pymupdf
from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.http import Http404
from django.test.utils import CaptureQueriesContext
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from medewerkers.models import Medewerker
from uren import totalen
from uren.models import Uurblok

from . import afbeeldingen, fotoposts, kleuren, opdrachtgevers, pdf_thumbnails, views, voorbeeld
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


def pdf(breedte=200, hoogte=280):
    """Een geldige PDF van één pagina, zoals een offerte of tekening."""
    with pymupdf.open() as document:
        document.new_page(width=breedte, height=hoogte)
        return document.tobytes()


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

    def test_thumbnail_van_geeft_voorbeeld_voor_een_foto_als_document(self):
        # bewaar_bijlage roept dit alleen aan met forceer_document=True: het
        # bestand zelf blijft dan ongemoeid, alleen dit voorbeeldplaatje wordt
        # gemaakt (zie klussen.views.bewaar_bijlage).
        thumbnail = afbeeldingen.thumbnail_van(BytesIO(jpeg()), "tekening.jpg")
        with Image.open(thumbnail) as klein:
            self.assertEqual(max(klein.size), afbeeldingen.THUMB_ZIJDE)

    def test_thumbnail_van_geeft_niets_voor_een_pdf(self):
        self.assertIsNone(afbeeldingen.thumbnail_van(BytesIO(b"%PDF-1.4"), "offerte.pdf"))

    def test_thumbnail_van_geeft_niets_voor_onleesbare_afbeelding(self):
        self.assertIsNone(afbeeldingen.thumbnail_van(BytesIO(b"dit is geen plaatje"), "stuk.jpg"))


class PdfThumbnailsTest(TestCase):
    """De PDF-voorbeeldplaatjes los, zonder database (zie AfbeeldingenTest)."""

    def test_eerste_pagina_wordt_een_thumbnail(self):
        thumbnail = pdf_thumbnails.thumbnail_van(BytesIO(pdf()), "tekening.pdf")
        with Image.open(thumbnail) as klein:
            self.assertEqual(max(klein.size), afbeeldingen.THUMB_ZIJDE)

    def test_geen_pdf_geeft_geen_thumbnail(self):
        self.assertIsNone(pdf_thumbnails.thumbnail_van(BytesIO(jpeg()), "tuin.jpg"))

    def test_onleesbare_pdf_geeft_geen_thumbnail(self):
        # Een half bestand (afgebroken upload, of gewoon geen echte PDF) mag
        # niet als 500 eindigen — het document wordt dan zonder voorbeeld
        # opgeslagen, precies zoals een document er tot nu toe uitzag.
        self.assertIsNone(pdf_thumbnails.thumbnail_van(BytesIO(b"%PDF-1.4"), "stuk.pdf"))


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
        bijlagen = list(Bijlage.objects.all())
        self.assertEqual(len(bijlagen), 3)
        # Alle drie uit dezelfde upload delen hun batch, zodat het fotoraster
        # ze als één post kan tonen (zie klussen.fotoposts.groepeer_in_posts).
        batches = {bijlage.batch for bijlage in bijlagen}
        self.assertEqual(len(batches), 1)
        self.assertIsNotNone(batches.pop())

    def test_los_bestand_krijgt_geen_batch(self):
        # Niets om mee te groeperen, dus geen kenmerk nodig.
        self.client.post(reverse("bijlage_toevoegen"), {"bestanden": upload()})
        self.assertIsNone(Bijlage.objects.get().batch)

    def test_forceer_document_maakt_van_een_foto_toch_een_document(self):
        # De documentendialoog op een klusdossier (_documentdialoog.html):
        # een foto van bijvoorbeeld een tekening hoort hier ook, en moet dan
        # niet tussen de werkfoto's in het fotoraster verschijnen.
        self.client.post(
            reverse("bijlage_toevoegen"),
            {"bestanden": upload("tekening.jpg"), "klus": self.klus.pk, "forceer_document": "1"},
        )
        bijlage = Bijlage.objects.get()
        self.assertEqual(bijlage.soort, Bijlage.Soort.DOCUMENT)
        self.assertFalse(bijlage.is_foto)
        # Het bestand zelf blijft ongemoeid, net als elk ander document —
        # niet verkleind zoals een gewone foto-upload.
        with Image.open(bijlage.bestand) as bewaard:
            self.assertEqual(bewaard.size, Image.open(BytesIO(jpeg())).size)
        # Wel een thumbnail, zodat de documentenlijst een voorbeeld toont.
        self.assertTrue(bijlage.thumbnail)

    def test_forceer_document_geldt_niet_in_de_fotodropbox(self):
        # Zonder klus/uurblok is dit de fotodropbox, die geen documenten
        # toont — forceer_document mag daar dus niet stiekem toch een
        # document van maken (zie klussen.views.bijlage_toevoegen).
        self.client.post(
            reverse("bijlage_toevoegen"),
            {"bestanden": upload("tekening.jpg"), "forceer_document": "1"},
        )
        self.assertEqual(Bijlage.objects.get().soort, Bijlage.Soort.FOTO)

    def test_twee_losse_uploads_delen_geen_batch(self):
        self.client.post(
            reverse("bijlage_toevoegen"),
            {"bestanden": [upload("een.jpg"), upload("twee.jpg")]},
        )
        self.client.post(
            reverse("bijlage_toevoegen"),
            {"bestanden": [upload("drie.jpg"), upload("vier.jpg")]},
        )
        batches = {bijlage.batch for bijlage in Bijlage.objects.all()}
        self.assertEqual(len(batches), 2)

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
            {
                "bestanden": upload("Tuinontwerp definitief.pdf", b"%PDF-1.4", "application/pdf"),
                "klus": self.klus.pk,
            },
        )
        bijlage = Bijlage.objects.get()
        self.assertEqual(bijlage.soort, Bijlage.Soort.DOCUMENT)
        self.assertEqual(bijlage.originele_naam, "Tuinontwerp definitief.pdf")
        self.assertEqual(bijlage.toonnaam, "Tuinontwerp definitief.pdf")
        self.assertFalse(bijlage.thumbnail)

    def test_document_zonder_klus_of_uurblok_wordt_geweigerd(self):
        # De fotodropbox (de "+" op de foto tab) is foto's-only: een document
        # zonder klus eronder kon vroeger alleen via de documentenlijst op dat
        # scherm teruggevonden worden, en die lijst is daar weg (zie fotos.html).
        antwoord = self.client.post(
            reverse("bijlage_toevoegen"),
            {"bestanden": upload("Tuinontwerp.pdf", b"%PDF-1.4", "application/pdf")},
            follow=True,
        )
        self.assertFalse(Bijlage.objects.exists())
        self.assertContains(antwoord, "geen document")

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
class FotosKlusfilterTest(TestCase):
    """De klus-dropdown op /fotos/: standaard alles plat, filteren op klus
    beperkt tot die ene klus (zie klussen/views.py:fotos)."""

    @classmethod
    def setUpTestData(cls):
        cls.sam = Medewerker.objects.create_user("sam", password="x", first_name="Sam")
        cls.klus = Klus.objects.create(naam="Tuin Vermeer", adres="Dijkweg 12")
        cls.lege_klus = Klus.objects.create(naam="Kale klus", actief=False)
        cls.foto_op_klus = Bijlage.objects.create(
            klus=cls.klus, bestand=upload(), soort=Bijlage.Soort.FOTO, datum=date(2026, 9, 1),
        )
        cls.losse_foto = Bijlage.objects.create(
            bestand=upload("los.jpg"), soort=Bijlage.Soort.FOTO, datum=date(2026, 9, 2),
        )

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TIJDELIJKE_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.client.force_login(self.sam)

    def _bijlagen(self, antwoord):
        """foto_posts groepeert per upload (zie klussen.fotoposts); deze
        tests kijken alleen of een bijlage wel/niet in het resultaat zit, dus
        die groepering weer platslaan naar een lijst bijlagen."""
        return [bijlage for post in antwoord.context["foto_posts"] for bijlage in post]

    def test_zonder_filter_toont_alle_fotos(self):
        antwoord = self.client.get(reverse("fotos"))
        self.assertEqual(antwoord.context["klus_pk"], "")
        self.assertIn(self.foto_op_klus, self._bijlagen(antwoord))
        self.assertIn(self.losse_foto, self._bijlagen(antwoord))

    def test_onbekende_klus_valt_terug_op_alles(self):
        antwoord = self.client.get(reverse("fotos"), {"klus": "onzin"})
        self.assertEqual(antwoord.context["klus_pk"], "")
        self.assertIn(self.losse_foto, self._bijlagen(antwoord))

    def test_filter_op_klus_toont_alleen_die_klus(self):
        antwoord = self.client.get(reverse("fotos"), {"klus": self.klus.pk})
        self.assertIn(self.foto_op_klus, self._bijlagen(antwoord))
        self.assertNotIn(self.losse_foto, self._bijlagen(antwoord))

    def test_dropdown_bevat_elke_klus_ook_zonder_inhoud(self):
        antwoord = self.client.get(reverse("fotos"))
        namen = [klus.naam for klus in antwoord.context["klussen"]]
        self.assertIn(self.klus.naam, namen)
        self.assertIn(self.lege_klus.naam, namen)


class GroepeerInPostsTest(TestCase):
    """klussen.fotoposts.groepeer_in_posts: bijlagen uit dezelfde upload
    (gelijke, niet-lege batch) horen samen in één post, in de volgorde
    waarin ze binnenkomen; al het andere blijft een post van één."""

    def _bijlage(self, batch=None):
        # Geen databaseobject nodig: groepeer_in_posts kijkt alleen naar
        # gelijkheid van .batch, dus een kaal object met dat ene attribuut is
        # genoeg en scheelt een hoop testopzet (bestand, klus, gebruiker...).
        return type("Bijlage", (), {"batch": batch})()

    def test_lege_lijst(self):
        self.assertEqual(fotoposts.groepeer_in_posts([]), [])

    def test_zonder_batch_blijft_elk_een_eigen_post(self):
        a, b = self._bijlage(), self._bijlage()
        self.assertEqual(fotoposts.groepeer_in_posts([a, b]), [[a], [b]])

    def test_gelijke_batch_wordt_één_post(self):
        batch = uuid.uuid4()
        a, b, c = self._bijlage(batch), self._bijlage(batch), self._bijlage(batch)
        self.assertEqual(fotoposts.groepeer_in_posts([a, b, c]), [[a, b, c]])

    def test_verschillende_batches_blijven_losse_posts(self):
        a = self._bijlage(uuid.uuid4())
        b = self._bijlage(uuid.uuid4())
        self.assertEqual(fotoposts.groepeer_in_posts([a, b]), [[a], [b]])

    def test_batch_alleen_gegroepeerd_als_opeenvolgend(self):
        # Twee losse uploads met toevallig dezelfde... nee, batch is altijd
        # een eigen uuid per upload, maar deze test bewaakt dat de functie op
        # opeenvolgendheid let en niet blind alles met dezelfde batch bij
        # elkaar raapt van overal in de lijst — dat zou immers nooit
        # voorkomen in een echt geordend raster.
        batch = uuid.uuid4()
        a = self._bijlage(batch)
        tussenin = self._bijlage()
        b = self._bijlage(batch)
        self.assertEqual(fotoposts.groepeer_in_posts([a, tussenin, b]), [[a], [tussenin], [b]])


@override_settings(MEDIA_ROOT=TIJDELIJKE_MEDIA)
class FotoPostsIntegratieTest(TestCase):
    """De fotos-pagina zelf: een upload van meerdere bestanden tegelijk moet
    daar als één post verschijnen, niet als losse kaartjes."""

    @classmethod
    def setUpTestData(cls):
        cls.sam = Medewerker.objects.create_user("sam", password="x", first_name="Sam")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TIJDELIJKE_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def test_batchupload_verschijnt_als_één_post(self):
        self.client.force_login(self.sam)
        self.client.post(
            reverse("bijlage_toevoegen"),
            {"bestanden": [upload("een.jpg"), upload("twee.jpg"), upload("drie.jpg")]},
        )
        antwoord = self.client.get(reverse("fotos"))
        self.assertEqual(len(antwoord.context["foto_posts"]), 1)
        self.assertEqual(len(antwoord.context["foto_posts"][0]), 3)


@override_settings(MEDIA_ROOT=TIJDELIJKE_MEDIA)
class VoorbeeldItemsTest(TestCase):
    """De gewaaierde stapel op een klustegel: voorbeeld.items_voor_stapel()
    bepaalt wat er in past en wat er "+N meer" bij komt te staan."""

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TIJDELIJKE_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def test_notitie_is_de_achterste_laag_en_verdringt_geen_media(self):
        klus = Klus.objects.create(naam="Tuin Vermeer", beschrijving="Volledige aanleg achtertuin")
        for dag in range(1, 5):
            Bijlage.objects.create(klus=klus, bestand=upload(), soort=Bijlage.Soort.FOTO, datum=date(2026, 9, dag))
        klus.voorbeeld_bijlagen = list(klus.bijlagen.order_by("-datum", "-toegevoegd_op"))

        items, meer = voorbeeld.items_voor_stapel(klus)

        self.assertEqual(len(items), 3)
        self.assertEqual(meer, 2)  # 4 foto's + 1 notitie = 5 stuks inhoud, 3 getoond -> 2 meer
        self.assertEqual(items[0]["soort"], "notitie")
        self.assertEqual(items[-1].datum, date(2026, 9, 4))  # meest recente foto, voorste laag


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
class PostVerwijderenTest(TestCase):
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

    def post_van_sam(self):
        self.client.force_login(self.sam)
        self.client.post(
            reverse("bijlage_toevoegen"),
            {"bestanden": [upload("een.jpg"), upload("twee.jpg"), upload("drie.jpg")]},
        )
        return Bijlage.objects.first().batch

    def test_verwijdert_alle_fotos_van_de_post(self):
        batch = self.post_van_sam()
        self.client.post(reverse("post_verwijderen", args=[batch]))
        self.assertFalse(Bijlage.objects.filter(batch=batch).exists())

    def test_ander_mag_andermans_post_niet_verwijderen(self):
        batch = self.post_van_sam()
        self.client.force_login(self.joep)
        self.assertEqual(
            self.client.post(reverse("post_verwijderen", args=[batch])).status_code, 404
        )
        self.assertEqual(Bijlage.objects.filter(batch=batch).count(), 3)

    def test_eigenaar_mag_andermans_post_wel_verwijderen(self):
        batch = self.post_van_sam()
        self.client.force_login(self.maarten)
        self.client.post(reverse("post_verwijderen", args=[batch]))
        self.assertFalse(Bijlage.objects.filter(batch=batch).exists())

    def test_verwijderen_kan_niet_met_een_gewone_link(self):
        batch = self.post_van_sam()
        self.assertEqual(
            self.client.get(reverse("post_verwijderen", args=[batch])).status_code, 405
        )
        self.assertEqual(Bijlage.objects.filter(batch=batch).count(), 3)

    def test_onbekende_batch_geeft_404(self):
        self.client.force_login(self.sam)
        self.assertEqual(
            self.client.post(reverse("post_verwijderen", args=[uuid.uuid4()])).status_code, 404
        )


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

    def test_document_is_inline_te_bekijken_niet_als_download(self):
        # Zonder dit forceert de browser een downloaddialoog in plaats van de
        # pdf te tonen, en daarmee is er geen preview "in de app zelf".
        self.client.force_login(self.sam)
        klus = Klus.objects.create(naam="Tuin Vermeer")
        self.client.post(
            reverse("bijlage_toevoegen"),
            {"bestanden": upload("Offerte.pdf", b"%PDF-1.4", "application/pdf"), "klus": klus.pk},
        )
        bijlage = Bijlage.objects.get()
        antwoord = self.client.get(reverse("media_bestand", args=[bijlage.bestand.name]))
        self.assertIn("inline", antwoord.headers["Content-Disposition"])
        self.assertIn("Offerte.pdf", antwoord.headers["Content-Disposition"])

    def test_document_thumbnail_krijgt_zijn_eigen_jpeg_content_type(self):
        # De thumbnail is altijd een jpg, ook van een pdf. Zonder de knip in
        # media_bestand tussen hoofdbestand en thumbnail leidt Django het
        # Content-Type af van de originele .pdf-naam ("application/pdf") in
        # plaats van van de echte, geserveerde bytes — met als gevolg dat
        # sommige mobiele browsers het plaatje niet tonen (het claimt een pdf
        # te zijn), ook al laadt het prima op de meeste desktopbrowsers.
        self.client.force_login(self.sam)
        klus = Klus.objects.create(naam="Tuin Vermeer")
        self.client.post(
            reverse("bijlage_toevoegen"),
            {"bestanden": upload("Offerte.pdf", pdf(), "application/pdf"), "klus": klus.pk},
        )
        bijlage = Bijlage.objects.get()
        self.assertTrue(bijlage.thumbnail)
        antwoord = self.client.get(reverse("media_bestand", args=[bijlage.thumbnail.name]))
        self.assertEqual(antwoord.headers["Content-Type"], "image/jpeg")


@override_settings(MEDIA_ROOT=TIJDELIJKE_MEDIA)
class DocumentToevoegenKnopTest(TestCase):
    """Het "Documenten"-tabblad en de knop erin moeten er staan vóórdat er
    ooit een document is geweest — anders is er geen zichtbare manier om de
    eerste pdf toe te voegen (zie klussen/_documentenlijst.html)."""

    @classmethod
    def setUpTestData(cls):
        cls.sam = Medewerker.objects.create_user("sam", password="x")
        cls.klus = Klus.objects.create(naam="Tuin Vermeer")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TIJDELIJKE_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.client.force_login(self.sam)

    def test_documentknop_staat_er_ook_zonder_bestaande_documenten(self):
        antwoord = self.client.get(self.klus.get_absolute_url())
        self.assertContains(antwoord, "Documenten")
        self.assertContains(antwoord, "Document toevoegen")
        self.assertContains(antwoord, "Nog geen documenten.")

    def test_geuploade_pdf_komt_in_de_documentenlijst_op_het_klusdossier(self):
        self.client.post(
            reverse("bijlage_toevoegen"),
            {"bestanden": upload("Offerte.pdf", b"%PDF-1.4", "application/pdf"), "klus": self.klus.pk},
        )
        antwoord = self.client.get(self.klus.get_absolute_url())
        self.assertContains(antwoord, "Offerte.pdf")


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

    def test_eenmalige_klus_zonder_startdatum_wordt_geweigerd(self):
        self.client.force_login(self.maarten)
        antwoord = self.client.post(reverse("klus_nieuw"), self.geldig(startdatum=""))
        self.assertEqual(antwoord.status_code, 200)
        self.assertContains(antwoord, "startdatum van de eenmalige klus")
        self.assertFalse(Klus.objects.exists())

    def test_klus_zonder_opdrachtgever_wordt_geweigerd(self):
        # Zonder opdrachtgever valt een klus buiten elke suggestie en elke
        # waarschuwing, en is "Onderhoud vaste klanten" weer de bak waarin
        # alles verdwijnt. Het modelveld blijft blank=True, dit formulier niet.
        self.client.force_login(self.maarten)
        antwoord = self.client.post(reverse("klus_nieuw"), self.geldig(opdrachtgever=""))
        self.assertEqual(antwoord.status_code, 200)
        self.assertFalse(Klus.objects.exists())

    def test_soort_staat_als_keuzepillen_bovenaan(self):
        # Geen <select> tussen de velden: dit is de keuze die bepaalt wat de
        # rest van het formulier betekent (SPEC §1, aanleg versus onderhoud).
        self.client.force_login(self.maarten)
        inhoud = self.client.get(reverse("klus_nieuw")).content.decode()
        self.assertIn('type="radio" name="soort"', inhoud)
        self.assertIn("Eenmalig", inhoud)
        self.assertIn("Onderhoud", inhoud)
        # ritme → wie → waar → naam, niet het alfabet en niet de modelvolgorde
        self.assertLess(inhoud.index('name="soort"'), inhoud.index('name="opdrachtgever"'))
        self.assertLess(inhoud.index('name="opdrachtgever"'), inhoud.index('name="adres"'))
        self.assertLess(inhoud.index('name="adres"'), inhoud.index('name="naam"'))

    def test_label_van_aanleg_is_eenmalig(self):
        # De databasewaarde blijft "aanleg"; alleen wat Maarten leest verandert,
        # want de as die dit veld beschrijft is ritme en geen soort werk.
        klus = Klus.objects.create(naam="Tuin Vermeer", soort=Klus.Soort.AANLEG)
        self.assertEqual(klus.soort, "aanleg")
        self.assertEqual(klus.get_soort_display(), "Eenmalig")

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
        # Op de url en niet op het woord "Bewerken": de knop op het dossier is
        # een potlood met een aria-label (zie _klushero.html), dus een test op
        # de tekst gaat stuk zodra het icoon verandert.
        bewerken = reverse("klus_bewerken", args=[klus.pk])
        self.client.force_login(self.sam)
        self.assertNotContains(self.client.get(reverse("klussen")), "Nieuwe klus")
        self.assertNotContains(self.client.get(klus.get_absolute_url()), bewerken)
        self.client.force_login(self.maarten)
        self.assertContains(self.client.get(reverse("klussen")), "Nieuwe klus")
        self.assertContains(self.client.get(klus.get_absolute_url()), bewerken)


@override_settings(MEDIA_ROOT=TIJDELIJKE_MEDIA)
class KlusBijlagenBijAanmakenTest(TestCase):
    """Foto's/documenten kunnen meteen op het aanmaakformulier, niet pas erna
    (klussen.forms.NieuweKlusBijlagenForm, klussen.views.klus_nieuw)."""

    @classmethod
    def setUpTestData(cls):
        cls.maarten = Medewerker.objects.create_user(
            "maarten", password="x", rol=Medewerker.Rol.EIGENAAR
        )

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TIJDELIJKE_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def geldig(self, **afwijkend):
        gegevens = {
            "naam": "Tuin Vermeer",
            "soort": Klus.Soort.AANLEG,
            "startdatum": "2026-09-14",
            "opdrachtgever": "Fam. Vermeer",
            "adres": "Dijkweg 12",
            "plaats": "Maasdijk",
            "actief": "on",
        }
        gegevens.update(afwijkend)
        return gegevens

    def test_klus_aanmaken_zonder_bestanden_werkt_gewoon(self):
        # Bestanden kiezen is geen verplichte stap.
        self.client.force_login(self.maarten)
        antwoord = self.client.post(reverse("klus_nieuw"), self.geldig())
        klus = Klus.objects.get()
        self.assertRedirects(antwoord, klus.get_absolute_url())
        self.assertFalse(klus.bijlagen.exists())

    def test_pdf_meteen_bij_het_aanmaken_toevoegen(self):
        self.client.force_login(self.maarten)
        self.client.post(
            reverse("klus_nieuw"),
            self.geldig(documenten=upload("Offerte.pdf", pdf(), "application/pdf")),
        )
        klus = Klus.objects.get()
        bijlage = klus.bijlagen.get()
        self.assertEqual(bijlage.soort, Bijlage.Soort.DOCUMENT)
        self.assertEqual(bijlage.originele_naam, "Offerte.pdf")
        self.assertEqual(bijlage.toegevoegd_door, self.maarten)

    def test_gefotografeerde_tekening_blijft_een_document(self):
        # Dit is waarom er twee velden zijn: een foto van een tekening hoort in
        # de documentenlijst en niet tussen de werkfoto's in het fotoraster.
        # Het bestand is een echte jpeg, alleen de bestemming verschilt.
        self.client.force_login(self.maarten)
        self.client.post(
            reverse("klus_nieuw"), self.geldig(documenten=upload("tekening.jpg"))
        )
        bijlage = Klus.objects.get().bijlagen.get()
        self.assertEqual(bijlage.soort, Bijlage.Soort.DOCUMENT)
        self.assertFalse(bijlage.is_foto)

    def test_foto_in_het_fotoveld_blijft_een_foto(self):
        self.client.force_login(self.maarten)
        self.client.post(reverse("klus_nieuw"), self.geldig(bestanden=upload("tuin.jpg")))
        bijlage = Klus.objects.get().bijlagen.get()
        self.assertEqual(bijlage.soort, Bijlage.Soort.FOTO)
        self.assertTrue(bijlage.thumbnail)

    def test_document_in_het_fotoveld_gaat_niet_verloren(self):
        # De offerte in het verkeerde vakje: die schuift naar de documenten in
        # plaats van geweigerd te worden. De klus staat op dat moment al, dus
        # weigeren zou betekenen dat het bestand weg is en Maarten 'm opnieuw
        # moet opzoeken.
        self.client.force_login(self.maarten)
        antwoord = self.client.post(
            reverse("klus_nieuw"),
            self.geldig(bestanden=upload("Offerte.pdf", pdf(), "application/pdf")),
            follow=True,
        )
        bijlage = Klus.objects.get().bijlagen.get()
        self.assertEqual(bijlage.soort, Bijlage.Soort.DOCUMENT)
        self.assertContains(antwoord, "Offerte.pdf staat bij de documenten")

    def test_fotos_en_documenten_tegelijk(self):
        self.client.force_login(self.maarten)
        self.client.post(
            reverse("klus_nieuw"),
            self.geldig(
                bestanden=[upload("een.jpg"), upload("twee.jpg")],
                documenten=upload("Tekening.pdf", pdf(), "application/pdf"),
            ),
        )
        klus = Klus.objects.get()
        self.assertEqual(klus.bijlagen.filter(soort=Bijlage.Soort.FOTO).count(), 2)
        self.assertEqual(klus.bijlagen.filter(soort=Bijlage.Soort.DOCUMENT).count(), 1)
        # Eigen batch per stapel: het fotoraster toont een upload van meerdere
        # bestanden als één post, en de tekening hoort daar niet in te zitten.
        fotobatches = set(klus.bijlagen.filter(soort=Bijlage.Soort.FOTO).values_list("batch", flat=True))
        document = klus.bijlagen.get(soort=Bijlage.Soort.DOCUMENT)
        self.assertEqual(len(fotobatches), 1)
        self.assertNotIn(document.batch, fotobatches)

    def test_meerdere_bestanden_tegelijk_bij_het_aanmaken(self):
        self.client.force_login(self.maarten)
        self.client.post(
            reverse("klus_nieuw"),
            self.geldig(bestanden=[upload("een.jpg"), upload("Offerte.pdf", b"%PDF-1.4", "application/pdf")]),
        )
        klus = Klus.objects.get()
        self.assertEqual(klus.bijlagen.count(), 2)

    def test_een_kapot_bestand_blokkeert_de_klus_niet(self):
        # De klus staat er al; alleen het ene bestand mislukt.
        self.client.force_login(self.maarten)
        antwoord = self.client.post(
            reverse("klus_nieuw"),
            self.geldig(bestanden=upload("stuk.jpg", b"geen plaatje")),
            follow=True,
        )
        klus = Klus.objects.get()
        self.assertRedirects(antwoord, klus.get_absolute_url())
        self.assertContains(antwoord, "stuk.jpg")
        self.assertFalse(klus.bijlagen.exists())


@override_settings(MEDIA_ROOT=TIJDELIJKE_MEDIA)
class KlussenlijstVoorbeeldTest(TestCase):
    """De klussenlijst toont dezelfde gewaaierde stapel als het startscherm
    (klussen/views.py:klus_lijst → klussen.voorbeeld.items_voor_stapel)."""

    @classmethod
    def setUpTestData(cls):
        cls.sam = Medewerker.objects.create_user("sam", password="x")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TIJDELIJKE_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.client.force_login(self.sam)

    def test_klus_met_inhoud_krijgt_een_stapel_en_zonder_inhoud_een_lege(self):
        met = Klus.objects.create(naam="Met inhoud", beschrijving="Een notitie")
        Klus.objects.create(naam="Zonder inhoud")
        self.client.post(
            reverse("bijlage_toevoegen"), {"bestanden": upload(), "klus": met.pk}
        )
        antwoord = self.client.get(reverse("klussen"))
        self.assertContains(antwoord, "voorbeeldstapel")
        self.assertContains(antwoord, "voorbeeldstapel-leeg")

    def test_meer_klussen_kosten_niet_meer_queries(self):
        # Zonder de Prefetch in klus_lijst wordt dit een query per klus.
        Klus.objects.create(naam="Klus 1")
        with CaptureQueriesContext(connection) as een:
            self.client.get(reverse("klussen"))
        for nummer in range(2, 7):
            Klus.objects.create(naam=f"Klus {nummer}")
        with CaptureQueriesContext(connection) as zes:
            self.client.get(reverse("klussen"))
        self.assertEqual(len(een), len(zes))


class TelefoonInvoerTest(TestCase):
    """Kleine dingen die op een telefoon het verschil maken en die je anders
    pas merkt als er een filmpje van 200 MB in een klusdossier staat."""

    @classmethod
    def setUpTestData(cls):
        cls.maarten = Medewerker.objects.create_user(
            "maarten", password="x", rol=Medewerker.Rol.EIGENAAR
        )

    def setUp(self):
        self.client.force_login(self.maarten)

    def test_bestandsveld_beperkt_wat_de_telefoon_aanbiedt(self):
        # Zonder accept zet iOS er "video opnemen" bij; dat bestand kan de app
        # niet verwerken en vult wel de opslag.
        antwoord = self.client.get(reverse("klus_nieuw"))
        self.assertContains(antwoord, 'accept="image/*,.pdf,.doc,.docx,.xls,.xlsx,.txt"')

    def test_naam_en_adres_krijgen_hoofdletters_per_woord(self):
        # Een telefoontoetsenbord maakt standaard alleen het eerste woord groot.
        antwoord = self.client.get(reverse("klus_nieuw"))
        inhoud = antwoord.content.decode()
        for veld in ("naam", "opdrachtgever", "adres", "plaats"):
            self.assertIn(f'name="{veld}"', inhoud)
        self.assertEqual(inhoud.count('autocapitalize="words"'), 4)


class KlusKleurTest(TestCase):
    """Automatische kleurtoewijzing bij het aanmaken van een klus (klussen.kleuren)."""

    @classmethod
    def setUpTestData(cls):
        cls.maarten = Medewerker.objects.create_user(
            "maarten", password="x", rol=Medewerker.Rol.EIGENAAR
        )

    def geldig(self, **afwijkend):
        gegevens = {
            "naam": "Tuin Vermeer",
            "soort": Klus.Soort.AANLEG,
            "startdatum": "2026-09-14",
            "opdrachtgever": "Fam. Vermeer",
            "adres": "Dijkweg 12",
            "plaats": "Maasdijk",
            "actief": "on",
        }
        gegevens.update(afwijkend)
        return gegevens

    def test_kleur_komt_uit_het_palet(self):
        self.client.force_login(self.maarten)
        self.client.post(reverse("klus_nieuw"), self.geldig())
        self.assertIn(Klus.objects.get().kleur, kleuren.PALET)

    def test_kleurkiezer_staat_niet_op_het_aanmaakformulier(self):
        self.client.force_login(self.maarten)
        antwoord = self.client.get(reverse("klus_nieuw"))
        self.assertNotContains(antwoord, 'type="color"')

    def test_kleurkiezer_staat_wel_op_het_bewerkformulier(self):
        klus = Klus.objects.create(naam="Tuin Vermeer", kleur=kleuren.PALET[0])
        self.client.force_login(self.maarten)
        antwoord = self.client.get(reverse("klus_bewerken", args=[klus.pk]))
        self.assertContains(antwoord, 'type="color"')

    def test_een_geposte_kleur_wordt_genegeerd_bij_aanmaken(self):
        # Het veld is verborgen; ook als iemand het zelf aanpast bepaalt de
        # server de kleur, niet de client.
        Klus.objects.create(naam="Bestaand", actief=True, kleur=kleuren.PALET[0])
        self.client.force_login(self.maarten)
        self.client.post(reverse("klus_nieuw"), self.geldig(kleur="#000000"))
        nieuwe = Klus.objects.exclude(naam="Bestaand").get()
        self.assertNotEqual(nieuwe.kleur, "#000000")

    def test_nieuwe_klus_krijgt_niet_de_kleur_van_een_actieve_klus(self):
        Klus.objects.create(naam="Bestaand", actief=True, kleur=kleuren.PALET[0])
        self.client.force_login(self.maarten)
        self.client.post(reverse("klus_nieuw"), self.geldig())
        nieuwe = Klus.objects.exclude(naam="Bestaand").get()
        self.assertNotEqual(nieuwe.kleur, kleuren.PALET[0])

    def test_nieuwe_klus_krijgt_niet_de_kleur_van_een_recent_afgeronde_klus(self):
        afgerond = Klus.objects.create(naam="Bestaand", actief=True, kleur=kleuren.PALET[0])
        afgerond.actief = False
        afgerond.save()
        self.assertEqual(afgerond.afgerond_op, date.today())

        self.client.force_login(self.maarten)
        self.client.post(reverse("klus_nieuw"), self.geldig())
        nieuwe = Klus.objects.exclude(naam="Bestaand").get()
        self.assertNotEqual(nieuwe.kleur, kleuren.PALET[0])

    def test_kleur_van_lang_geleden_afgeronde_klus_mag_weer_gebruikt_worden(self):
        lang_geleden = date.today() - timedelta(days=kleuren.RECENT_AFGEROND_DAGEN + 1)
        Klus.objects.create(
            naam="Bestaand", actief=False, kleur=kleuren.PALET[0], afgerond_op=lang_geleden
        )
        self.assertEqual(kleuren.volgende_kleur(), kleuren.PALET[0])

    def test_reactiveren_wist_afgerond_op(self):
        klus = Klus.objects.create(naam="Bestaand", actief=True)
        klus.actief = False
        klus.save()
        self.assertIsNotNone(klus.afgerond_op)
        klus.actief = True
        klus.save()
        self.assertIsNone(klus.afgerond_op)

    def test_leeg_palet_valt_terug_op_minst_gebruikte_kleur(self):
        for i, kleur in enumerate(kleuren.PALET):
            Klus.objects.create(naam=f"Klus {i}", actief=True, kleur=kleur)
        # Eén kleur twee keer, zodat er een duidelijk minst-drukke kleur overblijft.
        Klus.objects.create(naam="Extra", actief=True, kleur=kleuren.PALET[0])
        overgebleven = [k for k in kleuren.PALET if k != kleuren.PALET[0]]
        self.assertIn(kleuren.volgende_kleur(), overgebleven)

    def test_kleinletters_uit_de_kleurkiezer_botsen_toch_met_het_palet(self):
        # <input type=color> levert altijd kleine letters ("#95bf1d"), PALET
        # staat in hoofdletters ("#95BF1D") — zonder normaliseren ziet
        # volgende_kleur() dat niet als dezelfde kleur.
        Klus.objects.create(naam="Bestaand", actief=True, kleur=kleuren.PALET[0].lower())
        self.assertNotEqual(kleuren.volgende_kleur().upper(), kleuren.PALET[0].upper())

    def test_kleurstip_staat_in_de_klussenlijst_en_op_het_dossier(self):
        klus = Klus.objects.create(naam="Tuin Vermeer", kleur=kleuren.PALET[2])
        self.client.force_login(self.maarten)
        self.assertContains(self.client.get(reverse("klussen")), kleuren.PALET[2])
        self.assertContains(self.client.get(klus.get_absolute_url()), kleuren.PALET[2])


class KleurBackfillMigratieTest(TestCase):
    """migrations/0007_kleur_backfill.py: klussen van vóór de automatische
    kleurtoewijzing (kleur='') moeten alsnog, en elk apart, een kleur krijgen."""

    def kleur_vullen(self):
        import importlib.util

        pad = "klussen/migrations/0007_kleur_backfill.py"
        spec = importlib.util.spec_from_file_location("kleur_backfill", pad)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        class NepApps:
            def get_model(self, app_label, naam):
                return Klus

        module.kleur_vullen(NepApps(), None)

    def test_klussen_zonder_kleur_krijgen_er_allemaal_een_andere(self):
        klussen = [Klus.objects.create(naam=f"Klus {i}") for i in range(3)]
        self.kleur_vullen()
        gekregen = [Klus.objects.get(pk=k.pk).kleur for k in klussen]
        self.assertTrue(all(gekregen))
        self.assertEqual(len(gekregen), len(set(k.upper() for k in gekregen)))

    def test_bestaande_kleur_blijft_staan_en_telt_mee_als_bezet(self):
        # Kleinletters uit de kleurkiezer moeten ook hier als bezet gelden.
        oud = Klus.objects.create(naam="Al gekleurd", kleur=kleuren.PALET[0].lower())
        nieuw = Klus.objects.create(naam="Nog leeg")
        self.kleur_vullen()
        oud.refresh_from_db()
        nieuw.refresh_from_db()
        self.assertEqual(oud.kleur, kleuren.PALET[0].lower())
        self.assertNotEqual(nieuw.kleur.upper(), kleuren.PALET[0].upper())


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

    def test_medewerker_ziet_de_uren_van_collegas_niet_in_het_dossier(self):
        # Omgedraaid op 24-09-2026. SPEC §2 heeft twee helften: "een medewerker
        # ziet alleen zijn eigen uren, maar wél het volledige klusdossier".
        # Dit stond eerst op de tweede helft ("wie op welke klus heeft gewerkt
        # hoort bij het dossier"); nu op de eerste, want die gaat specifiek
        # over uren. Het gespreksverslag met Maarten geeft de doorslag: "je
        # wil niet dat iedereen ziet hoeveel uur iedereen werkt". De rest van
        # het dossier — documenten, foto's, adres — blijft voor iedereen.
        self.blok(self.joep, date(2026, 9, 7), 8, 16)
        self.client.force_login(self.sam)
        antwoord = self.client.get(self.klus.get_absolute_url())
        self.assertNotContains(antwoord, "Joep")
        self.assertContains(antwoord, "Tuin Vermeer")

    def test_functie_staat_naast_de_naam(self):
        self.blok(self.sam, date(2026, 9, 7), 8, 16)
        self.client.force_login(self.sam)
        antwoord = self.client.get(self.klus.get_absolute_url())
        self.assertContains(antwoord, "Sam de Wit")
        self.assertContains(antwoord, "Voorman")


class BekendeOpdrachtgeversTest(TestCase):
    """Wat het aanmaakformulier al weet (klussen.opdrachtgevers).

    Het adres hoort bij de klus en niet bij de opdrachtgever — bij een
    particulier valt dat samen, bij een VvE met drie terreinen niet. Deze
    module levert daarom suggesties en geen overerving.
    """

    @classmethod
    def setUpTestData(cls):
        cls.maarten = Medewerker.objects.create_user(
            "maarten", password="x", rol=Medewerker.Rol.EIGENAAR
        )

    def test_adressen_staan_bij_hun_opdrachtgever(self):
        Klus.objects.create(
            naam="Onderhoud Dijkweg", soort=Klus.Soort.ONDERHOUD,
            opdrachtgever="VvE Parkzicht", adres="Dijkweg 12", plaats="Maasdijk",
        )
        Klus.objects.create(
            naam="Onderhoud Parklaan", soort=Klus.Soort.ONDERHOUD,
            opdrachtgever="VvE Parkzicht", adres="Parklaan 4", plaats="Naaldwijk",
        )
        groepen = opdrachtgevers.bekende_opdrachtgevers()
        self.assertEqual([groep["naam"] for groep in groepen], ["VvE Parkzicht"])
        self.assertEqual(
            sorted(plek["adres"] for plek in groepen[0]["adressen"]),
            ["Dijkweg 12", "Parklaan 4"],
        )

    def test_spelling_verschilt_maar_het_is_dezelfde_klant(self):
        # Zonder dit is het de ene keer "Fam. Vermeer" en de andere keer
        # "fam.  vermeer", en is er geen koppeling meer tussen de klussen.
        Klus.objects.create(naam="Tuin", opdrachtgever="Fam. Vermeer", adres="Dijkweg 12")
        Klus.objects.create(naam="Haag", opdrachtgever="fam.  vermeer", adres="Dijkweg 99")
        groepen = opdrachtgevers.bekende_opdrachtgevers()
        self.assertEqual(len(groepen), 1)
        self.assertEqual(len(groepen[0]["adressen"]), 2)

    def test_klussen_op_een_adres_komen_mee_met_hun_label_en_link(self):
        klus = Klus.objects.create(
            naam="Onderhoud Dijkweg", soort=Klus.Soort.ONDERHOUD,
            opdrachtgever="Fam. Vermeer", adres="Dijkweg 12", plaats="Maasdijk",
        )
        plek = opdrachtgevers.bekende_opdrachtgevers()[0]["adressen"][0]
        self.assertEqual(
            plek["klussen"],
            [{"naam": "Onderhoud Dijkweg", "soort": "Onderhoud",
              "url": klus.get_absolute_url(), "actief": True}],
        )

    def test_de_klus_die_je_bewerkt_waarschuwt_niet_over_zichzelf(self):
        klus = Klus.objects.create(
            naam="Onderhoud Dijkweg", opdrachtgever="Fam. Vermeer", adres="Dijkweg 12"
        )
        self.assertEqual(opdrachtgevers.bekende_opdrachtgevers(uitgezonderd=klus), [])

    def test_klus_zonder_opdrachtgever_doet_niet_mee(self):
        Klus.objects.create(naam="Los", adres="Dijkweg 12")
        self.assertEqual(opdrachtgevers.bekende_opdrachtgevers(), [])

    def test_het_formulier_krijgt_de_gegevens_mee(self):
        # In één blok in de pagina, dus geen tweede verzoek en geen HTMX.
        Klus.objects.create(naam="Onderhoud Dijkweg", opdrachtgever="Fam. Vermeer", adres="Dijkweg 12")
        self.client.force_login(self.maarten)
        antwoord = self.client.get(reverse("klus_nieuw"))
        self.assertContains(antwoord, 'id="bekende-opdrachtgevers"')
        self.assertContains(antwoord, "Fam. Vermeer")

    def test_een_klus_met_veel_klussen_kost_een_vaste_hoeveelheid_queries(self):
        # get_absolute_url en get_soort_display mogen niet per klus een query
        # doen; met veertig onderhoudsklanten loopt dat anders hard op.
        for nummer in range(20):
            Klus.objects.create(
                naam=f"Onderhoud {nummer}", opdrachtgever=f"Klant {nummer}", adres=f"Weg {nummer}"
            )
        with CaptureQueriesContext(connection) as queries:
            opdrachtgevers.bekende_opdrachtgevers()
        self.assertEqual(len(queries), 1)


class KlussenlijstFilterTest(TestCase):
    """De filterrij boven de klussenlijst: twee gelijkwaardige groepen,
    Alles/Eenmalig/Onderhoud (ritme) en Alles/Actief/Afgerond (staat).

    SPEC §1: aanleg versus onderhoud bepaalt bijna elke ontwerpkeuze. Met een
    handvol eenmalige klussen naast tientallen onderhoudsadressen is een lijst
    die alleen op naam sorteert onbruikbaar voor allebei.
    """

    @classmethod
    def setUpTestData(cls):
        cls.sam = Medewerker.objects.create_user("sam", password="x")
        cls.eenmalig = Klus.objects.create(
            naam="Tuin Vermeer", soort=Klus.Soort.AANLEG, plaats="Maasdijk"
        )
        cls.onderhoud = Klus.objects.create(
            naam="Onderhoud Dijkweg", soort=Klus.Soort.ONDERHOUD, plaats="Maasdijk"
        )

    def setUp(self):
        self.client.force_login(self.sam)

    def namen(self, **parameters):
        antwoord = self.client.get(reverse("klussen"), parameters)
        self.assertEqual(antwoord.status_code, 200)
        return [klus.naam for klus in antwoord.context["klussen"]]

    def test_zonder_filter_staan_ze_er_allebei(self):
        self.assertCountEqual(self.namen(), ["Tuin Vermeer", "Onderhoud Dijkweg"])

    def test_alleen_onderhoud(self):
        self.assertEqual(self.namen(soort="onderhoud"), ["Onderhoud Dijkweg"])

    def test_alleen_eenmalig(self):
        self.assertEqual(self.namen(soort="aanleg"), ["Tuin Vermeer"])

    def test_onzin_valt_terug_op_alles(self):
        # Een waarde uit de url is niet te vertrouwen; alles tonen is hier de
        # veilige uitkomst, niet een lege lijst.
        self.assertCountEqual(self.namen(soort="kaboem"), ["Tuin Vermeer", "Onderhoud Dijkweg"])

    def test_filter_en_zoeken_werken_samen(self):
        Klus.objects.create(naam="Onderhoud Parklaan", soort=Klus.Soort.ONDERHOUD)
        self.assertEqual(self.namen(soort="onderhoud", q="Dijkweg"), ["Onderhoud Dijkweg"])

    def afronden(self, naam, soort):
        klus = Klus.objects.create(naam=naam, soort=soort)
        klus.actief = False
        klus.save()
        return klus

    def test_standaard_alleen_wat_loopt(self):
        # Standaard "Actief" en niet "Alles": je kijkt bijna altijd naar wat er
        # loopt. Het verschil met vroeger is dat die stand nu in beeld staat.
        self.afronden("Oude tuin", Klus.Soort.AANLEG)
        self.assertNotIn("Oude tuin", self.namen())

    def test_alles_en_afgerond_zijn_eigen_standen(self):
        self.afronden("Oude tuin", Klus.Soort.AANLEG)
        self.assertIn("Oude tuin", self.namen(scope="alles"))
        # Deze stand was kwijt toen het even een aan/uit-schakelaar was.
        self.assertEqual(self.namen(scope="afgerond"), ["Oude tuin"])

    def test_onzin_in_scope_valt_terug_op_actief(self):
        self.afronden("Oude tuin", Klus.Soort.AANLEG)
        self.assertNotIn("Oude tuin", self.namen(scope="kaboem"))

    def test_de_twee_assen_werken_samen(self):
        self.afronden("Oud onderhoud", Klus.Soort.ONDERHOUD)
        self.assertEqual(self.namen(soort="onderhoud", scope="afgerond"), ["Oud onderhoud"])
        self.assertEqual(self.namen(soort="onderhoud", scope="actief"), ["Onderhoud Dijkweg"])
        self.assertEqual(
            self.namen(soort="onderhoud", scope="alles"),
            ["Onderhoud Dijkweg", "Oud onderhoud"],
        )
        self.assertEqual(self.namen(soort="aanleg", scope="alles"), ["Tuin Vermeer"])

    def test_beide_groepen_staan_als_pillen_op_het_scherm(self):
        inhoud = self.client.get(reverse("klussen"), {"soort": "onderhoud"}).content.decode()
        for naam, waarden in (("soort", ["", "aanleg", "onderhoud"]),
                              ("scope", ["alles", "actief", "afgerond"])):
            for waarde in waarden:
                self.assertIn(f'name="{naam}" value="{waarde}"', inhoud)
        # Elke groep heeft er precies één aan: onderhoud, en de standaard actief.
        for zoek in ('value="onderhoud"', 'value="actief"'):
            plek = inhoud.index(zoek)
            self.assertIn("checked", inhoud[plek:plek + 140])

    def test_de_klus_kiezer_staat_niet_meer_op_dit_scherm(self):
        # Hij leverde hier een lijst van één klus op, terwijl je die klus in de
        # lijst eronder gewoon kunt aantikken — en hij verstopte de staat van
        # het tweede filter. Op de Galerij blijft hij wel staan.
        inhoud = self.client.get(reverse("klussen")).content.decode()
        self.assertNotIn('id="klus-kiezer"', inhoud)
        self.assertNotIn("kluskiezer.js", inhoud)
        self.assertIn('name="scope"', inhoud)

    def test_de_galerij_houdt_zijn_kiezer(self):
        inhoud = self.client.get(reverse("fotos")).content.decode()
        self.assertIn('id="klus-kiezer"', inhoud)

    def test_de_pillen_staan_op_het_scherm_met_de_juiste_aan(self):
        inhoud = self.client.get(reverse("klussen"), {"soort": "onderhoud"}).content.decode()
        self.assertIn('name="soort" value="onderhoud"', inhoud)
        self.assertIn(">Eenmalig<", inhoud)
        self.assertIn(">Alles<", inhoud)
        # het aangevinkte hoort onderhoud te zijn, niet eenmalig
        onderhoud_pil = inhoud.index('value="onderhoud"')
        self.assertIn("checked", inhoud[onderhoud_pil:onderhoud_pil + 120])

    def test_lege_uitkomst_zegt_welke_filters_niets_opleverden(self):
        # "Nog geen klussen" is onwaar als er wel klussen zijn maar niet in dit
        # filter; dan lijkt het alsof er niets bestaat.
        Klus.objects.all().update(soort=Klus.Soort.AANLEG)
        antwoord = self.client.get(reverse("klussen"), {"soort": "onderhoud"})
        self.assertContains(antwoord, "Geen lopende klussen van de soort onderhoud")
        self.assertNotContains(antwoord, "Nog geen klussen")

    def test_lege_uitkomst_noemt_ook_alleen_de_staat(self):
        antwoord = self.client.get(reverse("klussen"), {"scope": "afgerond"})
        self.assertContains(antwoord, "Geen afgeronde klussen")

    def test_zonder_filter_is_leeg_gewoon_leeg(self):
        Klus.objects.all().delete()
        antwoord = self.client.get(reverse("klussen"), {"scope": "alles"})
        self.assertContains(antwoord, "Nog geen klussen")



class KlusKiezerBijFotoPostenTest(TestCase):
    """De klus kies je in de postdialoog via de zoekbare kiezer van
    static/js/kluskiezer.js. Dit is de enige klussenlijst in de app waar ook
    de afgeronde klussen in staan, dus twee rijen pillen: soort én staat.
    Dat script leest allebei per optie uit `data-soort`/`data-staat`; zonder
    die attributen filtert er niets meer."""

    @classmethod
    def setUpTestData(cls):
        cls.sam = Medewerker.objects.create_user("sam", password="x", first_name="Sam")
        cls.lopend = Klus.objects.create(naam="Tuin Vermeer", soort=Klus.Soort.AANLEG)
        cls.klaar = Klus.objects.create(naam="Nieuwbouw Van Dijk", soort=Klus.Soort.AANLEG, actief=False)
        cls.vast = Klus.objects.create(naam="Parkzicht", soort=Klus.Soort.ONDERHOUD)

    def html(self):
        self.client.force_login(self.sam)
        return self.client.get(reverse("fotos")).content.decode()

    def test_elke_optie_draagt_soort_en_staat_mee(self):
        html = self.html()
        self.assertIn(f'value="{self.lopend.pk}" data-soort="aanleg" data-staat="actief"', html)
        self.assertIn(f'value="{self.klaar.pk}" data-soort="aanleg" data-staat="inactief"', html)
        self.assertIn(f'value="{self.vast.pk}" data-soort="onderhoud" data-staat="actief"', html)

    def test_algemeen_blijft_onder_elke_pil_staan(self):
        # De lege keuze is "Algemeen" (de foto belandt dan in de dropbox); die
        # mag geen enkele pil wegfilteren.
        self.assertIn('data-soort="altijd" data-staat="altijd"', self.html())

    def test_de_kiezer_krijgt_beide_rijen_en_het_script_wordt_geladen(self):
        html = self.html()
        self.assertIn('class="klus-kiezer klus-kiezer-veld" data-pillen="soort,staat"', html)
        self.assertIn("js/kluskiezer.js", html)


class KlusdossierUrenRechtenTest(TestCase):
    """SPEC §2: "een medewerker ziet alleen zijn eigen uren, maar wél het
    volledige klusdossier". Het tabblad Uren op een dossier toonde tot
    24-09-2026 de totalen van alle collega's, en `/uren-export/` gaf ze als
    Excel aan iedereen die was ingelogd."""

    @classmethod
    def setUpTestData(cls):
        cls.maarten = Medewerker.objects.create_user(
            "maarten", password="x", first_name="Maarten", rol=Medewerker.Rol.EIGENAAR
        )
        cls.sam = Medewerker.objects.create_user("sam", password="x", first_name="Sam")
        cls.joep = Medewerker.objects.create_user("joep", password="x", first_name="Joep")
        cls.klus = Klus.objects.create(naam="Tuin Vermeer", soort=Klus.Soort.AANLEG)
        for wie in (cls.sam, cls.joep):
            Uurblok.objects.create(
                medewerker=wie, klus=cls.klus, datum=date(2026, 9, 7),
                begintijd=time(8, 0), eindtijd=time(16, 0),
            )

    def dossier(self, wie):
        self.client.force_login(wie)
        return self.client.get(reverse("klus_detail", args=[self.klus.pk]))

    def test_medewerker_ziet_alleen_zijn_eigen_regel(self):
        antwoord = self.dossier(self.sam)
        namen = [rij["medewerker"] for rij in antwoord.context["gewerkt"]]
        self.assertEqual(namen, [self.sam])
        self.assertNotContains(antwoord, "Joep")

    def test_medewerker_zonder_uren_krijgt_geen_lijst_van_collegas(self):
        antwoord = self.dossier(self.maarten)  # eerst: de eigenaar ziet ze wel
        self.assertEqual(len(antwoord.context["gewerkt"]), 2)

        buitenstaander = Medewerker.objects.create_user("wim", password="x", first_name="Wim")
        antwoord = self.dossier(buitenstaander)
        self.assertEqual(antwoord.context["gewerkt"], [])
        self.assertContains(antwoord, "Je hebt nog geen uren op deze klus geschreven.")

    def test_eigenaar_ziet_iedereen_met_een_totaalregel(self):
        antwoord = self.dossier(self.maarten)
        self.assertFalse(antwoord.context["alleen_eigen_uren"])
        self.assertEqual(antwoord.context["totaal"]["uren"], "16:00")
        self.assertContains(antwoord, "Joep")

    def test_exportknop_staat_er_alleen_voor_de_eigenaar(self):
        url = reverse("klus_uren_export", args=[self.klus.pk])
        self.assertContains(self.dossier(self.maarten), url)
        self.assertNotContains(self.dossier(self.sam), url)

    def test_uren_export_van_een_klus_is_alleen_voor_de_eigenaar(self):
        url = reverse("klus_uren_export", args=[self.klus.pk])
        self.client.force_login(self.sam)
        # 404 en geen 403: zelfde lijn als de maandexport op /export/.
        self.assertEqual(self.client.get(url).status_code, 404)

        self.client.force_login(self.maarten)
        antwoord = self.client.get(url)
        self.assertEqual(antwoord.status_code, 200)
        self.assertTrue(antwoord.content.startswith(b"PK"))
