from datetime import date, time, timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from . import kalender
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
