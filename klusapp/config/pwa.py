"""De klusapp als installeerbare app (PWA): manifest, service worker en de
offline-pagina, plus het beginschermicoon in de root. Het recept en de keuzes erachter staan in development/PWA.md.

Alle drie hangen ze in de root van de site en niet onder /static/: een
service worker mag alleen de paden onder zijn eigen map aansturen, en in
productie hasht WhiteNoise de bestandsnamen onder /static/. Geen van drieën
vraagt om inloggen — de telefoon haalt ze op voordat iemand ingelogd is.
"""
import hashlib

import segno

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.cache import never_cache

KLEUR = "#1D1D1B"  # zelfde tegel als icoon-180.png en theme-color in basis.html

# Wat de service worker meteen bij het installeren in de cache zet: genoeg
# om de offline-pagina te tonen, plus de scripts die elk scherm laadt.
# Nooit HTML met gegevens erin, nooit /media/ — zie templates/sw.js.
VOORAF_IN_CACHE = [
    "css/app.css",
    "js/beweging.js",
    "js/klus-overgang.js",
    "js/eenmaal-versturen.js",
    "js/app-installeren.js",
    "img/logo-de-groene-m-licht.png",
    "img/icoon-192.png",
]


def manifest(request):
    return JsonResponse(
        {
            "id": "/",
            "name": "De Groene M",
            "short_name": "De Groene M",
            "description": "Uren en klussen van De Groene M",
            "lang": "nl",
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "background_color": KLEUR,
            "theme_color": KLEUR,
            "icons": [
                {"src": static("img/icoon-192.png"), "sizes": "192x192", "type": "image/png"},
                {"src": static("img/icoon-512.png"), "sizes": "512x512", "type": "image/png"},
                {
                    "src": static("img/icoon-maskable-512.png"),
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "maskable",
                },
            ],
        },
        content_type="application/manifest+json",
        json_dumps_params={"ensure_ascii": False},
    )


@never_cache
def service_worker(request):
    bestanden = [static(pad) for pad in VOORAF_IN_CACHE]
    offline_url = reverse("offline")
    # De versie volgt uit de gehashte bestandsnamen: verandert app.css, dan
    # verandert dit bestand, en dan haalt de telefoon zelf de nieuwe worker
    # op en ruimt hij de oude cache op. Niemand hoeft er een nummer bij te
    # houden.
    versie = hashlib.sha1("\n".join([offline_url, *bestanden]).encode()).hexdigest()[:12]
    js = render_to_string(
        "sw.js",
        {
            "versie": versie,
            "bestanden": bestanden,
            "offline_url": offline_url,
            "icoon": static("img/icoon-192.png"),  # bij pushmeldingen
        },
    )
    antwoord = HttpResponse(js, content_type="text/javascript; charset=utf-8")
    antwoord["Service-Worker-Allowed"] = "/"
    return antwoord


def offline(request):
    return render(request, "offline.html")


def apple_touch_icon(request):
    # iOS zoekt het beginschermicoon niet altijd via de <link> in basis.html:
    # soms vraagt hij blind /apple-touch-icon.png (of -precomposed.png) in de
    # root op. Gaf dat een 404, dan maakte hij er zelf een screenshot of een
    # letter van. Daarom hier hetzelfde plaatje, rechtstreeks uit static/.
    pad = settings.BASE_DIR / "static" / "img" / "icoon-180.png"
    antwoord = HttpResponse(pad.read_bytes(), content_type="image/png")
    antwoord["Cache-Control"] = "public, max-age=86400"
    return antwoord


# ── De installatielink ──────────────────────────────────────────────────
# /installeren/ is de link die je rondstuurt (of als QR-code ophangt). Hij
# vraagt niet om inloggen en kijkt zelf wat voor toestel er voor hem zit:
# Android krijgt de installeerknop van Chrome, de iPhone de stappen via het
# Deel-menu, een computer de QR-code om met de telefoon te scannen. Vanzelf
# op het beginscherm zetten kan geen enkele website.
#
# Tot 19-10-2026 kreeg de iPhone hier een installatieprofiel (.mobileconfig)
# om te downloaden. Weggehaald: downloaden en dan via Instellingen een "niet
# geverifieerd" profiel installeren voelde niet goed. Wie de pagina zelf op
# het beginscherm zet, komt toch op de startpagina uit: het manifest heeft
# start_url "/", en static/js/installatiepagina.js stuurt de app door als hij
# toch op /installeren/ opent.


def installeren(request):
    link = request.build_absolute_uri(reverse("installeren"))
    qr = segno.make(link, error="m").svg_inline(scale=5, border=2, dark=KLEUR, light="#ffffff")
    return render(request, "installeren.html", {"qr": qr, "link": link})
