from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Case, IntegerField, Max, Prefetch, Q, Value, When
from django.db.models.functions import Lower
from django.shortcuts import get_object_or_404, redirect, render

from klussen import voorbeeld
from klussen.models import Bijlage, Klus
from uren.models import Aanwezigheid
from uren import totalen

from .forms import MedewerkerForm, NieuweMedewerkerForm, WachtwoordForm
from .models import Medewerker
from .rechten import alleen_eigenaar
from .tegels import zichtbare_profieltegels, zichtbare_tegels

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
    klussen_recent = list(
        Klus.objects.annotate(
            laatste_uur=Max("uurblokken__datum", filter=Q(uurblokken__medewerker=request.user))
        )
        .filter(laatste_uur__isnull=False)
        .prefetch_related(
            Prefetch(
                "bijlagen",
                queryset=Bijlage.objects.order_by("-datum", "-toegevoegd_op"),
                to_attr="voorbeeld_bijlagen",
            )
        )
        .order_by("-laatste_uur")[:10]
    )
    # Zelfde gewaaierde voorproefje als op het foto's-scherm (klussen/views.py:fotos).
    for klus in klussen_recent:
        klus.voorbeeld_items, klus.voorbeeld_meer = voorbeeld.items_voor_stapel(klus)

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


def _te_beheren(gebruiker):
    """Wie deze gebruiker mag zien en bewerken, in de volgorde waarin je een
    ploeg leest: eerst de eigenaars, daarna de medewerkers, en binnen die
    twee op voornaam.

    De volgorde staat expliciet in een Case en leunt niet op de alfabetische
    volgorde van de rolnamen zelf — anders verschuift de lijst zodra er ooit
    een rol bijkomt of er een anders gaat heten.
    """
    return (
        Medewerker.objects.annotate(
            rolvolgorde=Case(
                When(rol=Medewerker.Rol.EIGENAAR, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        .order_by("rolvolgorde", Lower("first_name"), Lower("last_name"), "username")
    )


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


@alleen_eigenaar
def medewerker_nieuw(request):
    if request.method == "POST":
        formulier = NieuweMedewerkerForm(request.POST)
        if formulier.is_valid():
            medewerker = formulier.save()
            messages.success(
                request,
                f"{medewerker.naam} kan inloggen met gebruikersnaam “{medewerker.username}” "
                "en het wachtwoord dat je net hebt gekozen.",
            )
            return redirect("medewerkers")
    else:
        formulier = NieuweMedewerkerForm(initial={"in_dienst_sinds": date.today()})
    return render(request, "medewerkers/form.html", {"formulier": formulier, "nieuw": True})


@alleen_eigenaar
def medewerker_bewerken(request, pk):
    medewerker = get_object_or_404(_te_beheren(request.user), pk=pk)
    if request.method == "POST":
        formulier = MedewerkerForm(request.POST, instance=medewerker)
        if formulier.is_valid():
            formulier.save()
            messages.success(request, f"{medewerker.naam} is bijgewerkt.")
            return redirect("medewerkers")
    else:
        formulier = MedewerkerForm(instance=medewerker)
    return render(
        request,
        "medewerkers/form.html",
        {"formulier": formulier, "nieuw": False, "medewerker": medewerker},
    )


@alleen_eigenaar
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


@alleen_eigenaar
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


# ══════════ TIJDELIJK: tweede beginscherm als vergelijking ══════════
# Een rasterweergave van de onderdelen, elk met een cijfer erbij, zodat we
# kunnen zien of dat prettiger werkt dan het huidige startscherm. Staat als
# tweede huisje in de zijbalk. Weghalen = deze view, templates/menu.html, de
# route in medewerkers/urls.py en het tweede huisje in basis.html.


@login_required
def menu_demo(request):
    vandaag = date.today()
    maandag = vandaag - timedelta(days=vandaag.weekday())
    zondag = maandag + timedelta(days=6)

    uren = totalen.totaal_en_week(request.user, maandag, zondag)
    actieve_klussen = Klus.objects.filter(actief=True).count()
    fotos = Bijlage.objects.filter(soort=Bijlage.Soort.FOTO).count()

    # Per onderdeel één regel die iets zegt wat je anders had moeten opzoeken.
    info = {
        "mijn_uren": f"{uren['week']} deze week",
        "klussen": f"{actieve_klussen} lopend",
        "fotos": f"{fotos} foto's",
        "loonstrook": "bij Loondossier",
    }

    if request.user.is_eigenaar:
        in_dienst = Medewerker.objects.filter(uit_dienst_sinds__isnull=True).count()
        aanwezig = Aanwezigheid.objects.filter(datum=vandaag, aanwezig=True).count()
        info["medewerkers"] = f"{in_dienst} in dienst"
        info["aanwezigheid"] = f"{aanwezig} van {in_dienst} aanwezig"
        info["urenexport"] = f"{vandaag:%B}".lower()

    onderdelen = zichtbare_tegels(request.user) + zichtbare_profieltegels(request.user)
    for onderdeel in onderdelen:
        onderdeel["info"] = info.get(onderdeel.get("url_naam"), "")

    # Het profielscherm en dit menu zelf hoeven hier niet als tegel te staan.
    onderdelen = [o for o in onderdelen if o.get("url_naam") not in ("mijn_profiel", "menu_demo")]

    return render(request, "menu.html", {"onderdelen": onderdelen, "vandaag": vandaag})
