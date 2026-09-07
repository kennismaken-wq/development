from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import UurblokForm
from .models import Uurblok


def _gekozen_dag(request):
    """De dag die in beeld is. Standaard vandaag: uren worden dezelfde avond
    ingevuld, dus dat is bijna altijd de goede."""
    gevraagd = request.GET.get("dag")
    if gevraagd:
        try:
            return date.fromisoformat(gevraagd)
        except ValueError:
            pass
    return date.today()


def _als_uren(minuten):
    return f"{minuten // 60}:{minuten % 60:02d}"


def _terug_naar_dag(dag):
    return redirect(f"{reverse('mijn_uren')}?dag={dag.isoformat()}")


@login_required
def mijn_uren(request):
    dag = _gekozen_dag(request)
    blokken = list(
        Uurblok.objects.filter(medewerker=request.user, datum=dag)
        .select_related("klus")
        .order_by("begintijd")
    )
    maandag = dag - timedelta(days=dag.weekday())
    week = Uurblok.objects.filter(
        medewerker=request.user, datum__range=(maandag, maandag + timedelta(days=6))
    )
    return render(
        request,
        "uren/mijn_uren.html",
        {
            "dag": dag,
            "blokken": blokken,
            "dagtotaal": _als_uren(sum(blok.duur_minuten for blok in blokken)),
            "weektotaal": _als_uren(sum(blok.duur_minuten for blok in week)),
            "vorige": dag - timedelta(days=1),
            "volgende": dag + timedelta(days=1),
            "is_vandaag": dag == date.today(),
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
        laatste = (
            Uurblok.objects.filter(medewerker=request.user, datum=dag).order_by("eindtijd").last()
        )
        formulier = UurblokForm(
            initial={
                "datum": dag,
                # Meerdere klussen op een dag sluiten meestal op elkaar aan;
                # begin daarom waar het vorige blok ophield.
                "begintijd": laatste.eindtijd if laatste else None,
            }
        )
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
