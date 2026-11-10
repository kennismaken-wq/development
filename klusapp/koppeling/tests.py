import base64
import hashlib
import io
import json
import shutil
import tempfile
import zipfile
from datetime import date, time, timedelta
from urllib.parse import parse_qs, urlsplit

from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from klussen.models import Bijlage, Klus, Notitie
from medewerkers.models import Medewerker
from uren.models import Aanwezigheid, Dagnotitie, Inzet, Klusdag, Uurblok

from .models import Autorisatiecode, Client, Koppeling

TERUG = "https://claude.ai/api/mcp/auth_callback"
VERIFIER = "dit-is-een-geheime-code-verifier-van-minstens-43-tekens-lang"
CHALLENGE = base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).rstrip(b"=").decode()


class Basis(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.maarten = Medewerker.objects.create_user(
            "maarten", password="test1234", first_name="Maarten", last_name="Morée", rol=Medewerker.Rol.EIGENAAR
        )
        cls.henk = Medewerker.objects.create_user("henk", password="test1234", first_name="Henk", last_name="de Vries")
        cls.sam = Medewerker.objects.create_user("sam", password="test1234", first_name="Sam", last_name="Bakker")

    def registreer(self, uris=(TERUG,)):
        antwoord = self.client.post(
            reverse("oauth_registreren"),
            json.dumps({"client_name": "Claude", "redirect_uris": list(uris)}),
            content_type="application/json",
        )
        return antwoord

    def toestaan_parameters(self, client_id, **anders):
        return {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": TERUG,
            "code_challenge": CHALLENGE,
            "code_challenge_method": "S256",
            "state": "xyz",
            "scope": "lezen",
            **anders,
        }

    def koppel(self, wie=None):
        """De hele flow zoals Claude hem doorloopt; geeft (access, refresh, client_id)."""
        client_id = self.registreer().json()["client_id"]
        self.client.force_login(wie or self.maarten)
        antwoord = self.client.post(reverse("oauth_toestaan"), {**self.toestaan_parameters(client_id), "actie": "toestaan"})
        self.assertEqual(antwoord.status_code, 302)
        terug = parse_qs(urlsplit(antwoord["Location"]).query)
        self.assertEqual(terug["state"], ["xyz"])
        self.client.logout()
        tokens = self.client.post(
            reverse("oauth_token"),
            {"grant_type": "authorization_code", "code": terug["code"][0], "redirect_uri": TERUG, "client_id": client_id, "code_verifier": VERIFIER},
        ).json()
        return tokens["access_token"], tokens["refresh_token"], client_id

    def mcp(self, token, methode, params=None, bericht_id=1):
        return self.client.post(
            "/mcp",
            json.dumps({"jsonrpc": "2.0", "id": bericht_id, "method": methode, "params": params or {}}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

    def tool(self, token, naam, **argumenten):
        antwoord = self.mcp(token, "tools/call", {"name": naam, "arguments": argumenten})
        self.assertEqual(antwoord.status_code, 200, antwoord.content)
        return antwoord.json()["result"]


class MetadataTests(Basis):
    def test_protected_resource(self):
        gegevens = self.client.get("/.well-known/oauth-protected-resource").json()
        self.assertEqual(gegevens["resource"], "http://testserver/mcp")
        self.assertEqual(gegevens["authorization_servers"], ["http://testserver"])

    def test_authorization_server(self):
        gegevens = self.client.get("/.well-known/oauth-authorization-server").json()
        self.assertEqual(gegevens["token_endpoint"], "http://testserver/oauth/token/")
        self.assertEqual(gegevens["code_challenge_methods_supported"], ["S256"])

    def test_zonder_token_401_met_verwijzing(self):
        antwoord = self.mcp("", "tools/list")
        self.assertEqual(antwoord.status_code, 401)
        self.assertIn("/.well-known/oauth-protected-resource", antwoord["WWW-Authenticate"])

    def test_get_op_mcp_niet_toegestaan(self):
        self.assertEqual(self.client.get("/mcp").status_code, 405)


class OAuthTests(Basis):
    def test_hele_flow_en_lezen(self):
        access, _, _ = self.koppel()
        antwoord = self.mcp(access, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}})
        self.assertEqual(antwoord.json()["result"]["protocolVersion"], "2025-06-18")
        namen = [t["name"] for t in self.mcp(access, "tools/list").json()["result"]["tools"]]
        self.assertIn("uren", namen)
        self.assertNotIn("functie", self.mcp(access, "tools/list").json()["result"]["tools"][0])

    def test_alle_tools_zijn_alleen_lezen(self):
        access, _, _ = self.koppel()
        for tool in self.mcp(access, "tools/list").json()["result"]["tools"]:
            self.assertTrue(tool["annotations"]["readOnlyHint"], tool["name"])

    def test_tokens_niet_leesbaar_opgeslagen(self):
        access, refresh, _ = self.koppel()
        koppeling = Koppeling.objects.get()
        self.assertNotIn(access, (koppeling.access_hash, koppeling.refresh_hash))
        self.assertNotIn(refresh, (koppeling.access_hash, koppeling.refresh_hash))

    def test_registreren_alleen_naar_claude(self):
        self.assertEqual(self.registreer(["https://kwaadwillend.example/terug"]).status_code, 400)
        self.assertEqual(self.registreer(["http://claude.ai/terug"]).status_code, 400)
        self.assertEqual(self.registreer(["https://claude.ai.kwaad.example/terug"]).status_code, 400)
        self.assertEqual(self.registreer(["http://localhost:6274/callback"]).status_code, 201)
        self.assertEqual(self.registreer(["https://claude.com/api/mcp/auth_callback"]).status_code, 201)

    def test_toestaan_vraagt_inloggen(self):
        client_id = self.registreer().json()["client_id"]
        antwoord = self.client.get(reverse("oauth_toestaan"), self.toestaan_parameters(client_id))
        self.assertEqual(antwoord.status_code, 302)
        self.assertIn(reverse("inloggen"), antwoord["Location"])

    def test_scherm_toont_toestaan(self):
        client_id = self.registreer().json()["client_id"]
        self.client.force_login(self.maarten)
        antwoord = self.client.get(reverse("oauth_toestaan"), self.toestaan_parameters(client_id))
        self.assertContains(antwoord, "Toestaan")
        self.assertContains(antwoord, "claude.ai")

    def test_medewerker_kan_niet_koppelen(self):
        client_id = self.registreer().json()["client_id"]
        self.client.force_login(self.sam)
        antwoord = self.client.post(reverse("oauth_toestaan"), {**self.toestaan_parameters(client_id), "actie": "toestaan"})
        self.assertEqual(antwoord.status_code, 403)
        self.assertContains(antwoord, "rol eigenaar", status_code=403)
        self.assertFalse(Autorisatiecode.objects.exists())

    def test_ander_terugadres_dan_aangemeld_stuurt_niet_door(self):
        client_id = self.registreer().json()["client_id"]
        self.client.force_login(self.maarten)
        antwoord = self.client.get(
            reverse("oauth_toestaan"), self.toestaan_parameters(client_id, redirect_uri="https://claude.ai/ander")
        )
        self.assertEqual(antwoord.status_code, 400)

    def test_zonder_pkce_fout_terug(self):
        client_id = self.registreer().json()["client_id"]
        self.client.force_login(self.maarten)
        antwoord = self.client.get(reverse("oauth_toestaan"), self.toestaan_parameters(client_id, code_challenge_method="plain"))
        self.assertEqual(antwoord.status_code, 302)
        self.assertIn("error=invalid_request", antwoord["Location"])

    def test_weigeren(self):
        client_id = self.registreer().json()["client_id"]
        self.client.force_login(self.maarten)
        antwoord = self.client.post(reverse("oauth_toestaan"), {**self.toestaan_parameters(client_id), "actie": "weigeren"})
        self.assertIn("error=access_denied", antwoord["Location"])
        self.assertFalse(Autorisatiecode.objects.exists())

    def _code(self):
        client_id = self.registreer().json()["client_id"]
        self.client.force_login(self.maarten)
        antwoord = self.client.post(reverse("oauth_toestaan"), {**self.toestaan_parameters(client_id), "actie": "toestaan"})
        self.client.logout()
        return client_id, parse_qs(urlsplit(antwoord["Location"]).query)["code"][0]

    def test_verkeerde_verifier(self):
        client_id, code = self._code()
        antwoord = self.client.post(
            reverse("oauth_token"),
            {"grant_type": "authorization_code", "code": code, "redirect_uri": TERUG, "client_id": client_id, "code_verifier": "x" * 50},
        )
        self.assertEqual(antwoord.json()["error"], "invalid_grant")

    def test_code_eenmalig(self):
        client_id, code = self._code()
        gegevens = {"grant_type": "authorization_code", "code": code, "redirect_uri": TERUG, "client_id": client_id, "code_verifier": VERIFIER}
        self.assertEqual(self.client.post(reverse("oauth_token"), gegevens).status_code, 200)
        self.assertEqual(self.client.post(reverse("oauth_token"), gegevens).status_code, 400)

    def test_verlopen_code(self):
        client_id, code = self._code()
        Autorisatiecode.objects.update(verloopt_op=timezone.now() - timedelta(seconds=1))
        antwoord = self.client.post(
            reverse("oauth_token"),
            {"grant_type": "authorization_code", "code": code, "redirect_uri": TERUG, "client_id": client_id, "code_verifier": VERIFIER},
        )
        self.assertEqual(antwoord.status_code, 400)

    def test_vernieuwen_wisselt_beide_tokens(self):
        access, refresh, client_id = self.koppel()
        nieuw = self.client.post(reverse("oauth_token"), {"grant_type": "refresh_token", "refresh_token": refresh, "client_id": client_id}).json()
        self.assertEqual(self.mcp(access, "ping").status_code, 401)
        self.assertEqual(self.mcp(nieuw["access_token"], "ping").status_code, 200)
        oud = self.client.post(reverse("oauth_token"), {"grant_type": "refresh_token", "refresh_token": refresh, "client_id": client_id})
        self.assertEqual(oud.status_code, 400)

    def test_verlopen_access_token(self):
        access, _, _ = self.koppel()
        Koppeling.objects.update(access_verloopt_op=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.mcp(access, "ping").status_code, 401)

    def test_geen_eigenaar_meer_dan_geen_toegang(self):
        access, refresh, client_id = self.koppel()
        self.maarten.rol = Medewerker.Rol.MEDEWERKER
        self.maarten.save()
        self.assertEqual(self.mcp(access, "ping").status_code, 401)
        antwoord = self.client.post(reverse("oauth_token"), {"grant_type": "refresh_token", "refresh_token": refresh, "client_id": client_id})
        self.assertEqual(antwoord.status_code, 400)

    def test_oude_ongebruikte_aanmeldingen_worden_opgeruimd(self):
        self.registreer()
        Client.objects.update(aangemaakt_op=timezone.now() - timedelta(days=2))
        self.koppel()
        self.assertEqual(Client.objects.count(), 1)


class IntrekkenTests(Basis):
    def test_scherm_alleen_voor_eigenaar(self):
        self.client.force_login(self.sam)
        self.assertEqual(self.client.get(reverse("claude_koppeling")).status_code, 404)
        self.client.force_login(self.maarten)
        antwoord = self.client.get(reverse("claude_koppeling"))
        self.assertContains(antwoord, "http://testserver/mcp")
        self.assertContains(antwoord, "Er is nu geen Claude gekoppeld")

    def test_profiel_linkt_alleen_voor_eigenaar(self):
        self.client.force_login(self.maarten)
        self.assertContains(self.client.get(reverse("mijn_profiel")), reverse("claude_koppeling"))
        self.client.force_login(self.sam)
        self.assertNotContains(self.client.get(reverse("mijn_profiel")), reverse("claude_koppeling"))

    def test_intrekken_werkt_meteen(self):
        access, refresh, client_id = self.koppel()
        self.client.force_login(self.maarten)
        self.assertContains(self.client.get(reverse("claude_koppeling")), "Intrekken")
        koppeling = Koppeling.objects.get()
        self.client.post(reverse("claude_intrekken", args=[koppeling.pk]))
        self.assertEqual(self.mcp(access, "ping").status_code, 401)
        antwoord = self.client.post(reverse("oauth_token"), {"grant_type": "refresh_token", "refresh_token": refresh, "client_id": client_id})
        self.assertEqual(antwoord.status_code, 400)
        self.assertContains(self.client.get(reverse("claude_koppeling")), "Er is nu geen Claude gekoppeld")

    def test_medewerker_kan_niet_intrekken(self):
        self.koppel()
        self.client.force_login(self.sam)
        self.assertEqual(self.client.post(reverse("claude_intrekken", args=[Koppeling.objects.get().pk])).status_code, 404)
        self.assertIsNone(Koppeling.objects.get().ingetrokken_op)


class ProtocolTests(Basis):
    def setUp(self):
        self.access, _, _ = self.koppel()

    def test_notificatie_geeft_202(self):
        antwoord = self.client.post(
            "/mcp",
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access}",
        )
        self.assertEqual(antwoord.status_code, 202)

    def test_onbekende_methode(self):
        self.assertEqual(self.mcp(self.access, "iets/anders").json()["error"]["code"], -32601)

    def test_onbekende_tool(self):
        self.assertEqual(self.mcp(self.access, "tools/call", {"name": "wis_alles"}).json()["error"]["code"], -32602)

    def test_lijst_van_berichten(self):
        antwoord = self.client.post(
            "/mcp",
            json.dumps([{"jsonrpc": "2.0", "id": 1, "method": "ping"}, {"jsonrpc": "2.0", "id": 2, "method": "ping"}]),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access}",
        )
        self.assertEqual([a["id"] for a in antwoord.json()], [1, 2])

    def test_kapotte_json(self):
        antwoord = self.client.post("/mcp", "{", content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {self.access}")
        self.assertEqual(antwoord.json()["error"]["code"], -32700)

    def test_laatst_gebruikt_bijgehouden(self):
        self.mcp(self.access, "ping")
        self.assertIsNotNone(Koppeling.objects.get().laatst_gebruikt_op)


class ToolData(Basis):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.tuin = Klus.objects.create(naam="Tuin Vermeer", opdrachtgever="Fam. Vermeer", adres="Breestraat 1", plaats="Leiden", email="vermeer@example.nl")
        cls.park = Klus.objects.create(naam="Parkonderhoud", soort=Klus.Soort.ONDERHOUD, opdrachtgever="Gemeente Delft", plaats="Delft")
        cls.oud = Klus.objects.create(naam="Oude vijver", opdrachtgever="fam. vermeer", plaats="Leiden", actief=False)
        cls.gisteren = date(2026, 11, 9)
        Uurblok.objects.create(medewerker=cls.henk, klus=cls.tuin, datum=cls.gisteren, begintijd=time(8), eindtijd=time(12), toelichting="bestrating", extra_werk="3 palen")
        Uurblok.objects.create(medewerker=cls.henk, klus=cls.park, datum=cls.gisteren, begintijd=time(13), eindtijd=time(16, 30))
        Uurblok.objects.create(medewerker=cls.sam, klus=cls.tuin, datum=date(2026, 11, 2), begintijd=time(8), eindtijd=time(17))
        Notitie.objects.create(klus=cls.tuin, tekst="Sleutel bij de buren", geschreven_door=cls.sam)
        Klusdag.objects.create(klus=cls.tuin, datum=date(2026, 11, 12), notitie="met kraan")
        Inzet.objects.create(medewerker=cls.henk, klus=cls.tuin, datum=date(2026, 11, 12))
        Dagnotitie.objects.create(datum=date(2026, 11, 13), tekst="op tijd weg")
        Aanwezigheid.objects.create(medewerker=cls.sam, datum=date(2026, 11, 11), aanwezig=False, reden="ziek")

    def setUp(self):
        self.access, _, _ = self.koppel()


class ToolTests(ToolData):
    def test_vandaag(self):
        uitkomst = self.tool(self.access, "vandaag")["structuredContent"]
        self.assertEqual(uitkomst["datum"], timezone.localdate().isoformat())

    def test_zoek_klussen_in_leiden(self):
        uitkomst = self.tool(self.access, "zoek_klussen", plaats="Leiden")["structuredContent"]
        self.assertEqual({k["naam"] for k in uitkomst["klussen"]}, {"Tuin Vermeer", "Oude vijver"})
        uitkomst = self.tool(self.access, "zoek_klussen", plaats="Leiden", status="actief")["structuredContent"]
        self.assertEqual([k["naam"] for k in uitkomst["klussen"]], ["Tuin Vermeer"])

    def test_zoek_klussen_fout_soort(self):
        self.assertTrue(self.tool(self.access, "zoek_klussen", soort="snoeien")["isError"])

    def test_klus_dossier(self):
        uitkomst = self.tool(self.access, "klus_dossier", klus_id=self.tuin.pk)["structuredContent"]
        self.assertEqual(uitkomst["uren"]["totaal"], 13.0)
        self.assertEqual(uitkomst["uren"]["per_medewerker"], {"Henk de Vries": 4.0, "Sam Bakker": 9.0})
        self.assertEqual(uitkomst["notities"][0]["tekst"], "Sleutel bij de buren")
        self.assertEqual(uitkomst["email_opdrachtgever"], "vermeer@example.nl")

    def test_klus_dossier_onbekend(self):
        self.assertTrue(self.tool(self.access, "klus_dossier", klus_id=999999)["isError"])

    def test_opdrachtgevers_samengevoegd_op_spelling(self):
        uitkomst = self.tool(self.access, "opdrachtgevers", zoekterm="vermeer")["structuredContent"]
        self.assertEqual(uitkomst["aantal"], 1)
        self.assertEqual(len(uitkomst["opdrachtgevers"][0]["klussen"]), 2)
        self.assertEqual(uitkomst["opdrachtgevers"][0]["uren_totaal"], 13.0)

    def test_waar_was_henk_gisteren(self):
        uitkomst = self.tool(self.access, "uren", medewerker="henk", van="2026-11-09", tot="2026-11-09")["structuredContent"]
        self.assertEqual(uitkomst["totaal_uren"], 7.5)
        self.assertEqual([b["klus"] for b in uitkomst["uurblokken"]], ["Tuin Vermeer", "Parkonderhoud"])
        self.assertEqual(uitkomst["uurblokken"][0]["extra_werk"], "3 palen")

    def test_uren_per_medewerker_over_periode(self):
        uitkomst = self.tool(self.access, "uren", van="2026-11-01", tot="2026-11-30")["structuredContent"]
        self.assertEqual({r["medewerker"]: r["uren"] for r in uitkomst["per_medewerker"]}, {"Henk de Vries": 7.5, "Sam Bakker": 9.0})

    def test_uren_onbekende_medewerker_noemt_wie_er_wel_zijn(self):
        uitkomst = self.tool(self.access, "uren", medewerker="Piet")
        self.assertTrue(uitkomst["isError"])
        self.assertIn("Henk de Vries", uitkomst["content"][0]["text"])

    def test_uren_dubbelzinnige_naam(self):
        Medewerker.objects.create_user("henk2", first_name="Henk", last_name="Jansen")
        uitkomst = self.tool(self.access, "uren", medewerker="Henk")
        self.assertTrue(uitkomst["isError"])
        self.assertIn("Henk Jansen", uitkomst["content"][0]["text"])

    def test_uren_te_lange_periode(self):
        self.assertTrue(self.tool(self.access, "uren", van="2020-01-01", tot="2026-01-01")["isError"])

    def test_uren_kapotte_datum(self):
        self.assertTrue(self.tool(self.access, "uren", van="gisteren")["isError"])

    def test_werkplanning(self):
        uitkomst = self.tool(self.access, "werkplanning", van="2026-11-10", tot="2026-11-16")["structuredContent"]
        per_dag = {d["datum"]: d for d in uitkomst["dagen"]}
        self.assertEqual(per_dag["2026-11-12"]["klussen"][0]["notitie"], "met kraan")
        self.assertEqual(per_dag["2026-11-12"]["klussen"][0]["ingepland"], ["Henk de Vries"])
        self.assertEqual(per_dag["2026-11-13"]["dagnotitie"], "op tijd weg")

    def test_werkplanning_per_medewerker(self):
        uitkomst = self.tool(self.access, "werkplanning", van="2026-11-10", tot="2026-11-16", medewerker="sam")["structuredContent"]
        self.assertFalse(any(d["klussen"] for d in uitkomst["dagen"]))

    def test_aanwezigheid(self):
        uitkomst = self.tool(self.access, "aanwezigheid", van="2026-11-09", tot="2026-11-13", medewerker="Sam")["structuredContent"]
        woensdag = [d for d in uitkomst["medewerkers"][0]["dagen"] if d["datum"] == "2026-11-11"][0]
        self.assertEqual((woensdag["stand"], woensdag["reden"]), ("afwezig", "Ziek"))

    def test_aanwezigheid_hele_ploeg_zonder_verborgen_account(self):
        Medewerker.objects.create_user("admin", rol=Medewerker.Rol.EIGENAAR, verborgen=True)
        uitkomst = self.tool(self.access, "aanwezigheid", van="2026-11-09", tot="2026-11-09")["structuredContent"]
        self.assertNotIn("admin", [m["medewerker"] for m in uitkomst["medewerkers"]])
        self.assertEqual(len(uitkomst["medewerkers"]), 3)

    def test_medewerkers_zonder_contactgegevens(self):
        self.henk.telefoon = "0612345678"
        self.henk.save()
        tekst = self.tool(self.access, "medewerkers")["content"][0]["text"]
        self.assertIn("Henk de Vries", tekst)
        self.assertNotIn("0612345678", tekst)

    def test_zoek_notities(self):
        uitkomst = self.tool(self.access, "zoek_notities", zoekterm="sleutel")["structuredContent"]
        self.assertEqual(uitkomst["notities"][0]["klus"], "Tuin Vermeer")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class BestandTests(Basis):
    @classmethod
    def tearDownClass(cls):
        from django.conf import settings

        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.access, _, _ = self.koppel()
        self.klus = Klus.objects.create(naam="Tuin Vermeer")

    def bijlage(self, naam, inhoud, soort=Bijlage.Soort.DOCUMENT, **velden):
        b = Bijlage(klus=self.klus, soort=soort, originele_naam=naam, toegevoegd_door=self.sam, **velden)
        b.bestand.save(naam, ContentFile(inhoud), save=False)
        b.save()
        return b

    def test_foto_als_afbeelding(self):
        from PIL import Image

        uit = io.BytesIO()
        Image.new("RGB", (3000, 2000), "green").save(uit, "JPEG")
        b = self.bijlage("IMG_0001.jpg", uit.getvalue(), soort=Bijlage.Soort.FOTO, toelichting="Na het bestraten")
        inhoud = self.tool(self.access, "bekijk_bestand", bestand_id=b.pk)["content"]
        self.assertEqual(inhoud[1]["type"], "image")
        with Image.open(io.BytesIO(base64.b64decode(inhoud[1]["data"]))) as plaatje:
            self.assertLessEqual(max(plaatje.size), 1568)

    def test_pdf_als_tekst(self):
        import pymupdf

        pdf = pymupdf.open()
        pagina = pdf.new_page()
        pagina.insert_text((72, 72), "Offerte voor de bestrating van de achtertuin " * 5)
        b = self.bijlage("offerte.pdf", pdf.tobytes())
        inhoud = self.tool(self.access, "bekijk_bestand", bestand_id=b.pk)["content"]
        self.assertIn("bestrating", inhoud[1]["text"])

    def test_xlsx_als_tekst(self):
        from openpyxl import Workbook

        boek = Workbook()
        boek.active.append(["Materiaal", "Aantal"])
        boek.active.append(["Palen", 3])
        uit = io.BytesIO()
        boek.save(uit)
        b = self.bijlage("materiaal.xlsx", uit.getvalue())
        self.assertIn("Palen\t3", self.tool(self.access, "bekijk_bestand", bestand_id=b.pk)["content"][1]["text"])

    def test_docx_als_tekst(self):
        uit = io.BytesIO()
        with zipfile.ZipFile(uit, "w") as archief:
            archief.writestr(
                "word/document.xml",
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
                "<w:p><w:r><w:t>Werkbeschrijving</w:t></w:r></w:p></w:body></w:document>",
            )
        b = self.bijlage("werk.docx", uit.getvalue())
        self.assertIn("Werkbeschrijving", self.tool(self.access, "bekijk_bestand", bestand_id=b.pk)["content"][1]["text"])

    def test_onleesbaar_type(self):
        b = self.bijlage("tekening.dwg", b"\x00\x01")
        self.assertTrue(self.tool(self.access, "bekijk_bestand", bestand_id=b.pk)["isError"])

    def test_zoek_bestanden_ook_afgeschermde_zonder_rechten(self):
        """De eigenaar ziet alles in de app, dus Claude ook. Wie het verder mag
        zien, is een instelling van de app en gaat niet mee."""
        b = self.bijlage("offerte.pdf", b"%PDF")
        b.zichtbaar_voor.add(self.henk)
        uitkomst = self.tool(self.access, "zoek_bestanden", zoekterm="offerte")["structuredContent"]
        self.assertEqual(uitkomst["bestanden"][0]["naam"], "offerte.pdf")
        self.assertNotIn("zichtbaar", json.dumps(uitkomst))

    def test_geen_opslagpad(self):
        b = self.bijlage("offerte.pdf", b"%PDF")
        tekst = json.dumps(self.tool(self.access, "klus_dossier", klus_id=self.klus.pk))
        self.assertNotIn(b.bestand.name, tekst)
        self.assertNotIn("bijlagen/", tekst)


class GeenLekTests(ToolData):
    """Alleen bedrijfsgegevens: niets over code, server, accounts of rechten."""

    VERBODEN = [
        "gebruikersnaam", "username", "wachtwoord", "password", '"rol"', "eigenaar", "verborgen",
        "zichtbaar", "bijlagen/", "thumbnails/", "/srv/", "media", ".py", "traceback", "django",
        "http://", "https://", "telefoon", "noodcontact", "postcode", "woonplaats", "backup",
        "kleur", "_hash", "token", "Exception",
    ]

    def test_geen_enkele_tool_lekt(self):
        self.henk.telefoon = "0612345678"
        self.henk.save()
        admin = Medewerker.objects.create_user("admin", rol=Medewerker.Rol.EIGENAAR, verborgen=True)
        Notitie.objects.create(klus=self.tuin, tekst="Hek dicht", geschreven_door=admin)
        aanroepen = [
            ("vandaag", {}), ("zoek_klussen", {}), ("klus_dossier", {"klus_id": self.tuin.pk}),
            ("opdrachtgevers", {}), ("medewerkers", {"ook_uit_dienst": True}),
            ("uren", {"van": "2026-11-01", "tot": "2026-11-30"}),
            ("werkplanning", {"van": "2026-11-10", "tot": "2026-11-16"}),
            ("aanwezigheid", {"van": "2026-11-09", "tot": "2026-11-13"}),
            ("zoek_notities", {}), ("zoek_bestanden", {}),
            ("uren", {"medewerker": "niemand"}), ("klus_dossier", {"klus_id": "x"}),
        ]
        for naam, argumenten in aanroepen:
            tekst = json.dumps(self.tool(self.access, naam, **argumenten), ensure_ascii=False).lower()
            for woord in self.VERBODEN:
                self.assertNotIn(woord.lower(), tekst, f"{naam} geeft '{woord}' mee")
        self.assertNotIn("0612345678", tekst)
        notities = self.tool(self.access, "zoek_notities", zoekterm="hek")["structuredContent"]["notities"]
        self.assertEqual(notities[0]["door"], "HandigerAI")

    def test_onverwachte_fout_geeft_geen_details(self):
        from unittest.mock import patch

        with patch("koppeling.gereedschap.Klus.objects.all", side_effect=RuntimeError("geheim /srv/pad")):
            uitkomst = self.tool(self.access, "zoek_klussen")
        self.assertTrue(uitkomst["isError"])
        self.assertNotIn("geheim", json.dumps(uitkomst))

    def test_tool_beschrijvingen_noemen_geen_techniek(self):
        tekst = json.dumps(self.mcp(self.access, "tools/list").json()).lower()
        for woord in ("dropbox", "django", "database", "server", "http", "model"):
            self.assertNotIn(woord, tekst)
