from django.contrib.auth.decorators import login_required
from django.shortcuts import render

# Het beginscherm van de app: pictogrammen naar de onderdelen. Wat je ziet
# hangt af van je rol. De onderdelen zelf worden hierna gebouwd; de tegels
# zonder url zijn nog niet af.
TEGELS = [
    {"titel": "Uren schrijven", "teken": "⏱", "url": None, "rollen": ["medewerker", "eigenaar"]},
    {"titel": "Klussen", "teken": "◰", "url": None, "rollen": ["medewerker", "eigenaar"]},
    {"titel": "Mijn overzicht", "teken": "≡", "url": None, "rollen": ["medewerker"]},
    {"titel": "Planbord", "teken": "⊞", "url": None, "rollen": ["eigenaar"]},
    {"titel": "Overzichten", "teken": "≡", "url": None, "rollen": ["eigenaar"]},
    {"titel": "Aanwezigheid", "teken": "●", "url": None, "rollen": ["eigenaar"]},
    {"titel": "Foto's", "teken": "▣", "url": None, "rollen": ["medewerker", "eigenaar"]},
    {"titel": "Loonstrook", "teken": "€", "url": "https://www.loondossier.nl", "rollen": ["medewerker", "eigenaar"]},
    {"titel": "Beheer", "teken": "⚙", "url": "/beheer/", "rollen": ["eigenaar"]},
]


@login_required
def start(request):
    rol = request.user.rol
    tegels = [tegel for tegel in TEGELS if rol in tegel["rollen"]]
    return render(request, "start.html", {"tegels": tegels})
