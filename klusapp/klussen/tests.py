import shutil
import tempfile
from datetime import date, time, timedelta
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

from . import afbeeldingen, kleuren, views, voorbeeld
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
class FotosWeergaveTest(TestCase):
    """De schakelaar op /fotos/: "los" toont alles plat, "klus" toont elke
    klus als tegel — ook zonder inhoud (zie klussen/views.py:fotos)."""

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

    def test_zonder_weergave_valt_terug_op_los(self):
        antwoord = self.client.get(reverse("fotos"))
        self.assertEqual(antwoord.context["weergave"], "los")

    def test_onbekende_weergave_valt_terug_op_los(self):
        antwoord = self.client.get(reverse("fotos"), {"weergave": "onzin"})
        self.assertEqual(antwoord.context["weergave"], "los")

    def test_losse_fotos_toont_ook_fotos_van_een_klus(self):
        # Vóór deze wijziging liet "los" alleen bijlagen zonder klus zien.
        antwoord = self.client.get(reverse("fotos"), {"weergave": "los"})
        self.assertIn(self.foto_op_klus, antwoord.context["foto_bijlagen"])
        self.assertIn(self.losse_foto, antwoord.context["foto_bijlagen"])

    def test_elke_klus_krijgt_een_tegel_ook_zonder_inhoud(self):
        # Vóór deze wijziging verborg aantal_fotos__gt=0 een kale klus.
        antwoord = self.client.get(reverse("fotos"), {"weergave": "klus"})
        namen = [klus.naam for klus in antwoord.context["klus_tegels"]]
        self.assertIn(self.klus.naam, namen)
        self.assertIn(self.lege_klus.naam, namen)

    def test_klus_zonder_inhoud_toont_lege_stapel(self):
        antwoord = self.client.get(reverse("fotos"), {"weergave": "klus"})
        self.assertContains(antwoord, "Nog geen inhoud")


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
        self.client.post(
            reverse("bijlage_toevoegen"),
            {"bestanden": upload("Offerte.pdf", b"%PDF-1.4", "application/pdf")},
        )
        bijlage = Bijlage.objects.get()
        antwoord = self.client.get(reverse("media_bestand", args=[bijlage.bestand.name]))
        self.assertIn("inline", antwoord.headers["Content-Disposition"])
        self.assertIn("Offerte.pdf", antwoord.headers["Content-Disposition"])


@override_settings(MEDIA_ROOT=TIJDELIJKE_MEDIA)
class DocumentToevoegenKnopTest(TestCase):
    """De "Documenten"-sectie en de knop erin moeten er staan vóórdat er ooit
    een document is geweest — anders is er geen zichtbare manier om de eerste
    pdf toe te voegen (zie klussen/_documentenlijst.html)."""

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
            self.geldig(bestanden=upload("Offerte.pdf", b"%PDF-1.4", "application/pdf")),
        )
        klus = Klus.objects.get()
        bijlage = klus.bijlagen.get()
        self.assertEqual(bijlage.soort, Bijlage.Soort.DOCUMENT)
        self.assertEqual(bijlage.originele_naam, "Offerte.pdf")
        self.assertEqual(bijlage.toegevoegd_door, self.maarten)

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
