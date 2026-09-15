from datetime import date, time, timedelta

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
        html = self.client.get(f"/uren/{blok.pk}/").content.decode()
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
