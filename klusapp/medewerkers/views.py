from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from klussen.models import Klus

# Loondossier heeft twee ingangen. Op Android staat in hun assetlinks.json
# dat de app elk adres van mijn.loondossier.nl mag afvangen, dus daar opent
# de app vanzelf als hij geinstalleerd is. Op een iPhone geldt dat maar voor
# een pad: /open-app/. Wie dat pad opent zonder de app te hebben, komt op een
# foutpagina, en of de app er staat kan iOS ons niet vertellen. Daarom vragen
# we het daar een keer en onthouden we het antwoord op het toestel zelf.
LOONDOSSIER_WEB = "https://mijn.loondossier.nl/Aanmelden"
LOONDOSSIER_APP = "https://mijn.loondossier.nl/open-app/"


@login_required
def start(request):
    """Het beginscherm: een begroeting en de klussen waar je deze week aan
    hebt gewerkt. Navigatie zit niet meer hier maar in de zijbalk
    (basis.html) — die krijgt zijn tegels via de context processor, dus
    hoeft hier niet te worden meegegeven.
    """
    vandaag = date.today()
    maandag = vandaag - timedelta(days=vandaag.weekday())
    zondag = maandag + timedelta(days=6)
    klussen_deze_week = (
        Klus.objects.filter(uurblokken__medewerker=request.user, uurblokken__datum__range=(maandag, zondag))
        .distinct()
        .order_by("-aangemaakt_op")[:5]
    )
    return render(request, "start.html", {"vandaag": vandaag, "klussen_deze_week": klussen_deze_week})


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
