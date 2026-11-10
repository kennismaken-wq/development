"""Het MCP-eindpunt op /mcp: JSON-RPC over HTTP ("Streamable HTTP").

Stateloos: elk verzoek is een POST met één bericht (of een lijst), en het
antwoord is gewoon JSON. Geen sessies en geen server-sent events — er valt
niets te streamen, elke vraag is een databasequery. Dat mag volgens de
specificatie, en het past bij gunicorn met synchrone workers.

Bewust geen `mcp`-pakket: dat is gebouwd op Starlette/ASGI en zou naast
Django een tweede webserver vragen. De drie methoden die er toe doen
(initialize, tools/list, tools/call) zijn hieronder te lezen.
"""

import json
import logging

from django.db import connection, transaction
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from . import gereedschap
from .oauth import basis_url, koppeling_bij_token

log = logging.getLogger(__name__)

# Ongeveer 25.000 tokens: wat Claude nog goed in één keer kan lezen.
MAX_ANTWOORD = 100_000

MAX_VERZOEK = 64 * 1024
MAX_LIJST_BERICHTEN = 10


def _geen_nan(waarde):
    raise ValueError(f"{waarde} is geen geldige JSON")


PROTOCOLVERSIES = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"]

INSTRUCTIES = (
    "Je leest mee in de klusapp van hoveniersbedrijf De Groene M: klussen, opdrachtgevers, "
    "geschreven uren, werkplanning, aanwezigheid, notities, foto's en documenten. Je kunt "
    "alleen lezen, niets wijzigen. Roep eerst 'vandaag' aan als de vraag een relatieve datum "
    "noemt (gisteren, vorige week). Medewerkers zoek je op voornaam. Antwoord in het Nederlands."
)


def _antwoord(bericht_id, resultaat):
    return {"jsonrpc": "2.0", "id": bericht_id, "result": resultaat}


def _fout(bericht_id, code, tekst):
    return {"jsonrpc": "2.0", "id": bericht_id, "error": {"code": code, "message": tekst}}


def _niet_ingelogd(request):
    antwoord = JsonResponse(_fout(None, -32001, "Niet ingelogd. Koppel Claude opnieuw."), status=401)
    antwoord["WWW-Authenticate"] = (
        f'Bearer resource_metadata="{basis_url(request)}/.well-known/oauth-protected-resource", scope="lezen"'
    )
    return antwoord


_TYPEN = {
    "string": (lambda w: isinstance(w, str), "tekst"),
    # bool is in Python ook een int; True als klus_id is geen klus.
    "integer": (lambda w: isinstance(w, int) and not isinstance(w, bool), "een geheel getal"),
    "boolean": (lambda w: isinstance(w, bool), "true of false"),
}


def _controleer(schema, argumenten):
    """De argumenten tegen het schema van de tool, vóór er iets draait. Zo
    krijgt een tool alleen de vormen binnen waar hij op rekent, en Claude
    een zin die zegt wat er mis is in plaats van "er ging iets mis"."""
    velden = schema.get("properties", {})
    for naam in schema.get("required", []):
        if argumenten.get(naam) is None:
            return f"'{naam}' is verplicht."
    for naam, waarde in argumenten.items():
        if naam not in velden:
            return f"Onbekend argument '{naam}'. Mogelijk: {', '.join(velden) or 'geen'}."
        if waarde is None:
            continue
        klopt, omschrijving = _TYPEN[velden[naam]["type"]]
        if not klopt(waarde):
            return f"'{naam}' moet {omschrijving} zijn."
        if "enum" in velden[naam] and waarde not in velden[naam]["enum"]:
            return f"'{naam}' moet een van deze zijn: {', '.join(velden[naam]['enum'])}."
        if isinstance(waarde, str) and len(waarde) > 200:
            return f"'{naam}' is te lang."
    return None


def _momentopname():
    """Eén vraag van Claude ziet de database zoals hij was op het moment dat
    de vraag binnenkwam, ook als er intussen uren bij komen: het totaal en
    de lijst eronder kloppen dan altijd met elkaar. READ ONLY laat Postgres
    zelf elke schrijfpoging weigeren — een tweede slot naast "geen enkele
    tool schrijft". Lezen houdt op Postgres geen sloten vast, dus de app
    merkt hier niets van. SQLite (lokaal, tests) kent dit niet en heeft het
    ook niet nodig: daar is maar één schrijver tegelijk."""
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")


def _tool_aanroepen(params):
    naam = params.get("name")
    tool = gereedschap.PER_NAAM.get(naam) if isinstance(naam, str) else None
    if tool is None:
        return None
    argumenten = params.get("arguments") or {}
    if not isinstance(argumenten, dict):
        return {"content": [{"type": "text", "text": "De argumenten moeten een object zijn."}], "isError": True}
    probleem = _controleer(tool["inputSchema"], argumenten)
    if probleem:
        return {"content": [{"type": "text", "text": probleem}], "isError": True}
    try:
        with transaction.atomic():
            _momentopname()
            uitkomst = tool["functie"](argumenten)
    except gereedschap.Fout as fout:
        return {"content": [{"type": "text", "text": str(fout)}], "isError": True}
    except Exception:
        log.exception("Claude-koppeling: %s faalde", naam)
        return {"content": [{"type": "text", "text": "Er ging iets mis. Probeer het later opnieuw."}], "isError": True}
    if isinstance(uitkomst, list):
        return {"content": uitkomst}
    # Compact en één keer: geen inspringing en geen tweede kopie als
    # structuredContent. Een jaar uren was zo 367 KB, de helft dubbel.
    tekst = json.dumps(uitkomst, ensure_ascii=False, separators=(",", ":"))
    if len(tekst) > MAX_ANTWOORD:
        # Liever een duidelijke vraag om in te perken dan een antwoord dat
        # Claude halverwege afkapt en waar hij dan toch op gaat rekenen.
        return {
            "content": [{"type": "text", "text": "Dit zijn te veel gegevens voor één antwoord. Vraag een kortere periode, of filter op een medewerker of klus."}],
            "isError": True,
        }
    return {"content": [{"type": "text", "text": tekst}]}


def _verwerk(bericht):
    """Eén JSON-RPC-bericht; None voor een notificatie (geen antwoord)."""
    if not isinstance(bericht, dict) or bericht.get("jsonrpc") != "2.0" or not isinstance(bericht.get("method"), str):
        return _fout(bericht.get("id") if isinstance(bericht, dict) else None, -32600, "Ongeldig verzoek.")
    if "id" not in bericht:
        return None
    bericht_id = bericht["id"]
    if not isinstance(bericht_id, (str, int)) or isinstance(bericht_id, bool):
        return _fout(None, -32600, "Ongeldig id.")
    methode = bericht["method"]
    params = bericht.get("params") or {}
    if not isinstance(params, dict):
        return _fout(bericht_id, -32602, "params moet een object zijn.")

    if methode == "initialize":
        gevraagd = params.get("protocolVersion")
        return _antwoord(
            bericht_id,
            {
                "protocolVersion": gevraagd if gevraagd in PROTOCOLVERSIES else PROTOCOLVERSIES[0],
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "klusapp-de-groene-m", "title": "Klusapp De Groene M", "version": "1.0"},
                "instructions": INSTRUCTIES,
            },
        )
    if methode == "ping":
        return _antwoord(bericht_id, {})
    if methode == "tools/list":
        return _antwoord(
            bericht_id,
            {"tools": [{k: v for k, v in tool.items() if k != "functie"} for tool in gereedschap.TOOLS]},
        )
    if methode == "tools/call":
        resultaat = _tool_aanroepen(params)
        if resultaat is None:
            return _fout(bericht_id, -32602, f"Onbekende tool: {params.get('name')!r}.")
        return _antwoord(bericht_id, resultaat)
    if methode in ("resources/list", "prompts/list"):
        return _antwoord(bericht_id, {methode.split("/")[0]: []})
    return _fout(bericht_id, -32601, f"Onbekende methode: {methode}.")


@csrf_exempt
def eindpunt(request):
    if request.method != "POST":
        # Geen SSE-stroom en geen sessies om af te sluiten.
        antwoord = HttpResponse(status=405)
        antwoord["Allow"] = "POST"
        return antwoord

    koppeling = koppeling_bij_token(request)
    if koppeling is None:
        return _niet_ingelogd(request)
    # Op het intrekscherm zie je zo of een koppeling nog gebruikt wordt. Eens
    # per minuut is genoeg; elke vraag van Claude een schrijfactie is zonde.
    nu = timezone.now()
    if koppeling.laatst_gebruikt_op is None or (nu - koppeling.laatst_gebruikt_op).total_seconds() > 60:
        koppeling.laatst_gebruikt_op = nu
        koppeling.save(update_fields=["laatst_gebruikt_op"])

    # Een vraag van Claude is een paar honderd bytes. Groter is geen vraag.
    try:
        lengte = int(request.META.get("CONTENT_LENGTH") or 0)
    except ValueError:
        lengte = 0
    if lengte > MAX_VERZOEK:
        return JsonResponse(_fout(None, -32600, "Verzoek te groot."), status=413)
    try:
        bericht = json.loads(request.body[: MAX_VERZOEK + 1], parse_constant=_geen_nan)
    except (ValueError, UnicodeDecodeError, RecursionError):
        return JsonResponse(_fout(None, -32700, "Geen geldige JSON."), status=400)

    try:
        if isinstance(bericht, list):
            if not bericht:
                return JsonResponse(_fout(None, -32600, "Lege lijst."), status=400)
            # Nieuwere protocolversies kennen geen lijsten meer; oudere
            # sturen er hooguit een paar. Zonder plafond hield één verzoek
            # met 5000 zware vragen een worker minutenlang bezig.
            if len(bericht) > MAX_LIJST_BERICHTEN:
                return JsonResponse(_fout(None, -32600, "Te veel berichten in één verzoek."), status=400)
            antwoorden = [a for a in map(_verwerk, bericht) if a is not None]
            return JsonResponse(antwoorden, safe=False) if antwoorden else HttpResponse(status=202)
        antwoord = _verwerk(bericht)
    except Exception:
        # Nooit een foutpagina of traceback richting Claude: daar staan
        # bestandsnamen en regels code in.
        log.exception("Claude-koppeling: verzoek faalde")
        return JsonResponse(_fout(None, -32603, "Er ging iets mis. Probeer het later opnieuw."), status=500)
    if antwoord is None:
        return HttpResponse(status=202)
    return JsonResponse(antwoord, json_dumps_params={"ensure_ascii": False})
