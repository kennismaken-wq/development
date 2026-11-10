"""OAuth 2.1 voor de koppeling met Claude: precies genoeg, en niet meer.

Wat Claude (claude.ai, de desktop-app, Claude Code) verwacht als je een eigen
connector toevoegt:

1. Hij vraagt /mcp zonder sleutel en krijgt een 401 met een verwijzing naar
   /.well-known/oauth-protected-resource.
2. Daar en in /.well-known/oauth-authorization-server leest hij waar hij zich
   aanmeldt, waar de eigenaar toestemming geeft en waar hij tokens haalt.
3. Hij meldt zich aan (/oauth/registreren/), stuurt de eigenaar naar
   /oauth/toestaan/, en wisselt de code die daaruit komt in bij /oauth/token/.

Alleen het "authorization code"-pad met PKCE (S256), plus vernieuwen met een
refresh token. Geen client secrets: Claude is een publieke client, en PKCE
maakt een onderschepte code waardeloos.

Bewust geen bibliotheek als django-oauth-toolkit: die kent geen dynamische
registratie, en de stukken die we nodig hebben zijn klein genoeg om hier
helemaal te lezen.
"""

import base64
import hashlib
import json
import re
import secrets
from datetime import timedelta
from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from medewerkers.rem import ip_van

from .models import CODE_GELDIG, HERGEBRUIK_MARGE, Autorisatiecode, Client, Koppeling, vingerafdruk

SCOPE = "lezen"

# PKCE: base64url zonder opvulling, 43-128 tekens (RFC 7636). Ook de
# verifier; een "é" liet compare_digest eerder een 500 geven.
PKCE_VORM = re.compile(r"^[A-Za-z0-9._~-]{43,128}$")
# Aanmelden kan anoniem. Zonder grenzen schreef één verzoek 20 MB in de
# database, en 500 verzoeken 500 rijen (stresstest 10-11-2026).
MAX_AANMELDING = 8 * 1024
MAX_URIS = 5
MAX_AANMELDINGEN_PER_IP = 10      # per uur
MAX_ONGEBRUIKT = 200              # aanmeldingen zonder koppeling, in totaal


def basis_url(request):
    """https://develop.handigerai.nl — achter nginx klopt dit dankzij
    SECURE_PROXY_SSL_HEADER en ALLOWED_HOSTS."""
    return f"{request.scheme}://{request.get_host()}"


def resource_url(request):
    return basis_url(request) + "/mcp"


def _json(gegevens, status=200):
    antwoord = JsonResponse(gegevens, status=status)
    antwoord["Cache-Control"] = "no-store"
    # Claude in de browser (bv. de MCP-inspector) leest deze adressen ook
    # rechtstreeks; er staat niets geheims in.
    antwoord["Access-Control-Allow-Origin"] = "*"
    return antwoord


def _fout(code, uitleg="", status=400):
    gegevens = {"error": code}
    if uitleg:
        gegevens["error_description"] = uitleg
    return _json(gegevens, status)


# ── metadata ──────────────────────────────────────────────────────────────


@require_GET
def protected_resource(request):
    """RFC 9728: waar de sleutels voor /mcp vandaan komen."""
    return _json(
        {
            "resource": resource_url(request),
            "authorization_servers": [basis_url(request)],
            "scopes_supported": [SCOPE],
            "bearer_methods_supported": ["header"],
            "resource_name": "Klusapp De Groene M",
        }
    )


@require_GET
def authorization_server(request):
    """RFC 8414: de adressen van de inlogstappen."""
    basis = basis_url(request)
    return _json(
        {
            "issuer": basis,
            "authorization_endpoint": basis + "/oauth/toestaan/",
            "token_endpoint": basis + "/oauth/token/",
            "registration_endpoint": basis + "/oauth/registreren/",
            "scopes_supported": [SCOPE],
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"],
        }
    )


# ── registreren ───────────────────────────────────────────────────────────


# Claude Code en de desktop-app vangen de code op met een tijdelijke server op
# de eigen computer: http://localhost:<poort>/<pad>. Alleen gewone tekens, zodat
# er geen ruimte is voor trucs met @, backslashes of procenttekens.
LOKAAL = re.compile(r"^http://(localhost|127\.0\.0\.1)(:[0-9]{1,5})?(/[A-Za-z0-9/_.-]*)?$")


def redirect_toegestaan(uri):
    """Alleen terug naar Claude zelf: precies een van de terugadressen uit
    KLUSAPP_CLAUDE_REDIRECT_URIS (claude.ai en claude.com), of localhost voor
    Claude Code. Exact vergelijken, niet op host: zo kan een nagemaakte
    "Claude" de eigenaar niet naar een eigen site laten doorsturen met een
    geldige code in de hand."""
    return uri in settings.CLAUDE_REDIRECT_URIS or bool(LOKAAL.match(uri))


@csrf_exempt
@require_POST
def registreren(request):
    """RFC 7591. Aanmelden geeft geen toegang; het toestemmingsscherm wel."""
    try:
        lengte = int(request.META.get("CONTENT_LENGTH") or 0)
    except ValueError:
        lengte = 0
    if lengte > MAX_AANMELDING:
        return _fout("invalid_client_metadata", "Te groot.", status=413)
    ip = ip_van(request)
    nu = timezone.now()
    if (ip and Client.objects.filter(ip=ip, aangemaakt_op__gte=nu - timedelta(hours=1)).count() >= MAX_AANMELDINGEN_PER_IP) or (
        Client.objects.filter(koppelingen__isnull=True).count() >= MAX_ONGEBRUIKT
    ):
        return _fout("temporarily_unavailable", "Te veel aanmeldingen; probeer het later opnieuw.", status=429)
    try:
        gegevens = json.loads(request.body[: MAX_AANMELDING + 1] or b"{}")
    except (ValueError, UnicodeDecodeError, RecursionError):
        return _fout("invalid_client_metadata", "Geen geldige JSON.")
    if not isinstance(gegevens, dict):
        return _fout("invalid_client_metadata", "Geen geldige JSON.")
    uris = gegevens.get("redirect_uris")
    if not isinstance(uris, list) or not uris or not all(isinstance(u, str) for u in uris):
        return _fout("invalid_redirect_uri", "redirect_uris ontbreekt.")
    if len(uris) > MAX_URIS or not all(len(u) <= 500 and redirect_toegestaan(u) for u in uris):
        return _fout("invalid_redirect_uri", "Deze koppeling werkt alleen met Claude.")

    # Een aanmelding zonder dat er ooit iemand toestemming gaf, is na een dag
    # niets meer waard. Opruimen hier houdt de tabel klein zonder cronjob.
    Client.objects.filter(aangemaakt_op__lt=nu - timedelta(days=1), koppelingen__isnull=True).delete()

    naam = gegevens.get("client_name")
    client = Client.objects.create(naam=naam[:120] if isinstance(naam, str) else "", redirect_uris=uris, ip=ip)
    return _json(
        {
            "client_id": client.client_id,
            "client_id_issued_at": int(client.aangemaakt_op.timestamp()),
            "client_name": client.naam,
            "redirect_uris": uris,
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
            "scope": SCOPE,
        },
        status=201,
    )


# ── toestaan ──────────────────────────────────────────────────────────────


def _terug(redirect_uri, **parameters):
    scheiding = "&" if "?" in redirect_uri else "?"
    schoon = {k: v for k, v in parameters.items() if v}
    return HttpResponseRedirect(redirect_uri + scheiding + urlencode(schoon))


@login_required
def toestaan(request):
    """Het scherm "Claude wil meelezen in de klusapp".

    Klopt de aanvraag zelf niet (onbekende client, vreemd terugadres), dan
    sturen we níet terug maar tonen we een foutmelding: anders wordt dit een
    open doorstuurpunt. Klopt hij wel maar mist er iets, dan gaat de fout
    netjes terug naar Claude, zoals OAuth dat voorschrijft."""
    p = request.POST if request.method == "POST" else request.GET
    client = Client.objects.filter(client_id=p.get("client_id", "")).first()
    redirect_uri = p.get("redirect_uri", "")
    if client is None or redirect_uri not in client.redirect_uris:
        return render(request, "koppeling/toestaan.html", {"ongeldig": True}, status=400)

    state = p.get("state", "")
    if p.get("response_type") != "code":
        return _terug(redirect_uri, error="unsupported_response_type", state=state)
    challenge = p.get("code_challenge", "")
    if p.get("code_challenge_method") != "S256" or not PKCE_VORM.match(challenge):
        return _terug(redirect_uri, error="invalid_request", error_description="PKCE (S256) is verplicht.", state=state)

    if not request.user.is_eigenaar:
        # Een medewerker ziet een uitleg in plaats van een knop; een
        # zelfgemaakte POST levert hetzelfde op.
        return render(request, "koppeling/toestaan.html", {"geen_eigenaar": True}, status=403)

    if request.method == "POST":
        if request.POST.get("actie") != "toestaan":
            return _terug(redirect_uri, error="access_denied", state=state)
        code = secrets.token_urlsafe(32)
        Autorisatiecode.objects.filter(verloopt_op__lt=timezone.now()).delete()
        Autorisatiecode.objects.create(
            code_hash=vingerafdruk(code),
            client=client,
            medewerker=request.user,
            redirect_uri=redirect_uri,
            code_challenge=challenge,
            verloopt_op=timezone.now() + CODE_GELDIG,
        )
        return _terug(redirect_uri, code=code, state=state)

    velden = ["client_id", "redirect_uri", "response_type", "code_challenge", "code_challenge_method", "state", "scope", "resource"]
    return render(
        request,
        "koppeling/toestaan.html",
        {
            "client": client,
            "terug_naar": urlsplit(redirect_uri).hostname,
            "verborgen": [(veld, p.get(veld)) for veld in velden if p.get(veld)],
        },
    )


# ── token ─────────────────────────────────────────────────────────────────


def _pkce_klopt(verifier, challenge):
    if not PKCE_VORM.match(verifier):
        return False
    berekend = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return secrets.compare_digest(berekend, challenge)


def _tokenantwoord(koppeling, access, refresh):
    return _json(
        {
            "access_token": access,
            "token_type": "Bearer",
            "expires_in": int((koppeling.access_verloopt_op - timezone.now()).total_seconds()),
            "refresh_token": refresh,
            "scope": SCOPE,
        }
    )


@csrf_exempt
@require_POST
def token(request):
    soort = request.POST.get("grant_type")
    client = Client.objects.filter(client_id=request.POST.get("client_id", "")).first()
    if client is None:
        return _fout("invalid_client", status=401)

    if soort == "authorization_code":
        with transaction.atomic():
            # Eenmalig: ophalen en weggooien in één stap, ook als er iets
            # niet klopt. Een tweede poging met dezelfde code faalt altijd.
            code = (
                Autorisatiecode.objects.select_for_update()
                .filter(code_hash=vingerafdruk(request.POST.get("code", "")), client=client)
                .select_related("medewerker")
                .first()
            )
            if code is None:
                return _fout("invalid_grant")
            code.delete()
        if (
            code.verlopen()
            or code.redirect_uri != request.POST.get("redirect_uri", "")
            or not _pkce_klopt(request.POST.get("code_verifier", ""), code.code_challenge)
            or not code.medewerker.is_eigenaar
            or not code.medewerker.is_active
        ):
            return _fout("invalid_grant")
        koppeling = Koppeling(medewerker=code.medewerker, client=client)
        access, refresh = koppeling.nieuwe_tokens()
        koppeling.save()
        return _tokenantwoord(koppeling, access, refresh)

    if soort == "refresh_token":
        with transaction.atomic():
            sleutel = vingerafdruk(request.POST.get("refresh_token", ""))
            koppeling = (
                Koppeling.objects.actief()
                .select_for_update()
                .filter(refresh_hash=sleutel, client=client)
                .select_related("medewerker")
                .first()
            )
            if koppeling is None:
                _hergebruik_afhandelen(sleutel, client)
                return _fout("invalid_grant")
            if not koppeling.mag_lezen() or koppeling.refresh_verloopt_op <= timezone.now():
                return _fout("invalid_grant")
            access, refresh = koppeling.nieuwe_tokens()
            koppeling.save(
                update_fields=["access_hash", "refresh_hash", "access_verloopt_op", "refresh_verloopt_op", "vorige_refresh_hash", "geroteerd_op"]
            )
        return _tokenantwoord(koppeling, access, refresh)

    return _fout("unsupported_grant_type")


def _hergebruik_afhandelen(sleutel, client):
    """Een refresh token die al eens is ingewisseld. Vlak na het wisselen is
    dat een dubbel verzoek; later betekent het dat iemand anders hem heeft.
    Dan gaat de hele koppeling dicht en moet de eigenaar opnieuw koppelen."""
    oud = Koppeling.objects.actief().filter(vorige_refresh_hash=sleutel, client=client).first()
    if oud and oud.geroteerd_op and timezone.now() - oud.geroteerd_op > HERGEBRUIK_MARGE:
        oud.ingetrokken_op = timezone.now()
        oud.save(update_fields=["ingetrokken_op"])


def koppeling_bij_token(request):
    """De koppeling achter "Authorization: Bearer …", of None."""
    kop = request.headers.get("Authorization", "")
    soort, _, token = kop.partition(" ")
    if soort.lower() != "bearer" or not token:
        return None
    koppeling = (
        Koppeling.objects.actief()
        .filter(access_hash=vingerafdruk(token.strip()), access_verloopt_op__gt=timezone.now())
        .select_related("medewerker", "client")
        .first()
    )
    if koppeling is None or not koppeling.mag_lezen():
        return None
    return koppeling
