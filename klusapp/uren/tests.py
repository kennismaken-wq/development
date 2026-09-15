from datetime import date, datetime, time, timedelta
from datetime import timezone as dt_timezone
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from klussen.models import Klus
from medewerkers.models import Medewerker

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
        blok = Uurblok.objects.create(
            medewerker=self.sam, klus=self.klus, datum=self.dag,
            begintijd=time(8, 0), eindtijd=time(16, 30),
        )
        html = self.client.get(f"/uren/{blok.pk}/bewerken/").content.decode()
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

    def test_chip_toont_begintijd_en_duur_en_niet_de_omschrijving(self):
        # SPEC §5: op deze breedte breekt een omschrijving in lettergrepen,
        # de kleur draagt de klus.
        Uurblok.objects.create(
            medewerker=self.sam, klus=self.klus, datum=self.maandag,
            begintijd=time(8, 0), eindtijd=time(16, 30), toelichting="Bestrating uitgevlakt",
        )
        self.client.force_login(self.maarten)
        antwoord = self.client.get("/planbord/?dag=2026-09-09")
        self.assertContains(antwoord, ">08:00<")
        self.assertContains(antwoord, ">8:30<")
        self.assertNotContains(antwoord, "Bestrating uitgevlakt")

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


class MijnOverzichtTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.maarten = Medewerker.objects.create_user(
            "maarten", password="x", first_name="Maarten", rol=Medewerker.Rol.EIGENAAR
        )
        cls.sam = Medewerker.objects.create_user("sam", password="x", first_name="Sam")
        cls.klus = Klus.objects.create(naam="Tuin Vermeer", soort=Klus.Soort.AANLEG)
        cls.haag = Klus.objects.create(naam="Haag Jansen", soort=Klus.Soort.ONDERHOUD)

    def blok(self, medewerker, dag, begin, eind, klus=None):
        return Uurblok.objects.create(
            medewerker=medewerker, klus=klus or self.klus, datum=dag,
            begintijd=begin, eindtijd=eind,
        )

    def test_inloggen_vereist(self):
        antwoord = self.client.get("/overzicht/")
        self.assertEqual(antwoord.status_code, 302)

    def test_medewerker_ziet_zijn_eigen_uren_per_klus_en_per_dag(self):
        self.blok(self.sam, date(2026, 9, 7), time(8, 0), time(12, 0))
        self.blok(self.sam, date(2026, 9, 8), time(8, 0), time(9, 30), klus=self.haag)
        self.client.force_login(self.sam)
        antwoord = self.client.get("/overzicht/?dag=2026-09-07")
        self.assertEqual(antwoord.context["totaal_waarde"], "5:30")
        per_klus = {rij["klus"]: rij["uren"] for rij in antwoord.context["klusrijen"]}
        self.assertEqual(per_klus, {self.klus: "4:00", self.haag: "1:30"})
        per_dag = {rij["datum"]: rij["uren"] for rij in antwoord.context["dagrijen"]}
        self.assertEqual(per_dag, {date(2026, 9, 7): "4:00", date(2026, 9, 8): "1:30"})

    def test_medewerker_die_een_ander_opvraagt_ziet_zichzelf(self):
        # Stilzwijgend terugvallen, geen 404: de eigenaar deelt links naar dit
        # scherm en een foutpagina levert alleen telefoontjes op. Zien doet hij
        # er nog steeds niets van.
        self.blok(self.sam, date(2026, 9, 7), time(8, 0), time(12, 0))
        self.blok(self.maarten, date(2026, 9, 7), time(8, 0), time(17, 0))
        self.client.force_login(self.sam)
        antwoord = self.client.get(f"/overzicht/?dag=2026-09-07&medewerker={self.maarten.pk}")
        self.assertEqual(antwoord.status_code, 200)
        self.assertEqual(antwoord.context["medewerker"], self.sam)
        self.assertEqual(antwoord.context["totaal_waarde"], "4:00")

    def test_eigenaar_kiest_een_medewerker(self):
        self.blok(self.sam, date(2026, 9, 7), time(8, 0), time(12, 0))
        self.client.force_login(self.maarten)
        antwoord = self.client.get(f"/overzicht/?dag=2026-09-07&medewerker={self.sam.pk}")
        self.assertEqual(antwoord.context["medewerker"], self.sam)
        self.assertEqual(antwoord.context["totaal_waarde"], "4:00")
        self.assertTrue(antwoord.context["mag_kiezen"])

    def test_week_loopt_door_over_de_maandgrens(self):
        # 28 september is een maandag; die week loopt door tot 4 oktober.
        self.blok(self.sam, date(2026, 9, 30), time(8, 0), time(12, 0))
        self.blok(self.sam, date(2026, 10, 1), time(8, 0), time(11, 0))
        self.client.force_login(self.sam)
        antwoord = self.client.get("/overzicht/?weergave=week&dag=2026-09-30")
        self.assertEqual(antwoord.context["begin"], date(2026, 9, 28))
        self.assertEqual(antwoord.context["eind"], date(2026, 10, 4))
        self.assertEqual(antwoord.context["totaal_waarde"], "7:00")

    def test_maand_telt_alleen_die_kalendermaand(self):
        self.blok(self.sam, date(2026, 9, 30), time(8, 0), time(12, 0))
        self.blok(self.sam, date(2026, 10, 1), time(8, 0), time(11, 0))
        self.client.force_login(self.sam)
        antwoord = self.client.get("/overzicht/?weergave=maand&dag=2026-09-30")
        self.assertEqual(antwoord.context["begin"], date(2026, 9, 1))
        self.assertEqual(antwoord.context["eind"], date(2026, 9, 30))
        self.assertEqual(antwoord.context["totaal_waarde"], "4:00")

        oktober = self.client.get("/overzicht/?weergave=maand&dag=2026-10-15")
        self.assertEqual(oktober.context["totaal_waarde"], "3:00")

    def test_maandnavigatie_naar_vorige_en_volgende_maand(self):
        self.client.force_login(self.sam)
        antwoord = self.client.get("/overzicht/?weergave=maand&dag=2026-12-15")
        self.assertEqual(antwoord.context["vorige"], date(2026, 11, 1))
        self.assertEqual(antwoord.context["volgende"], date(2027, 1, 1))

    def test_medewerker_krijgt_geen_keuzelijst(self):
        self.client.force_login(self.sam)
        antwoord = self.client.get("/overzicht/")
        self.assertFalse(antwoord.context["mag_kiezen"])
        self.assertNotContains(antwoord, 'name="medewerker"')


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
