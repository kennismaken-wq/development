import calendar
from datetime import date, time, timedelta

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from medewerkers.models import Medewerker

from . import export, kalender
from .forms import UurblokForm
from .models import Uurblok


def _gekozen_dag(request):
    """De dag waar de kalender op staat. Standaard vandaag: uren worden
    dezelfde avond ingevuld, dus dat is bijna altijd de goede."""
    gevraagd = request.GET.get("dag")
    if gevraagd:
        try:
            return date.fromisoformat(gevraagd)
        except ValueError:
            pass
    return date.today()


def _tijd_uit(waarde):
    try:
        return time.fromisoformat(waarde)
    except (TypeError, ValueError):
        return None


def _terug_naar_dag(dag):
    return redirect(f"{reverse('mijn_uren')}?dag={dag.isoformat()}")


@login_required
def mijn_uren(request):
    dag = _gekozen_dag(request)
    maandag = dag - timedelta(days=dag.weekday())
    zondag = maandag + timedelta(days=6)
    vandaag = date.today()

    blokken = (
        Uurblok.objects.filter(medewerker=request.user, datum__range=(maandag, zondag))
        .select_related("klus")
        .order_by("begintijd")
    )

    dagen = []
    for nummer in range(7):
        datum = maandag + timedelta(days=nummer)
        van_die_dag = [blok for blok in blokken if blok.datum == datum]
        dagen.append(
            {
                "datum": datum,
                "is_vandaag": datum == vandaag,
                "getekend": kalender.plaats_blokken(van_die_dag),
                "totaal": kalender.als_uren(sum(blok.duur_minuten for blok in van_die_dag)),
                "heeft_uren": bool(van_die_dag),
            }
        )

    return render(
        request,
        "uren/mijn_uren.html",
        {
            "dagen": dagen,
            "maandag": maandag,
            "zondag": zondag,
            "vorige_week": maandag - timedelta(days=7),
            "volgende_week": maandag + timedelta(days=7),
            "is_deze_week": maandag <= vandaag <= zondag,
            "weektotaal": kalender.als_uren(sum(blok.duur_minuten for blok in blokken)),
            "vakken": kalender.vakken(),
            "uurlabels": kalender.uurlabels(),
            "rasterhoogte": kalender.raster_hoogte(),
            "rijhoogte": kalender.RIJ_H,
            "vandaag": vandaag,
        },
    )


@login_required
def uurblok_nieuw(request):
    dag = _gekozen_dag(request)
    if request.method == "POST":
        formulier = UurblokForm(request.POST)
        if formulier.is_valid():
            blok = formulier.save(commit=False)
            blok.medewerker = request.user
            blok.save()
            return _terug_naar_dag(blok.datum)
    else:
        # Uit de kalender komen begin- en eindtijd mee van het vak waarop je
        # hebt gesleept; anders sluiten we aan op het laatste blok van die dag.
        van = _tijd_uit(request.GET.get("van"))
        tot = _tijd_uit(request.GET.get("tot"))
        if van is None:
            laatste = (
                Uurblok.objects.filter(medewerker=request.user, datum=dag)
                .order_by("eindtijd")
                .last()
            )
            van = laatste.eindtijd if laatste else None
        formulier = UurblokForm(initial={"datum": dag, "begintijd": van, "eindtijd": tot})
    return render(
        request, "uren/uurblok_form.html", {"formulier": formulier, "dag": dag, "nieuw": True}
    )


@login_required
def uurblok_bewerken(request, pk):
    # Een medewerker komt alleen bij zijn eigen blokken; die van een ander
    # bestaan voor hem niet.
    blok = get_object_or_404(Uurblok, pk=pk, medewerker=request.user)
    if request.method == "POST":
        formulier = UurblokForm(request.POST, instance=blok)
        if formulier.is_valid():
            formulier.save()
            return _terug_naar_dag(formulier.instance.datum)
    else:
        formulier = UurblokForm(instance=blok)
    return render(
        request,
        "uren/uurblok_form.html",
        {"formulier": formulier, "dag": blok.datum, "blok": blok, "nieuw": False},
    )


@login_required
def uurblok_verwijderen(request, pk):
    blok = get_object_or_404(Uurblok, pk=pk, medewerker=request.user)
    dag = blok.datum
    if request.method == "POST":
        blok.delete()
    return _terug_naar_dag(dag)


def _maandopties(vandaag, aantal=14):
    """De laatste veertien kalendermaanden, nieuwste eerst — ruim genoeg om
    terug te kunnen tot de start van de app zonder een aparte jaarkeuze."""
    opties = []
    jaar, maand = vandaag.year, vandaag.month
    for _ in range(aantal):
        opties.append(date(jaar, maand, 1))
        maand -= 1
        if maand == 0:
            maand, jaar = 12, jaar - 1
    return opties


def _gekozen_maand(request, vandaag):
    gevraagd = request.GET.get("maand", "")
    try:
        jaar, maand = (int(deel) for deel in gevraagd.split("-", 1))
        return date(jaar, maand, 1)
    except (TypeError, ValueError):
        return vandaag.replace(day=1)


@login_required
def urenexport(request):
    """Exportscherm voor de boekhouder: uren van een kalendermaand als Excel.

    Periode is de kalendermaand-fallback uit docs/VRAGEN-MAARTEN.md; Maarten
    heeft op 15-09-2026 wel al bevestigd dat het bestand Excel moet zijn, geen
    CSV, zodat de boekhouding er verder in kan werken.

    Alleen de eigenaar mag dit openen: de boekhouder krijgt geen account in de
    app, hij krijgt het gedownloade bestand toegestuurd (SPEC §2, punt 6).
    """
    if not request.user.is_eigenaar:
        raise Http404

    vandaag = timezone.localdate()
    gekozen_maand = _gekozen_maand(request, vandaag)
    laatste_dag = calendar.monthrange(gekozen_maand.year, gekozen_maand.month)[1]
    eind_maand = gekozen_maand.replace(day=laatste_dag)

    medewerker_pk = request.GET.get("medewerker", "")
    blokken = (
        Uurblok.objects.filter(datum__range=(gekozen_maand, eind_maand))
        .select_related("medewerker", "klus")
        .order_by(
            "medewerker__first_name", "medewerker__last_name", "medewerker__username", "datum", "begintijd"
        )
    )
    if medewerker_pk:
        blokken = blokken.filter(medewerker__pk=medewerker_pk)
    blokken = list(blokken)

    if request.GET.get("download") == "1":
        boek = export.werkboek_bouwen(blokken, f"Uren {gekozen_maand:%m-%Y}")
        antwoord = HttpResponse(
            export.werkboek_als_bytes(boek),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        antwoord["Content-Disposition"] = f'attachment; filename="uren-{gekozen_maand:%Y-%m}.xlsx"'
        return antwoord

    totalen = []
    for blok in blokken:
        if not totalen or totalen[-1]["medewerker"] != blok.medewerker:
            totalen.append({"medewerker": blok.medewerker, "minuten": 0})
        totalen[-1]["minuten"] += blok.duur_minuten
    for regel in totalen:
        regel["totaal"] = kalender.als_uren(regel["minuten"])

    return render(
        request,
        "uren/export.html",
        {
            "gekozen_maand": gekozen_maand,
            "medewerker_pk": medewerker_pk,
            "maandopties": _maandopties(vandaag),
            "medewerkers": Medewerker.objects.filter(rol=Medewerker.Rol.MEDEWERKER),
            "totalen": totalen,
        },
    )
