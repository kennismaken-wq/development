import shutil
from datetime import date, datetime, time, timedelta
from datetime import timezone as dt_timezone
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from . import kalender

from klussen.models import Bijlage, Klus
from klussen.tests import TIJDELIJKE_MEDIA, upload
from medewerkers.models import Medewerker

from . import export, totalen
from .models import Aanwezigheid, Uurblok


class UurblokTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sam = Medewerker.objects.create_user("sam", password="x", first_name="Sam")
        cls.klus = Klus.objects.create(naam="Tuin Vermeer", soort=Klus.Soort.AANLEG)

    def blok(self, begin, eind, dag=date(2026, 9, 7)):
        return Uurblok(medewerker=self.sam, klus=self.klus, datum=dag, begintijd=begin, eindtijd=eind)

    def test_duur_in_minuten(self):
        self.assertEqual(self.blok(time(8, 0), time(16, 30)).duur_minuten, 510)

    def test_eindtijd_moet_na_begintijd(self):
        with self.assertRaises(ValidationError):
            self.blok(time(16, 0), time(8, 0)).clean()

    def test_database_weigert_omgekeerd_blok(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.blok(time(16, 0), time(8, 0)).save()

    def test_meerdere_blokken_op_een_dag(self):
        # Bij onderhoud doet iemand zes tot acht adressen op een dag.
        self.blok(time(8, 0), time(9, 30)).save()
        self.blok(time(9, 45), time(11, 0)).save()
        self.assertEqual(Uurblok.objects.filter(medewerker=self.sam).count(), 2)


class AanwezigheidTest(TestCase):
    def test_een_registratie_per_dag(self):
        sam = Medewerker.objects.create_user("sam", password="x")
        Aanwezigheid.objects.create(medewerker=sam, datum=date(2026, 9, 7), aanwezig=True)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Aanwezigheid.objects.create(medewerker=sam, datum=date(2026, 9, 7), aanwezig=False)


class UrenSchrijvenTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sam = Medewerker.objects.create_user("sam", password="x", first_name="Sam")
        cls.joep = Medewerker.objects.create_user("joep", password="x", first_name="Joep")
        cls.klus = Klus.objects.create(naam="Tuin Vermeer", soort=Klus.Soort.AANLEG)
        cls.oude_klus = Klus.objects.create(naam="Afgeronde klus", actief=False)
        cls.dag = date(2026, 9, 7)

    def setUp(self):
        self.client.force_login(self.sam)

    def test_inloggen_vereist(self):
        self.client.logout()
        antwoord = self.client.get("/uren/")
        self.assertEqual(antwoord.status_code, 302)

    def test_uren_toevoegen(self):
        antwoord = self.client.post(
            "/uren/nieuw/",
            {
                "klus": self.klus.pk,
                "datum": "2026-09-07",
                "begintijd": "08:00",
                "eindtijd": "16:30",
                "toelichting": "Bestrating uitgevlakt",
            },
        )
        self.assertEqual(antwoord.status_code, 302)
        blok = Uurblok.objects.get()
        self.assertEqual(blok.medewerker, self.sam)
        self.assertEqual(blok.duur_minuten, 510)

    def test_omgekeerde_tijden_worden_geweigerd(self):
        antwoord = self.client.post(
            "/uren/nieuw/",
            {"klus": self.klus.pk, "datum": "2026-09-07", "begintijd": "16:00", "eindtijd": "08:00"},
        )
        self.assertEqual(antwoord.status_code, 200)
        self.assertContains(antwoord, "eindtijd moet na de begintijd")
        self.assertFalse(Uurblok.objects.exists())

    def test_alleen_eigen_uren_in_beeld(self):
        Uurblok.objects.create(
            medewerker=self.joep, klus=self.klus, datum=self.dag,
            begintijd=time(8, 0), eindtijd=time(16, 0), toelichting="Werk van Joep",
        )
        antwoord = self.client.get("/uren/?dag=2026-09-07&weergave=week")
        self.assertNotContains(antwoord, "Werk van Joep")

    def test_blok_van_ander_niet_te_bewerken(self):
        blok = Uurblok.objects.create(
            medewerker=self.joep, klus=self.klus, datum=self.dag,
            begintijd=time(8, 0), eindtijd=time(16, 0),
        )
        self.assertEqual(self.client.get(f"/uren/{blok.pk}/").status_code, 404)
        self.assertEqual(self.client.post(f"/uren/{blok.pk}/verwijderen/").status_code, 404)
        self.assertTrue(Uurblok.objects.filter(pk=blok.pk).exists())

    def test_volgend_blok_begint_waar_vorige_ophield(self):
        Uurblok.objects.create(
            medewerker=self.sam, klus=self.klus, datum=self.dag,
            begintijd=time(8, 0), eindtijd=time(9, 30),
        )
        antwoord = self.client.get("/uren/nieuw/?dag=2026-09-07")
        self.assertEqual(antwoord.context["formulier"].initial["begintijd"], time(9, 30))

    def test_afgeronde_klussen_niet_kiesbaar(self):
        antwoord = self.client.get("/uren/nieuw/")
        keuzes = antwoord.context["formulier"].fields["klus"].queryset
        self.assertIn(self.klus, keuzes)
        self.assertNotIn(self.oude_klus, keuzes)

    def test_week_en_dagtotalen(self):
        for begin, eind in [(time(8, 0), time(9, 30)), (time(10, 0), time(12, 15))]:
            Uurblok.objects.create(
                medewerker=self.sam, klus=self.klus, datum=self.dag, begintijd=begin, eindtijd=eind
            )
        # een dag verderop in dezelfde week telt mee in het weektotaal
        Uurblok.objects.create(
            medewerker=self.sam, klus=self.klus, datum=self.dag + timedelta(days=1),
            begintijd=time(8, 0), eindtijd=time(9, 0),
        )
        antwoord = self.client.get("/uren/?dag=2026-09-07&weergave=week")
        self.assertEqual(antwoord.context["weektotaal"], "4:45")
        maandag = antwoord.context["dagen"][0]
        self.assertEqual(maandag["datum"], self.dag)
        self.assertEqual(maandag["totaal"], "3:45")

    def test_week_toont_zeven_dagen_vanaf_maandag(self):
        antwoord = self.client.get("/uren/?dag=2026-09-10&weergave=week")   # een donderdag
        dagen = antwoord.context["dagen"]
        self.assertEqual(len(dagen), 7)
        self.assertEqual(dagen[0]["datum"], date(2026, 9, 7))
        self.assertEqual(dagen[6]["datum"], date(2026, 9, 13))

    def test_slepen_vult_begin_en_eindtijd_in(self):
        antwoord = self.client.get("/uren/nieuw/?dag=2026-09-07&van=08:30&tot=11:00")
        beginwaarden = antwoord.context["formulier"].initial
        self.assertEqual(beginwaarden["begintijd"], time(8, 30))
        self.assertEqual(beginwaarden["eindtijd"], time(11, 0))

    def test_blok_krijgt_plek_in_het_raster(self):
        Uurblok.objects.create(
            medewerker=self.sam, klus=self.klus, datum=self.dag,
            begintijd=time(8, 0), eindtijd=time(9, 0),
        )
        antwoord = self.client.get("/uren/?dag=2026-09-07&weergave=week")
        getekend = antwoord.context["dagen"][0]["getekend"][0]
        # 08:00 is vier halve uren na 06:00, elk 26px hoog
        self.assertEqual(getekend["top"], 4 * 26)
        self.assertEqual(getekend["hoogte"], 2 * 26 - 2)

    def test_bestaand_blok_vult_datum_en_tijden_in(self):
        # Een HTML-datumveld toont alleen jjjj-mm-dd; met het Nederlandse
        # formaat zou het veld leeg binnenkomen en de datum verdwijnen.
        # GET naar .../bewerken/ is geen los scherm meer maar een redirect
        # naar hetzelfde detailscherm, opengezet (zie uren.views.uurblok_bewerken).
        blok = Uurblok.objects.create(
            medewerker=self.sam, klus=self.klus, datum=self.dag,
            begintijd=time(8, 0), eindtijd=time(16, 30),
        )
        html = self.client.get(f"/uren/{blok.pk}/bewerken/", follow=True).content.decode()
        self.assertIn('value="2026-09-07"', html)
        self.assertIn('value="08:00"', html)
        self.assertIn('value="16:30"', html)

    def test_dag_is_de_standaardweergave(self):
        antwoord = self.client.get("/uren/?dag=2026-09-07")
        self.assertEqual(antwoord.context["weergave"], "dag")
        self.assertEqual(len(antwoord.context["dagen"]), 1)
        self.assertEqual(antwoord.context["dagen"][0]["datum"], self.dag)

    def test_dagweergave_toont_alleen_die_dag(self):
        Uurblok.objects.create(
            medewerker=self.sam, klus=self.klus, datum=self.dag,
            begintijd=time(8, 0), eindtijd=time(9, 0), toelichting="Vandaag",
        )
        Uurblok.objects.create(
            medewerker=self.sam, klus=self.klus, datum=self.dag + timedelta(days=1),
            begintijd=time(8, 0), eindtijd=time(9, 0), toelichting="Morgen",
        )
        antwoord = self.client.get("/uren/?dag=2026-09-07")
        self.assertContains(antwoord, "Vandaag")
        self.assertNotContains(antwoord, "Morgen")

    def test_maandraster_bevat_complete_weken_vanaf_maandag(self):
        antwoord = self.client.get("/uren/?weergave=maand&dag=2026-09-15")
        raster = antwoord.context["maandraster"]
        for week in raster:
            self.assertEqual(len(week), 7)
            self.assertEqual(week[0]["datum"].weekday(), 0)
        alle_datums = [dagcel["datum"] for week in raster for dagcel in week]
        self.assertIn(date(2026, 9, 1), alle_datums)
        self.assertIn(date(2026, 9, 30), alle_datums)

    def test_maandcel_toont_dagtotaal(self):
        Uurblok.objects.create(
            medewerker=self.sam, klus=self.klus, datum=date(2026, 9, 10),
            begintijd=time(8, 0), eindtijd=time(9, 30),
        )
        antwoord = self.client.get("/uren/?weergave=maand&dag=2026-09-15")
        raster = antwoord.context["maandraster"]
        cel = next(dagcel for week in raster for dagcel in week if dagcel["datum"] == date(2026, 9, 10))
        self.assertEqual(cel["totaal"], "1:30")

    def test_maandnavigatie_naar_vorige_en_volgende_maand(self):
        antwoord = self.client.get("/uren/?weergave=maand&dag=2026-09-15")
        self.assertEqual(antwoord.context["vorige"], date(2026, 8, 1))
        self.assertEqual(antwoord.context["volgende"], date(2026, 10, 1))


class UrenCompacteKopTest(TestCase):
    """De compacte kop (dropdown i.p.v. drie knoppen, swipe-doelen, "+"-knop
    i.p.v. "Uren toevoegen") — zie templates/uren/mijn_uren.html."""

    @classmethod
    def setUpTestData(cls):
        cls.sam = Medewerker.objects.create_user("sam", password="x")

    def setUp(self):
        self.client.force_login(self.sam)

    def test_dropdown_heeft_drie_weergaven_met_juiste_selectie(self):
        html = self.client.get("/uren/?dag=2026-09-07&weergave=week").content.decode()
        self.assertIn('class="weergave-kiezer"', html)
        self.assertIn(">Dag<", html)
        self.assertIn(">Week<", html)
        self.assertIn(">Maand<", html)
        self.assertIn('value="?weergave=week&dag=2026-09-07" selected', html)

    def test_swipe_doelen_staan_in_de_dagweergave(self):
        # kalender.js zoekt hierop om te weten welke kant op te navigeren.
        html = self.client.get("/uren/?dag=2026-09-07&weergave=dag").content.decode()
        self.assertIn('data-urennav="vorige"', html)
        self.assertIn('data-urennav="volgende"', html)

    def test_swipe_doelen_staan_ook_in_de_weekweergave(self):
        # De swipe zelf doet kalender.js alleen bij precies één dagkolom,
        # maar de vorige/volgende-links moeten er sowieso staan.
        html = self.client.get("/uren/?dag=2026-09-07&weergave=week").content.decode()
        self.assertIn('data-urennav="vorige"', html)
        self.assertIn('data-urennav="volgende"', html)

    def test_geen_losse_uren_toevoegen_tekstknop_meer(self):
        # Vervangen door .knop-uren-toevoegen (tekst op breed scherm, zwevend
        # "+"-knopje op een telefoon — CSS, niet twee aparte knoppen).
        html = self.client.get("/uren/?dag=2026-09-07&weergave=dag").content.decode()
        self.assertNotIn('class="knop" onclick', html)
        self.assertIn("knop-uren-toevoegen", html)
        self.assertIn("openSheet", html)

    def test_maandweergave_heeft_geen_swipe_doelen_of_toevoegknop(self):
        # De maandweergave heeft geen sleepbaar dagraster en geen eigen
        # "uren toevoegen"-knop; tikken op een dag opent die dagweergave.
        html = self.client.get("/uren/?weergave=maand&dag=2026-09-15").content.decode()
        self.assertNotIn("knop-uren-toevoegen", html)


class TijdzoneTest(TestCase):
    """`date.today()` gaf op een UTC-server na 22:00 de vorige dag terug —
    precies wanneer de mannen in de bus hun uren invullen."""

    def setUp(self):
        self.sam = Medewerker.objects.create_user("sam", password="x")
        self.client.force_login(self.sam)

    def test_na_tienen_s_avonds_is_vandaag_al_de_volgende_dag(self):
        # 22:30 UTC = 23:30 in Amsterdam, dus nog steeds 14 januari daar.
        with patch("django.utils.timezone.now", return_value=datetime(2026, 1, 14, 22, 30, tzinfo=dt_timezone.utc)):
            antwoord = self.client.get("/uren/")
        self.assertEqual(antwoord.context["vandaag"], date(2026, 1, 14))

    def test_na_middernacht_amsterdam_schuift_de_dag_mee(self):
        # 23:30 UTC = 00:30 in Amsterdam: daar is het al 15 januari.
        with patch("django.utils.timezone.now", return_value=datetime(2026, 1, 14, 23, 30, tzinfo=dt_timezone.utc)):
            antwoord = self.client.get("/uren/")
        self.assertEqual(antwoord.context["vandaag"], date(2026, 1, 15))


class PlanbordTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.maarten = Medewerker.objects.create_user(
            "maarten", password="x", first_name="Maarten", rol=Medewerker.Rol.EIGENAAR
        )
        cls.sam = Medewerker.objects.create_user("sam", password="x", first_name="Sam")
        cls.joep = Medewerker.objects.create_user("joep", password="x", first_name="Joep")
        cls.vertrokken = Medewerker.objects.create_user(
            "wim", password="x", first_name="Wim", uit_dienst_sinds=date(2026, 1, 1)
        )
        cls.klus = Klus.objects.create(naam="Tuin Vermeer", soort=Klus.Soort.AANLEG)
        cls.maandag = date(2026, 9, 7)
        cls.woensdag = date(2026, 9, 9)

    def rij_van(self, antwoord, medewerker):
        return next(rij for rij in antwoord.context["rijen"] if rij["medewerker"] == medewerker)

    def test_inloggen_vereist(self):
        antwoord = self.client.get("/planbord/")
        self.assertEqual(antwoord.status_code, 302)

    def test_medewerker_mag_er_niet_in(self):
        # 404 en geen 403: een medewerker hoeft niet te weten dat dit bestaat.
        self.client.force_login(self.sam)
        self.assertEqual(self.client.get("/planbord/").status_code, 404)

    def test_eigenaar_ziet_iedereen_op_de_juiste_plek(self):
        Uurblok.objects.create(
            medewerker=self.sam, klus=self.klus, datum=self.maandag,
            begintijd=time(8, 0), eindtijd=time(16, 30),
        )
        Uurblok.objects.create(
            medewerker=self.joep, klus=self.klus, datum=self.woensdag,
            begintijd=time(7, 30), eindtijd=time(12, 0),
        )
        self.client.force_login(self.maarten)
        antwoord = self.client.get("/planbord/?dag=2026-09-09")
        self.assertEqual(antwoord.status_code, 200)

        sam = self.rij_van(antwoord, self.sam)
        self.assertEqual(len(sam["dagen"][0]["blokken"]), 1)   # maandag
        self.assertEqual(sam["dagen"][0]["blokken"][0]["duur"], "8:30")
        self.assertEqual(sam["dagen"][2]["blokken"], [])       # woensdag
        self.assertEqual(sam["weektotaal"], "8:30")

        joep = self.rij_van(antwoord, self.joep)
        self.assertEqual(joep["dagen"][0]["blokken"], [])
        self.assertEqual(len(joep["dagen"][2]["blokken"]), 1)
        self.assertEqual(joep["weektotaal"], "4:30")

        self.assertEqual(antwoord.context["weektotaal"], "13:00")
        self.assertEqual(antwoord.context["kopdagen"][2]["totaal"], "4:30")

    def test_lege_rij_voor_wie_niets_schreef(self):
        # "Wie staat er níét ingepland" is de vraag waarvoor dit scherm bestaat.
        self.client.force_login(self.maarten)
        antwoord = self.client.get("/planbord/?dag=2026-09-09")
        self.assertEqual(self.rij_van(antwoord, self.joep)["weektotaal"], "")
        self.assertContains(antwoord, "Joep")

    def test_iemand_uit_dienst_krijgt_geen_rij(self):
        self.client.force_login(self.maarten)
        antwoord = self.client.get("/planbord/?dag=2026-09-09")
        medewerkers = [rij["medewerker"] for rij in antwoord.context["rijen"]]
        self.assertNotIn(self.vertrokken, medewerkers)

    def test_dag_verschuift_de_zeven_kolommen(self):
        self.client.force_login(self.maarten)
        antwoord = self.client.get("/planbord/?dag=2026-09-16")   # week erna
        kolommen = [kopdag["datum"] for kopdag in antwoord.context["kopdagen"]]
        self.assertEqual(len(kolommen), 7)
        self.assertEqual(kolommen[0], date(2026, 9, 14))
        self.assertEqual(kolommen[6], date(2026, 9, 20))
        rij = self.rij_van(antwoord, self.sam)
        self.assertEqual([dagcel["datum"] for dagcel in rij["dagen"]], kolommen)

    def test_blok_linkt_naar_het_detailscherm(self):
        blok = Uurblok.objects.create(
            medewerker=self.sam, klus=self.klus, datum=self.maandag,
            begintijd=time(8, 0), eindtijd=time(16, 30),
        )
        self.client.force_login(self.maarten)
        antwoord = self.client.get("/planbord/?dag=2026-09-09")
        self.assertContains(antwoord, f'href="/uren/{blok.pk}/"')

    def test_chip_toont_de_klus_en_de_uren_en_niet_de_omschrijving(self):
        # Zoals in de demo: op dit bord is de vraag "waar stond hij", dus de
        # klusnaam met het aantal uren. De begintijd zit in de tooltip en op
        # het detailscherm. De toelichting blijft eruit — SPEC §5: die breekt
        # op deze breedte in lettergrepen.
        Uurblok.objects.create(
            medewerker=self.sam, klus=self.klus, datum=self.maandag,
            begintijd=time(8, 0), eindtijd=time(16, 30), toelichting="Bestrating uitgevlakt",
        )
        self.client.force_login(self.maarten)
        antwoord = self.client.get("/planbord/?dag=2026-09-09")
        self.assertContains(antwoord, f">{self.klus.naam}<")
        self.assertContains(antwoord, ">8,5<")
        self.assertContains(antwoord, "08:00–16:30")     # in de tooltip
        self.assertNotContains(antwoord, "Bestrating uitgevlakt")

    def test_lege_dag_krijgt_een_streepje(self):
        # Een gat laat je je afvragen of het scherm klopt; een streepje zegt
        # dat er gekeken is en er niets was.
        self.client.force_login(self.maarten)
        self.assertContains(self.client.get("/planbord/?dag=2026-09-09"), "bord-leeg")

    def test_legenda_noemt_de_klussen_van_die_week(self):
        andere_klus = Klus.objects.create(naam="Haag Jansen", soort=Klus.Soort.ONDERHOUD)
        Uurblok.objects.create(
            medewerker=self.sam, klus=self.klus, datum=self.maandag,
            begintijd=time(8, 0), eindtijd=time(9, 0),
        )
        self.client.force_login(self.maarten)
        antwoord = self.client.get("/planbord/?dag=2026-09-09")
        klussen = [regel["klus"] for regel in antwoord.context["legenda"]]
        self.assertEqual(klussen, [self.klus])
        self.assertNotIn(andere_klus, klussen)


class AanwezigheidSchermTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.maarten = Medewerker.objects.create_user(
            "maarten", password="x", first_name="Maarten", rol=Medewerker.Rol.EIGENAAR
        )
        cls.sam = Medewerker.objects.create_user("sam", password="x", first_name="Sam")
        cls.joep = Medewerker.objects.create_user("joep", password="x", first_name="Joep")
        cls.vertrokken = Medewerker.objects.create_user(
            "wim", password="x", first_name="Wim", uit_dienst_sinds=date(2026, 1, 1)
        )
        cls.dag = date(2026, 9, 7)

    def dagformulier(self, **velden):
        basis = {
            f"aanwezig_{self.maarten.pk}": "",
            f"aanwezig_{self.sam.pk}": "",
            f"aanwezig_{self.joep.pk}": "",
        }
        basis.update(velden)
        return basis

    def test_inloggen_vereist(self):
        antwoord = self.client.get("/aanwezigheid/")
        self.assertEqual(antwoord.status_code, 302)

    def test_medewerker_ziet_het_scherm_maar_krijgt_geen_formulier(self):
        # Dit is het enige beheerdersscherm dat een medewerker wél mag inzien:
        # wie is er vandaag, wie is er ziek. Zetten mag hij niet.
        Aanwezigheid.objects.create(medewerker=self.sam, datum=self.dag, aanwezig=True)
        self.client.force_login(self.sam)
        antwoord = self.client.get("/aanwezigheid/?dag=2026-09-07")
        self.assertEqual(antwoord.status_code, 200)
        self.assertFalse(antwoord.context["mag_zetten"])
        self.assertNotContains(antwoord, f'name="aanwezig_{self.sam.pk}"')
        self.assertNotContains(antwoord, "Opslaan")
        self.assertContains(antwoord, "Aanwezig")

    def test_post_van_een_medewerker_verandert_niets(self):
        # De knoppen weglaten in de template is geen rechtencontrole.
        self.client.force_login(self.sam)
        antwoord = self.client.post(
            "/aanwezigheid/?dag=2026-09-07",
            self.dagformulier(**{f"aanwezig_{self.sam.pk}": "ja"}),
        )
        self.assertEqual(antwoord.status_code, 404)
        self.assertFalse(Aanwezigheid.objects.exists())

    def test_eigenaar_zet_groen_en_rood(self):
        self.client.force_login(self.maarten)
        antwoord = self.client.post(
            "/aanwezigheid/?dag=2026-09-07",
            self.dagformulier(
                **{
                    f"aanwezig_{self.sam.pk}": "ja",
                    f"aanwezig_{self.joep.pk}": "nee",
                    f"opmerking_{self.joep.pk}": "Ziek gemeld",
                }
            ),
        )
        self.assertEqual(antwoord.status_code, 302)
        self.assertEqual(Aanwezigheid.objects.count(), 2)
        self.assertTrue(Aanwezigheid.objects.get(medewerker=self.sam, datum=self.dag).aanwezig)
        joep = Aanwezigheid.objects.get(medewerker=self.joep, datum=self.dag)
        self.assertFalse(joep.aanwezig)
        self.assertEqual(joep.opmerking, "Ziek gemeld")

    def test_tweede_post_werkt_bij_in_plaats_van_te_klappen(self):
        # Op (medewerker, datum) ligt een unieke sleutel; zonder
        # update_or_create geeft een tweede verzending een IntegrityError.
        self.client.force_login(self.maarten)
        self.client.post(
            "/aanwezigheid/?dag=2026-09-07",
            self.dagformulier(**{f"aanwezig_{self.sam.pk}": "ja"}),
        )
        antwoord = self.client.post(
            "/aanwezigheid/?dag=2026-09-07",
            self.dagformulier(
                **{f"aanwezig_{self.sam.pk}": "nee", f"opmerking_{self.sam.pk}": "Tandarts"}
            ),
        )
        self.assertEqual(antwoord.status_code, 302)
        registratie = Aanwezigheid.objects.get(medewerker=self.sam, datum=self.dag)
        self.assertFalse(registratie.aanwezig)
        self.assertEqual(registratie.opmerking, "Tandarts")
        self.assertEqual(Aanwezigheid.objects.count(), 1)

    def test_keuze_wissen_haalt_de_rij_weg(self):
        # Derde stand: "nog niet ingevuld" is iets anders dan "afwezig", en
        # past niet in een BooleanField dat niet leeg mag zijn.
        Aanwezigheid.objects.create(medewerker=self.sam, datum=self.dag, aanwezig=True)
        self.client.force_login(self.maarten)
        self.client.post("/aanwezigheid/?dag=2026-09-07", self.dagformulier())
        self.assertFalse(Aanwezigheid.objects.filter(medewerker=self.sam, datum=self.dag).exists())

    def test_alleen_wie_in_dienst_is_krijgt_een_rij(self):
        self.client.force_login(self.maarten)
        antwoord = self.client.get("/aanwezigheid/?dag=2026-09-07")
        getoond = [rij["medewerker"] for rij in antwoord.context["rijen"]]
        self.assertIn(self.sam, getoond)
        self.assertNotIn(self.vertrokken, getoond)

    def test_een_andere_dag_staat_los(self):
        Aanwezigheid.objects.create(medewerker=self.sam, datum=self.dag, aanwezig=True)
        self.client.force_login(self.maarten)
        antwoord = self.client.get("/aanwezigheid/?dag=2026-09-08")
        self.assertEqual(antwoord.context["dag"], date(2026, 9, 8))
        self.assertEqual(antwoord.context["aantal_aanwezig"], 0)
        self.assertTrue(all(rij["registratie"] is None for rij in antwoord.context["rijen"]))

    def test_opslaan_gaat_terug_naar_dezelfde_dag(self):
        self.client.force_login(self.maarten)
        antwoord = self.client.post("/aanwezigheid/?dag=2026-09-07", self.dagformulier())
        self.assertEqual(antwoord.headers["Location"], "/aanwezigheid/?dag=2026-09-07")


class UurblokDetailTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sam = Medewerker.objects.create_user("sam", password="x", first_name="Sam")
        cls.joep = Medewerker.objects.create_user("joep", password="x", first_name="Joep")
        cls.maarten = Medewerker.objects.create_user(
            "maarten", password="x", first_name="Maarten", rol=Medewerker.Rol.EIGENAAR
        )
        cls.klus = Klus.objects.create(naam="Tuin Vermeer", soort=Klus.Soort.AANLEG)
        cls.blok = Uurblok.objects.create(
            medewerker=cls.sam, klus=cls.klus, datum=date(2026, 9, 7),
            begintijd=time(8, 0), eindtijd=time(16, 30), toelichting="Bestrating gelegd",
        )

    def test_inloggen_vereist(self):
        antwoord = self.client.get(f"/uren/{self.blok.pk}/")
        self.assertEqual(antwoord.status_code, 302)

    def test_eigen_blok_bekijken_met_bewerkknop(self):
        self.client.force_login(self.sam)
        antwoord = self.client.get(f"/uren/{self.blok.pk}/")
        self.assertContains(antwoord, "Bestrating gelegd")
        self.assertContains(antwoord, f"/uren/{self.blok.pk}/bewerken/")

    def test_medewerker_ziet_blok_van_ander_niet(self):
        self.client.force_login(self.joep)
        self.assertEqual(self.client.get(f"/uren/{self.blok.pk}/").status_code, 404)

    def test_eigenaar_bekijkt_wel_maar_bewerkt_niet(self):
        # Doorklikken vanaf het planbord moet werken; corrigeren van andermans
        # uren is bewust niet toegestaan.
        self.client.force_login(self.maarten)
        antwoord = self.client.get(f"/uren/{self.blok.pk}/")
        self.assertContains(antwoord, "Bestrating gelegd")
        self.assertNotContains(antwoord, f"/uren/{self.blok.pk}/bewerken/")
        self.assertEqual(self.client.get(f"/uren/{self.blok.pk}/bewerken/").status_code, 404)

    def test_uploadveld_hangt_de_bijlage_aan_dit_blok(self):
        self.client.force_login(self.sam)
        html = self.client.get(f"/uren/{self.blok.pk}/").content.decode()
        self.assertIn(f'name="uurblok" value="{self.blok.pk}"', html)


class UrenexportTest(TestCase):
    """De export ging live zonder tests. Hij gaat naar de boekhouder, dus een
    verkeerd totaal is hier duurder dan een verkeerd scherm."""

    @classmethod
    def setUpTestData(cls):
        cls.sam = Medewerker.objects.create_user("sam", password="x", first_name="Sam", last_name="de Wit")
        cls.joep = Medewerker.objects.create_user("joep", password="x", first_name="Joep", last_name="Bakker")
        cls.maarten = Medewerker.objects.create_user(
            "maarten", password="x", first_name="Maarten", rol=Medewerker.Rol.EIGENAAR
        )
        cls.klus = Klus.objects.create(
            naam="Tuin Vermeer",
            soort=Klus.Soort.AANLEG,
            opdrachtgever="Fam. Vermeer",
            adres="Dorpsstraat 12",
            plaats="Maasdijk",
        )
        for medewerker, dag, begin, eind in [
            (cls.sam, date(2026, 8, 3), time(8, 0), time(16, 30)),
            (cls.sam, date(2026, 8, 4), time(8, 0), time(12, 0)),
            (cls.joep, date(2026, 8, 3), time(9, 0), time(17, 0)),
            # buiten de maand: mag niet meetellen
            (cls.sam, date(2026, 9, 1), time(8, 0), time(16, 0)),
        ]:
            Uurblok.objects.create(
                medewerker=medewerker, klus=cls.klus, datum=dag, begintijd=begin, eindtijd=eind
            )

    def test_inloggen_vereist(self):
        self.assertEqual(self.client.get("/export/").status_code, 302)

    def test_medewerker_komt_er_niet_in(self):
        # 404 en geen 403: een medewerker hoeft niet te weten dat het bestaat.
        self.client.force_login(self.sam)
        self.assertEqual(self.client.get("/export/").status_code, 404)

    def test_eigenaar_ziet_totalen_per_medewerker(self):
        self.client.force_login(self.maarten)
        antwoord = self.client.get("/export/?maand=2026-08")
        totalen = {rij["medewerker"].username: rij["totaal"] for rij in antwoord.context["totalen"]}
        self.assertEqual(totalen, {"sam": "12:30", "joep": "8:00"})

    def test_download_levert_een_excelbestand(self):
        self.client.force_login(self.maarten)
        antwoord = self.client.get("/export/?maand=2026-08&download=1")
        self.assertEqual(
            antwoord["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn("uren-2026-08.xlsx", antwoord["Content-Disposition"])
        # PK: een xlsx is een zipbestand; zo weten we dat het echt Excel is.
        self.assertTrue(antwoord.content.startswith(b"PK"))

    def test_werkboek_telt_per_medewerker_op_met_een_eindtotaal(self):
        blokken = list(
            Uurblok.objects.filter(datum__range=(date(2026, 8, 1), date(2026, 8, 31)))
            .select_related("medewerker", "klus")
            .order_by("medewerker__first_name", "datum", "begintijd")
        )
        blad = export.werkboek_bouwen(blokken, "Uren 08-2026").active
        regels = [(rij[0].value, rij[7].value) for rij in blad.iter_rows(min_row=2)]
        self.assertIn(("Totaal Joep Bakker", 8.0), regels)
        self.assertIn(("Totaal Sam de Wit", 12.5), regels)
        self.assertEqual(regels[-1], ("Totaal alle medewerkers", 20.5))

        eerste_urenregel = next(blad.iter_rows(min_row=2))
        self.assertEqual(eerste_urenregel[3].value, "Fam. Vermeer")
        self.assertEqual(eerste_urenregel[4].value, "Dorpsstraat 12, Maasdijk")

    def test_lege_maand_geeft_een_leeg_maar_geldig_bestand(self):
        self.client.force_login(self.maarten)
        antwoord = self.client.get("/export/?maand=2026-01&download=1")
        self.assertTrue(antwoord.content.startswith(b"PK"))
        self.assertEqual(antwoord.context, None)

    def test_filteren_op_een_medewerker(self):
        self.client.force_login(self.maarten)
        antwoord = self.client.get(f"/export/?maand=2026-08&medewerker={self.joep.pk}")
        namen = [rij["medewerker"].username for rij in antwoord.context["totalen"]]
        self.assertEqual(namen, ["joep"])


class DecimaleUrenTest(TestCase):
    """Uren als getal, zoals ze op het planbord naast een klusnaam staan."""

    def test_hele_en_halve_uren(self):
        self.assertEqual(kalender.als_decimaal(480), "8")
        self.assertEqual(kalender.als_decimaal(510), "8,5")
        self.assertEqual(kalender.als_decimaal(195), "3,25")
        self.assertEqual(kalender.als_decimaal(0), "0")


@override_settings(MEDIA_ROOT=TIJDELIJKE_MEDIA)
class UurblokBijlagenBijAanmakenTest(TestCase):
    """Een foto meteen bij het invullen van de uren kunnen toevoegen, niet pas
    erna via het detailscherm (uren.forms.UurblokFotosForm, uren.views.uurblok_nieuw).
    Alleen foto's, net als de fotodropbox (klussen.forms.AlleenFotosForm) —
    geen documenten."""

    @classmethod
    def setUpTestData(cls):
        cls.sam = Medewerker.objects.create_user("sam", password="x", first_name="Sam")
        cls.klus = Klus.objects.create(naam="Tuin Vermeer", soort=Klus.Soort.AANLEG)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TIJDELIJKE_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.client.force_login(self.sam)

    def geldig(self, **afwijkend):
        gegevens = {
            "klus": self.klus.pk,
            "datum": "2026-09-07",
            "begintijd": "08:00",
            "eindtijd": "16:30",
            "toelichting": "Bestrating uitgevlakt",
        }
        gegevens.update(afwijkend)
        return gegevens

    def test_uren_zonder_foto_werkt_gewoon(self):
        # Bestanden kiezen is geen verplichte stap.
        antwoord = self.client.post("/uren/nieuw/", self.geldig())
        self.assertEqual(antwoord.status_code, 302)
        blok = Uurblok.objects.get()
        self.assertFalse(blok.bijlagen.exists())

    def test_foto_bij_de_uren_hangt_aan_het_uurblok_en_de_klus(self):
        self.client.post("/uren/nieuw/", self.geldig(bestanden=upload("werk.jpg")))
        blok = Uurblok.objects.get()
        bijlage = Bijlage.objects.get()
        self.assertEqual(bijlage.uurblok, blok)
        self.assertEqual(bijlage.klus, self.klus)
        self.assertEqual(bijlage.soort, Bijlage.Soort.FOTO)
        self.assertEqual(bijlage.toegevoegd_door, self.sam)

    def test_meerdere_fotos_tegelijk(self):
        self.client.post(
            "/uren/nieuw/", self.geldig(bestanden=[upload("een.jpg"), upload("twee.jpg")])
        )
        blok = Uurblok.objects.get()
        self.assertEqual(blok.bijlagen.count(), 2)

    def test_een_kapot_bestand_blokkeert_de_uren_niet(self):
        # De uren staan er al; alleen de foto mislukt, niet het hele blok.
        antwoord = self.client.post(
            "/uren/nieuw/", self.geldig(bestanden=upload("stuk.jpg", b"geen plaatje")), follow=True
        )
        blok = Uurblok.objects.get()
        self.assertFalse(blok.bijlagen.exists())
        self.assertContains(antwoord, "stuk.jpg")

    def test_document_wordt_geweigerd(self):
        # Alleen foto's bij de uren, net als de fotodropbox — een document
        # hoort hier niet, ook niet als iemand het bestandenveld omzeilt.
        antwoord = self.client.post(
            "/uren/nieuw/",
            self.geldig(bestanden=upload("Offerte.pdf", b"%PDF-1.4", "application/pdf")),
            follow=True,
        )
        blok = Uurblok.objects.get()
        self.assertFalse(blok.bijlagen.exists())
        self.assertContains(antwoord, "alleen een foto")

    def test_ongeldige_uren_met_foto_slaat_niets_op(self):
        # Omgekeerde tijden: het uurblok mag niet aangemaakt worden, dus ook
        # geen wees-bijlage die nergens aan hangt.
        antwoord = self.client.post(
            "/uren/nieuw/",
            self.geldig(begintijd="16:00", eindtijd="08:00", bestanden=upload("werk.jpg")),
        )
        self.assertEqual(antwoord.status_code, 200)
        self.assertFalse(Uurblok.objects.exists())
        self.assertFalse(Bijlage.objects.exists())


class MaandHeatmapTest(TestCase):
    """De maandwidget bovenaan het startscherm — zie uren/totalen.py."""

    @classmethod
    def setUpTestData(cls):
        cls.sam = Medewerker.objects.create_user("sam", password="x", first_name="Sam")
        cls.klus = Klus.objects.create(naam="Tuin Vermeer", soort=Klus.Soort.AANLEG)

    def blok(self, dag, uren):
        Uurblok.objects.create(
            medewerker=self.sam, klus=self.klus, datum=dag,
            begintijd=time(8, 0), eindtijd=time(8 + uren, 0),
        )

    def cel(self, heatmap, dag):
        return next(c for week in heatmap["weken"] for c in week if c["datum"] == dag)

    def test_drukste_dag_krijgt_de_bovenste_tint_en_een_lege_dag_geen(self):
        self.blok(date(2026, 9, 10), 8)
        self.blok(date(2026, 9, 11), 2)
        heatmap = totalen.maand_heatmap(self.sam, date(2026, 9, 23))
        self.assertEqual(self.cel(heatmap, date(2026, 9, 10))["tint"], totalen.HEATMAP_TINTEN)
        self.assertEqual(self.cel(heatmap, date(2026, 9, 11))["tint"], 1)
        self.assertEqual(self.cel(heatmap, date(2026, 9, 12))["tint"], 0)

    def test_totaal_telt_alleen_de_maand_zelf(self):
        # 31 augustus valt in de eerste week van het septemberraster en hoort
        # dus wel in beeld, maar niet in het maandtotaal.
        self.blok(date(2026, 8, 31), 4)
        self.blok(date(2026, 9, 10), 8)
        heatmap = totalen.maand_heatmap(self.sam, date(2026, 9, 23))
        self.assertEqual(heatmap["totaal"], "8:00")
        self.assertFalse(self.cel(heatmap, date(2026, 8, 31))["in_maand"])
        self.assertEqual(self.cel(heatmap, date(2026, 8, 31))["uren"], "4:00")

    def test_lege_maand_valt_niet_om(self):
        heatmap = totalen.maand_heatmap(self.sam, date(2026, 9, 23))
        self.assertEqual(heatmap["totaal"], "0:00")
        self.assertTrue(all(c["tint"] == 0 for week in heatmap["weken"] for c in week))

    def test_startscherm_toont_de_widget(self):
        self.blok(date(2026, 9, 10), 8)
        self.client.force_login(self.sam)
        with patch("medewerkers.views.date") as nep:
            nep.today.return_value = date(2026, 9, 23)
            antwoord = self.client.get("/")
        self.assertEqual(antwoord.context["maandwidget"]["totaal"], "8:00")
        self.assertContains(antwoord, "uur deze maand")
