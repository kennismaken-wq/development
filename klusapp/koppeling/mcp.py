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

from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from . import gereedschap
from .oauth import basis_url, koppeling_bij_token

log = logging.getLogger(__name__)

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


def _tool_aanroepen(params):
    naam = params.get("name")
    tool = gereedschap.PER_NAAM.get(naam)
    if tool is None:
        return None
    argumenten = params.get("arguments") or {}
    if not isinstance(argumenten, dict):
        return {"content": [{"type": "text", "text": "De argumenten moeten een object zijn."}], "isError": True}
    try:
        uitkomst = tool["functie"](argumenten)
    except gereedschap.Fout as fout:
        return {"content": [{"type": "text", "text": str(fout)}], "isError": True}
    except Exception:
        log.exception("Claude-koppeling: %s faalde", naam)
        return {"content": [{"type": "text", "text": "Er ging iets mis in de klusapp. Probeer het later opnieuw."}], "isError": True}
    if isinstance(uitkomst, list):
        return {"content": uitkomst}
    return {
        "content": [{"type": "text", "text": json.dumps(uitkomst, ensure_ascii=False, indent=1)}],
        "structuredContent": uitkomst,
    }


def _verwerk(bericht):
    """Eén JSON-RPC-bericht; None voor een notificatie (geen antwoord)."""
    if not isinstance(bericht, dict) or bericht.get("jsonrpc") != "2.0" or not isinstance(bericht.get("method"), str):
        return _fout(bericht.get("id") if isinstance(bericht, dict) else None, -32600, "Ongeldig verzoek.")
    if "id" not in bericht:
        return None
    bericht_id = bericht["id"]
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

    try:
        bericht = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse(_fout(None, -32700, "Geen geldige JSON."), status=400)

    if isinstance(bericht, list):
        if not bericht:
            return JsonResponse(_fout(None, -32600, "Lege lijst."), status=400)
        antwoorden = [a for a in map(_verwerk, bericht) if a is not None]
        return JsonResponse(antwoorden, safe=False) if antwoorden else HttpResponse(status=202)

    antwoord = _verwerk(bericht)
    if antwoord is None:
        return HttpResponse(status=202)
    return JsonResponse(antwoord, json_dumps_params={"ensure_ascii": False})
