from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse

# Het beginscherm van de app: pictogrammen naar de onderdelen. Wat je ziet
# hangt af van je rol. De onderdelen zelf worden hierna gebouwd; de tegels
# zonder url zijn nog niet af.
TEGELS = [
    {"titel": "Uren schrijven", "teken": "⏱", "url_naam": "mijn_uren", "rollen": ["medewerker", "eigenaar"]},
    {"titel": "Klussen", "teken": "◰", "url": None, "rollen": ["medewerker", "eigenaar"]},
    {"titel": "Mijn overzicht", "teken": "≡", "url": None, "rollen": ["medewerker"]},
    {"titel": "Planbord", "teken": "⊞", "url": None, "rollen": ["eigenaar"]},
    {"titel": "Overzichten", "teken": "≡", "url": None, "rollen": ["eigenaar"]},
    {"titel": "Aanwezigheid", "teken": "●", "url": None, "rollen": ["eigenaar"]},
    {"titel": "Foto's", "teken": "▣", "url": None, "rollen": ["medewerker", "eigenaar"]},
    {"titel": "Loonstrook", "teken": "€", "url": "https://mijn.loondossier.nl/Aanmelden", "rollen": ["medewerker", "eigenaar"]},
    {"titel": "Beheer", "teken": "⚙", "url": "/beheer/", "rollen": ["eigenaar"]},
]


@login_required
def start(request):
    rol = request.user.rol
    tegels = []
    for tegel in TEGELS:
        if rol not in tegel["rollen"]:
            continue
        tegel = dict(tegel)
        if "url_naam" in tegel:
            tegel["url"] = reverse(tegel["url_naam"])
        # het loonstrookportaal is een andere site; die opent in een eigen
        # tabblad zodat je je uren niet kwijtraakt
        tegel["extern"] = str(tegel.get("url") or "").startswith("http")
        tegels.append(tegel)
    return render(request, "start.html", {"tegels": tegels, "vandaag": date.today()})
