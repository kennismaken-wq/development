"""Welke onderdelen een gebruiker ziet en waar ze naartoe wijzen.

Gedeeld tussen het (verdwenen) tegel-grid en de navigatie-zijbalk — één
bron, zodat rol-gebaseerde zichtbaarheid maar op één plek hoeft te kloppen.
Zie ook de context processor in context_processors.py, die dit voor elke
pagina beschikbaar maakt, niet alleen het startscherm.
"""

from django.urls import reverse

# Loondossier heeft twee ingangen. Op Android staat in hun assetlinks.json
# dat de app elk adres van mijn.loondossier.nl mag afvangen, dus daar opent
# de app vanzelf als hij geinstalleerd is. Op een iPhone geldt dat maar voor
# een pad: /open-app/. Wie dat pad opent zonder de app te hebben, komt op een
# foutpagina, en of de app er staat kan iOS ons niet vertellen. Daarom vragen
# we het daar een keer en onthouden we het antwoord op het toestel zelf.
LOONDOSSIER_WEB = "https://mijn.loondossier.nl/Aanmelden"

# Elk onderdeel heeft zijn definitieve url_naam, ook als het scherm nog niet
# bestaat — die namen staan geregistreerd in config/urls.py. Een tegel met
# "in_aanbouw" wordt gedimd en niet-klikbaar getoond. Is jouw scherm af, haal
# dan alléén die vlag hier weg en verplaats de route uit config/urls.py naar je
# eigen urls.py. Zo hoeft niemand anders deze lijst aan te raken.
#
# "icoon" wijst naar een sleutel in pictogrammen.PICTOGRAMMEN — de zijbalk
# tekent daarmee een lijnicoon i.p.v. een los teken.
TEGELS = [
    {"titel": "Uren schrijven", "icoon": "uren", "url_naam": "mijn_uren", "rollen": ["medewerker", "eigenaar"]},
    {"titel": "Klussen", "icoon": "klussen", "url_naam": "klussen", "rollen": ["medewerker", "eigenaar"]},
    # Ook voor de eigenaar: hij is degene die de maand van een ander opzoekt,
    # en met alleen "medewerker" in deze lijst is het scherm voor hem onbereikbaar.
    {"titel": "Mijn overzicht", "icoon": "overzicht", "url_naam": "mijn_overzicht", "rollen": ["medewerker", "eigenaar"]},
    {"titel": "Planbord", "icoon": "planbord", "url_naam": "planbord", "rollen": ["eigenaar"]},
    {"titel": "Overzichten", "icoon": "export", "url_naam": "urenexport", "rollen": ["eigenaar"]},
    {"titel": "Aanwezigheid", "icoon": "aanwezigheid", "url_naam": "aanwezigheid", "rollen": ["eigenaar"], "in_aanbouw": True},
    {"titel": "Foto's", "icoon": "fotos", "url_naam": "fotos", "rollen": ["medewerker", "eigenaar"]},
    {"titel": "Loonstrook", "icoon": "loonstrook", "url_naam": "loonstrook", "rollen": ["medewerker", "eigenaar"]},
    # Het Django-beheerscherm is geen scherm voor de klant: het toont alle
    # velden en verwijdert zonder vangnet. Alleen wie het systeem beheert
    # (is_staff) ziet deze tegel — de rol "eigenaar" geeft er geen toegang toe.
    # Hangt aan is_staff, niet aan een rol: wie het systeem beheert hoeft in
    # de app geen eigenaar te zijn.
    {"titel": "Beheer", "icoon": "beheer", "url": "/beheer/", "rollen": ["medewerker", "eigenaar"], "alleen_beheerder": True},
]


def zichtbare_tegels(user):
    """De tegels die deze gebruiker mag zien, met opgeloste url en
    gedimde/niet-klikbare status voor onderdelen die nog gebouwd worden."""
    rol = user.rol
    tegels = []
    for tegel in TEGELS:
        if rol not in tegel["rollen"]:
            continue
        if tegel.get("alleen_beheerder") and not user.is_staff:
            continue
        tegel = dict(tegel)
        if "url_naam" in tegel:
            tegel["url"] = reverse(tegel["url_naam"])
        # Een scherm dat nog gebouwd wordt tonen we gedimd en niet-klikbaar:
        # de tegel bestaat al zodat de navigatie niet elke week verspringt,
        # maar erop tikken levert niets op.
        if tegel.get("in_aanbouw"):
            tegel["url"] = None
        # het loonstrookportaal is een andere site; die opent in een eigen
        # tabblad zodat je je uren niet kwijtraakt
        tegel["extern"] = str(tegel.get("url") or "").startswith("http")
        tegels.append(tegel)
    return tegels
