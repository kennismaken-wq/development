from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.db.models import Case, IntegerField, Max, Prefetch, Q, Value, When
from django.db.models.functions import Lower
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from klussen import voorbeeld
from klussen.models import Bijlage, Klus
from uren.models import Aanwezigheid, Uurblok
from uren import totalen

from .forms import (
    EigenGegevensForm,
    EigenWachtwoordForm,
    MedewerkerForm,
    NieuweMedewerkerForm,
    WachtwoordForm,
)
from .models import Medewerker
from . import testgegevens as demo_gegevens
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


def _onderdelen_met_cijfers(gebruiker, vandaag, maandag, zondag, uren):
    """De tegels voor het startscherm, elk met één regel die iets zegt wat je
    anders had moeten opzoeken: hoeveel klussen er lopen, wie er vandaag is.

    De lijsten komen uit medewerkers/tegels.py, dezelfde bron als de
    navigatiebalk — wie wat mag zien staat dus op één plek.
    """
    actieve_klussen = Klus.objects.filter(actief=True).count()
    fotos = Bijlage.objects.filter(soort=Bijlage.Soort.FOTO).count()

    info = {
        "mijn_uren": f"{uren['week']} deze week",
        "klussen": f"{actieve_klussen} lopend",
        "fotos": f"{fotos} foto's",
        "loonstrook": "bij Loondossier",
    }

    if gebruiker.is_eigenaar:
        in_dienst = Medewerker.objects.filter(uit_dienst_sinds__isnull=True).count()
        aanwezig = Aanwezigheid.objects.filter(datum=vandaag, aanwezig=True).count()
        gewerkt_deze_week = (
            Uurblok.objects.filter(datum__range=(maandag, zondag))
            .values("medewerker")
            .distinct()
            .count()
        )
        info["medewerkers"] = f"{in_dienst} in dienst"
        info["aanwezigheid"] = f"{aanwezig} van {in_dienst} aanwezig"
        info["urenexport"] = f"{vandaag:%B}".lower()
        info["planbord"] = f"{gewerkt_deze_week} aan het werk"

    onderdelen = zichtbare_tegels(gebruiker) + zichtbare_profieltegels(gebruiker)

    # Het planbord staat sinds 17-09 niet in de navigatiebalk (zie
    # medewerkers/tegels.py), maar hoort wel op het startscherm: het is het
    # scherm dat Maarten 's ochtends opent.
    if gebruiker.is_eigenaar:
        # Op plek twee, niet achteraan: dit is het scherm dat de eigenaar
        # 's ochtends als eerste opent na zijn eigen uren.
        onderdelen.insert(
            1,
            {"titel": "Planbord", "icoon": "planbord", "url_naam": "planbord",
             "url": reverse("planbord"), "extern": False},
        )

    for onderdeel in onderdelen:
        onderdeel["info"] = info.get(onderdeel.get("url_naam"), "")

    # Start en Mijn profiel staan al in de balk; die hoeven hier niet ook nog.
    return [o for o in onderdelen if o.get("url_naam") not in ("mijn_profiel", "start")]


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
    # vooraan, ook als dat vorige week was. Alleen actieve klussen: een
    # afgeronde klus hoort niet meer bovenaan het startscherm.
    klussen_recent = list(
        Klus.objects.annotate(
            laatste_uur=Max("uurblokken__datum", filter=Q(uurblokken__medewerker=request.user))
        )
        .filter(laatste_uur__isnull=False, actief=True)
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
            "onderdelen": _onderdelen_met_cijfers(request.user, vandaag, maandag, zondag, uren_stats),
            # TIJDELIJK: de opruimknop verschijnt alleen zolang er
            # testmedewerkers in de database staan.
            "testgegevens_aanwezig": request.user.is_eigenaar
            and Medewerker.objects.filter(
                username__startswith=demo_gegevens.VOORVOEGSEL
            ).exists(),
            "klussen_recent": klussen_recent,
            "uren_stats": uren_stats,
            "recente_fotos": recente_fotos,
        },
    )


@login_required
def mijn_profiel(request):
    """Je eigen gegevens: bekijken en wijzigen, plus wachtwoord en uitloggen.

    Allebei de formulieren staan ingeklapt op deze pagina en versturen naar
    dit adres; je blijft dus op /mijn-profiel/ in plaats van heen en weer te
    springen tussen schermen. Na opslaan een omleiding naar dezelfde pagina,
    zodat verversen niet opnieuw opslaat.
    """
    # De gegevens staan er altijd als formulier, alleen niet bewerkbaar. Met
    # "Gegevens wijzigen" gaan dezelfde velden open, zodat het scherm niet
    # verspringt tussen een lees- en een schrijfversie.
    bewerken = request.GET.get("bewerken") == "1"
    gegevens = EigenGegevensForm(instance=request.user)
    wachtwoord = EigenWachtwoordForm(request.user)

    if request.method == "POST":
        if request.POST.get("actie") == "wachtwoord":
            wachtwoord = EigenWachtwoordForm(request.user, request.POST)
            if wachtwoord.is_valid():
                wachtwoord.opslaan()
                # Zonder dit ben je na het wijzigen je eigen sessie kwijt.
                update_session_auth_hash(request, request.user)
                messages.success(request, "Je wachtwoord is gewijzigd.")
                return redirect("mijn_profiel")
        else:
            gegevens = EigenGegevensForm(request.POST, instance=request.user)
            if gegevens.is_valid():
                gegevens.save()
                messages.success(request, "Je gegevens zijn bijgewerkt.")
                return redirect("mijn_profiel")

    # Bij een fout blijft het formulier open staan, anders zie je niet waarom
    # er niets is opgeslagen.
    bewerken = bewerken or bool(gegevens.errors)
    if not bewerken:
        for veld in gegevens.fields.values():
            veld.widget.attrs["disabled"] = True
            # Een streepje bij wat niet is ingevuld; anders staat er een kopje
            # met niets eronder en lijkt het scherm half geladen.
            veld.widget.attrs.setdefault("placeholder", "—")

    return render(
        request,
        "profiel.html",
        {
            "formulier": gegevens,
            "bewerken": bewerken,
            "wachtwoordformulier": wachtwoord,
            "open_wachtwoord": wachtwoord.errors,
        },
    )


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


@alleen_eigenaar
def testgegevens(request):
    """TIJDELIJK — nepmedewerkers met uren aanmaken of weghalen.

    Staat onderaan het rastermenu. Zie medewerkers/testgegevens.py.
    """
    if request.method != "POST":
        return redirect("start")

    if request.POST.get("actie") == "opruimen":
        aantal = demo_gegevens.opruimen()
        messages.success(request, f"{aantal} testmedewerkers en hun uren zijn verwijderd.")
        return redirect("start")

    gekozen = request.POST.get("week")
    try:
        dag = date.fromisoformat(gekozen) if gekozen else date.today()
    except ValueError:
        dag = date.today()

    mensen, blokken = demo_gegevens.aanmaken(dag)
    maandag, zondag = demo_gegevens.week_van(dag)
    def kort(datum):
        return datum.strftime("%d %B").lstrip("0")

    messages.success(
        request,
        f"{mensen} testmedewerkers met {blokken} uurblokken in de week van "
        f"{kort(maandag)} tot {kort(zondag)}.",
    )
    return redirect("start")
