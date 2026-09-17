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
#
# TEGELS zijn de vaste iconen in de navigatiebalk zelf: bewust maar vijf voor
# iedereen (Start staat los in basis.html, dus hier vier) plus Aanwezigheid
# als extra voor de eigenaar, die dat scherm dagelijks gebruikt. Alles wat
# minder vaak nodig is staat in PROFIEL_TEGELS, bereikbaar via die vijfde
# tegel "Mijn profiel" — zo blijft de balk kort in plaats van dat hij vol
# loopt met elk scherm dat er ooit bijkomt.
TEGELS = [
    {"titel": "Uren schrijven", "icoon": "uren", "url_naam": "mijn_uren", "rollen": ["medewerker", "eigenaar"]},
    {"titel": "Klussen", "icoon": "klussen", "url_naam": "klussen", "rollen": ["medewerker", "eigenaar"]},
    {"titel": "Foto's", "icoon": "fotos", "url_naam": "fotos", "rollen": ["medewerker", "eigenaar"]},
    {"titel": "Aanwezigheid", "icoon": "aanwezigheid", "url_naam": "aanwezigheid", "rollen": ["eigenaar"]},
    {"titel": "Mijn profiel", "icoon": "profiel", "url_naam": "mijn_profiel", "rollen": ["medewerker", "eigenaar"]},
]

# Schermen die niet in de navigatiebalk passen maar wel bereikbaar moeten
# blijven — getoond als knoppenlijst op het profielscherm (templates/profiel.html).
PROFIEL_TEGELS = [
    {"titel": "Overzichten", "icoon": "export", "url_naam": "urenexport", "rollen": ["eigenaar"]},
    {"titel": "Loonstrook", "icoon": "loonstrook", "url_naam": "loonstrook", "rollen": ["medewerker", "eigenaar"]},
    # Het Django-beheerscherm is geen scherm voor de klant: het toont alle
    # velden en verwijdert zonder vangnet. Alleen de systeembeheerder ziet
    # deze tegel; een eigenaar komt er niet in.
    {"titel": "Beheer", "icoon": "beheer", "url": "/beheer/", "rollen": ["medewerker", "eigenaar"], "alleen_beheerder": True},
]

# Planbord is op 17-09-2026 op verzoek van Thijmen uit de navigatie gehaald
# om de balk tot vijf iconen te beperken (later apart te bespreken waar het
# terugkomt). De route en view (uren.views.planbord, url_naam "planbord")
# bestaan nog gewoon; alleen de link ernaartoe ontbreekt bewust.


def _zichtbaar(lijst, user):
    """De tegels uit `lijst` die deze gebruiker mag zien, met opgeloste url en
    gedimde/niet-klikbare status voor onderdelen die nog gebouwd worden."""
    # De systeembeheerder ziet alles wat de eigenaar ziet, plus het
    # beheerscherm; daarom kijken we hier naar wat iemand mag, niet naar de
    # letterlijke rolnaam.
    rol = "eigenaar" if user.is_eigenaar else "medewerker"
    tegels = []
    for tegel in lijst:
        if rol not in tegel["rollen"]:
            continue
        if tegel.get("alleen_beheerder") and not user.is_systeembeheerder:
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


def zichtbare_tegels(user):
    return _zichtbaar(TEGELS, user)


def zichtbare_profieltegels(user):
    return _zichtbaar(PROFIEL_TEGELS, user)
