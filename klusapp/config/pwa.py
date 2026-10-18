"""De klusapp als installeerbare app (PWA): manifest, service worker en de
offline-pagina. Het recept en de keuzes erachter staan in development/PWA.md.

Alle drie hangen ze in de root van de site en niet onder /static/: een
service worker mag alleen de paden onder zijn eigen map aansturen, en in
productie hasht WhiteNoise de bestandsnamen onder /static/. Geen van drieën
vraagt om inloggen — de telefoon haalt ze op voordat iemand ingelogd is.
"""
import hashlib

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
            "name": "Klusapp · De Groene M",
            "short_name": "Klusapp",
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
        {"versie": versie, "bestanden": bestanden, "offline_url": offline_url},
    )
    antwoord = HttpResponse(js, content_type="text/javascript; charset=utf-8")
    antwoord["Service-Worker-Allowed"] = "/"
    return antwoord


def offline(request):
    return render(request, "offline.html")
