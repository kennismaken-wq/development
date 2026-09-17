from datetime import date, timedelta

from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Max, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from klussen.models import Bijlage, Klus
from uren import totalen

from .tegels import zichtbare_profieltegels

from .forms import MedewerkerForm, NieuweMedewerkerForm, WachtwoordForm
from .models import Medewerker
from .rechten import alleen_eigenaar

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
    """Het beginscherm: een begroeting, de klussen waar je het laatst uren op
    hebt geschreven, je uren-statistieken en de laatst toegevoegde foto's.
    Navigatie zit niet meer hier maar in de zijbalk (basis.html) — die krijgt
    zijn tegels via de context processor, dus hoeft hier niet te worden
    meegegeven.
    """
    vandaag = date.today()
    maandag = vandaag - timedelta(days=vandaag.weekday())
    zondag = maandag + timedelta(days=6)

    # Niet beperkt tot deze week: de klus waar je het laatst aan werkte staat
    # vooraan, ook als dat vorige week was.
    klussen_recent = (
        Klus.objects.annotate(
            laatste_uur=Max("uurblokken__datum", filter=Q(uurblokken__medewerker=request.user))
        )
        .filter(laatste_uur__isnull=False)
        .order_by("-laatste_uur")[:10]
    )

    uren_stats = totalen.totaal_en_week(request.user, maandag, zondag)

    recente_fotos = (
        Bijlage.objects.filter(soort=Bijlage.Soort.FOTO, klus__isnull=False)
        .select_related("klus")
        .order_by("-toegevoegd_op")[:20]
    )

    return render(
        request,
        "start.html",
        {
            "vandaag": vandaag,
            "klussen_recent": klussen_recent,
            "uren_stats": uren_stats,
            "recente_fotos": recente_fotos,
        },
    )


@login_required
def mijn_profiel(request):
    """Naam, rol en uitloggen, met daaronder de schermen die niet in de
    vaste navigatiebalk passen (zie medewerkers/tegels.py)."""
    return render(request, "profiel.html", {"profiel_tegels": zichtbare_profieltegels(request.user)})


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


def alleen_werkgever(view):
    """Schermen waar alleen de werkgever bij mag: wachtwoorden zetten, iemand
    aannemen of uit dienst zetten.

    Wij als systeembeheerder mogen die gegevens inzien om te kunnen helpen,
    maar niet wijzigen — een wachtwoord zetten is een account overnemen, en
    dat hoort niet bij onderhoud.
    """

    @wraps(view)
    @alleen_eigenaar
    def binnen(request, *args, **kwargs):
        if request.user.is_systeembeheerder:
            raise Http404
        return view(request, *args, **kwargs)

    return binnen


def _te_beheren(gebruiker):
    """Wie deze gebruiker mag zien en bewerken.

    Een eigenaar beheert zijn eigen mensen; onze systeembeheerders vallen
    daar niet onder en zijn voor hem onzichtbaar.
    """
    mensen = Medewerker.objects.all()
    if not gebruiker.is_systeembeheerder:
        mensen = mensen.exclude(rol=Medewerker.Rol.BEHEERDER)
    return mensen


@alleen_eigenaar
def medewerker_lijst(request):
    mensen = _te_beheren(request.user)
    return render(
        request,
        "medewerkers/lijst.html",
        {
            "in_dienst": mensen.filter(uit_dienst_sinds__isnull=True),
            "uit_dienst": mensen.filter(uit_dienst_sinds__isnull=False),
        },
    )


@alleen_werkgever
def medewerker_nieuw(request):
    if request.method == "POST":
        formulier = NieuweMedewerkerForm(request.POST, door=request.user)
        if formulier.is_valid():
            medewerker = formulier.save()
            messages.success(
                request,
                f"{medewerker.naam} kan inloggen met gebruikersnaam “{medewerker.username}” "
                "en het wachtwoord dat je net hebt gekozen.",
            )
            return redirect("medewerkers")
    else:
        formulier = NieuweMedewerkerForm(door=request.user, initial={"in_dienst_sinds": date.today()})
    return render(request, "medewerkers/form.html", {"formulier": formulier, "nieuw": True})


@alleen_eigenaar
def medewerker_bewerken(request, pk):
    medewerker = get_object_or_404(_te_beheren(request.user), pk=pk)
    if request.user.is_systeembeheerder:
        # Meekijken mag, meeschrijven niet: de mensen van de klant zijn niet
        # van ons om aan te passen.
        return render(request, "medewerkers/inzien.html", {"medewerker": medewerker})
    if request.method == "POST":
        formulier = MedewerkerForm(request.POST, instance=medewerker, door=request.user)
        if formulier.is_valid():
            formulier.save()
            messages.success(request, f"{medewerker.naam} is bijgewerkt.")
            return redirect("medewerkers")
    else:
        formulier = MedewerkerForm(instance=medewerker, door=request.user)
    return render(
        request,
        "medewerkers/form.html",
        {"formulier": formulier, "nieuw": False, "medewerker": medewerker},
    )


@alleen_werkgever
def medewerker_wachtwoord(request, pk):
    medewerker = get_object_or_404(_te_beheren(request.user), pk=pk)
    if request.method == "POST":
        formulier = WachtwoordForm(request.POST)
        if formulier.is_valid():
            medewerker.set_password(formulier.cleaned_data["wachtwoord"])
            medewerker.save()
            messages.success(request, f"Het wachtwoord van {medewerker.naam} is gewijzigd.")
            return redirect("medewerkers")
    else:
        formulier = WachtwoordForm()
    return render(
        request,
        "medewerkers/wachtwoord.html",
        {"formulier": formulier, "medewerker": medewerker},
    )


@alleen_werkgever
def medewerker_dienst(request, pk):
    """Uit dienst zetten of terughalen.

    Verwijderen doen we nooit: aan een medewerker hangen uren, foto's en
    aanwezigheid, en die hoort de boekhouder over zeven jaar nog terug te
    kunnen vinden. Uit dienst betekent: kan niet meer inloggen, blijft wel
    in de overzichten van vroeger staan.
    """
    medewerker = get_object_or_404(_te_beheren(request.user), pk=pk)
    if request.method != "POST":
        return redirect("medewerkers")
    if medewerker.pk == request.user.pk:
        messages.error(request, "Je kunt jezelf niet uit dienst zetten.")
        return redirect("medewerkers")

    if medewerker.uit_dienst_sinds:
        medewerker.uit_dienst_sinds = None
        medewerker.is_active = True
        bericht = f"{medewerker.naam} is weer in dienst en kan weer inloggen."
    else:
        medewerker.uit_dienst_sinds = date.today()
        medewerker.is_active = False
        bericht = f"{medewerker.naam} staat uit dienst. Zijn uren en foto's blijven bewaard."
    medewerker.save()
    messages.success(request, bericht)
    return redirect("medewerkers")
