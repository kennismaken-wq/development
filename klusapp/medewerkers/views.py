from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse

# Loondossier heeft twee ingangen. Op Android staat in hun assetlinks.json
# dat de app elk adres van mijn.loondossier.nl mag afvangen, dus daar opent
# de app vanzelf als hij geinstalleerd is. Op een iPhone geldt dat maar voor
# een pad: /open-app/. Wie dat pad opent zonder de app te hebben, komt op een
# foutpagina, en of de app er staat kan iOS ons niet vertellen. Daarom vragen
# we het daar een keer en onthouden we het antwoord op het toestel zelf.
LOONDOSSIER_WEB = "https://mijn.loondossier.nl/Aanmelden"
LOONDOSSIER_APP = "https://mijn.loondossier.nl/open-app/"

# Het beginscherm van de app: pictogrammen naar de onderdelen. Wat je ziet
# hangt af van je rol.
#
# Elke tegel heeft zijn definitieve url_naam, ook als het scherm nog niet
# bestaat — die namen staan geregistreerd in config/urls.py. Een tegel met
# "in_aanbouw" wordt gedimd en niet-klikbaar getoond. Is jouw scherm af, haal
# dan alléén die vlag hier weg en verplaats de route uit config/urls.py naar je
# eigen urls.py. Zo hoeft niemand anders deze lijst aan te raken.
TEGELS = [
    {"titel": "Uren schrijven", "teken": "⏱", "url_naam": "mijn_uren", "rollen": ["medewerker", "eigenaar"]},
    {"titel": "Klussen", "teken": "◰", "url_naam": "klussen", "rollen": ["medewerker", "eigenaar"]},
    {"titel": "Mijn overzicht", "teken": "≡", "url_naam": "mijn_overzicht", "rollen": ["medewerker"], "in_aanbouw": True},
    {"titel": "Planbord", "teken": "⊞", "url_naam": "planbord", "rollen": ["eigenaar"], "in_aanbouw": True},
    {"titel": "Overzichten", "teken": "≡", "url_naam": "urenexport", "rollen": ["eigenaar"], "in_aanbouw": True},
    {"titel": "Aanwezigheid", "teken": "●", "url_naam": "aanwezigheid", "rollen": ["eigenaar"], "in_aanbouw": True},
    {"titel": "Foto's", "teken": "▣", "url_naam": "fotos", "rollen": ["medewerker", "eigenaar"]},
    {"titel": "Loonstrook", "teken": "€", "url_naam": "loonstrook", "rollen": ["medewerker", "eigenaar"]},
    # Het Django-beheerscherm is geen scherm voor de klant: het toont alle
    # velden en verwijdert zonder vangnet. Alleen wie het systeem beheert
    # (is_staff) ziet deze tegel — de rol "eigenaar" geeft er geen toegang toe.
    # Hangt aan is_staff, niet aan een rol: wie het systeem beheert hoeft in
    # de app geen eigenaar te zijn.
    {"titel": "Beheer", "teken": "⚙", "url": "/beheer/", "rollen": ["medewerker", "eigenaar"], "alleen_beheerder": True},
]


@login_required
def start(request):
    rol = request.user.rol
    tegels = []
    for tegel in TEGELS:
        if rol not in tegel["rollen"]:
            continue
        if tegel.get("alleen_beheerder") and not request.user.is_staff:
            continue
        tegel = dict(tegel)
        if "url_naam" in tegel:
            tegel["url"] = reverse(tegel["url_naam"])
        # Een scherm dat nog gebouwd wordt tonen we gedimd en niet-klikbaar:
        # de tegel bestaat al zodat het beginscherm niet elke week verspringt,
        # maar erop tikken levert niets op.
        if tegel.get("in_aanbouw"):
            tegel["url"] = None
        # het loonstrookportaal is een andere site; die opent in een eigen
        # tabblad zodat je je uren niet kwijtraakt
        tegel["extern"] = str(tegel.get("url") or "").startswith("http")
        tegels.append(tegel)
    return render(request, "start.html", {"tegels": tegels, "vandaag": date.today()})


@login_required
def in_aanbouw(request):
    """Tijdelijke view voor schermen die nog gebouwd worden.

    Ze hebben nu al een geregistreerde url-naam, zodat de rest van de app
    ernaar kan verwijzen zonder dat er halverwege links omgehangen moeten
    worden. Zie config/urls.py.
    """
    return render(request, "in_aanbouw.html", status=404)


@login_required
def loonstrook(request):
    """Doorsturen naar Loondossier: naar de app als die er is, anders naar
    de website."""
    useragent = request.headers.get("User-Agent", "")
    op_iphone = any(toestel in useragent for toestel in ("iPhone", "iPad", "iPod"))
    if not op_iphone:
        # Android regelt dit zelf; op een computer is er geen app.
        return redirect(LOONDOSSIER_WEB)
    return render(request, "loonstrook.html", {"app_adres": LOONDOSSIER_APP, "web_adres": LOONDOSSIER_WEB})
