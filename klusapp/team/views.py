"""Ons team: iedereen die bij De Groene M werkt of werkte, met per persoon
zijn foto's, zijn klussen, zijn uren en zijn beste score in het springspel.

Geen eigen model: alles komt uit wat er al is (Uurblok, Bijlage, BesteScore).
Privégegevens (adres, telefoon, noodcontact) staan hier bewust niet; die zijn
voor de eigenaar en staan op de persoonskaart bij Medewerkers.
"""

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, render

from klussen.models import Bijlage
from klussen.views import _fotos_tot
from medewerkers.models import Medewerker
from spel.models import BesteScore
from spel.scorebord import ranglijst
from uren.kalender import als_uren
from uren.models import Uurblok
from uren.totalen import DUUR_IN_MINUTEN


@login_required
def team(request):
    """Huidige collega's bovenaan, oud-collega's eronder."""
    # Uit dienst zetten maakt een account ook inactief (medewerker_dienst);
    # die mensen horen hier juist wel, als oud-collega.
    mensen = list(Medewerker.objects.select_related("beste_score"))
    return render(
        request,
        "team/lijst.html",
        {
            "in_dienst": [m for m in mensen if m.is_active and not m.uit_dienst_sinds],
            "oud": sorted((m for m in mensen if m.uit_dienst_sinds), key=lambda m: m.uit_dienst_sinds, reverse=True),
        },
    )


def _klussen_van(persoon):
    """Op welke klussen iemand gewerkt heeft, de laatste eerst, met per klus
    zijn uren en de periode. Afgeleid uit de geschreven uren, net als het
    tabblad Uren in het klusdossier (uren/totalen.py)."""
    verzameld = {}
    for blok in Uurblok.objects.filter(medewerker=persoon).select_related("klus").only(
        "datum", "begintijd", "eindtijd", "klus"
    ):
        rij = verzameld.setdefault(blok.klus_id, {"klus": blok.klus, "minuten": 0, "dagen": set()})
        rij["minuten"] += blok.duur_minuten
        rij["dagen"].add(blok.datum)
    rijen = [
        {
            "klus": rij["klus"],
            "uren": als_uren(rij["minuten"]),
            "aantal_dagen": len(rij["dagen"]),
            "eerste_dag": min(rij["dagen"]),
            "laatste_dag": max(rij["dagen"]),
        }
        for rij in verzameld.values()
    ]
    rijen.sort(key=lambda rij: (rij["laatste_dag"], rij["klus"].naam), reverse=True)
    return rijen


@login_required
def persoon(request, pk):
    persoon = get_object_or_404(Medewerker.objects, pk=pk)

    # Uren van een ander zijn voor de eigenaar: een medewerker ziet alleen
    # zijn eigen uren, ook in het klusdossier (SPEC §2). Dus het totaal en de
    # uren per klus alleen voor de eigenaar en voor jezelf. Op welke klussen
    # iemand werkte, zie je wel: dat staat ook in elk klusdossier.
    mag_uren_zien = request.user.is_eigenaar or request.user.pk == persoon.pk

    totaal_minuten = (
        Uurblok.objects.filter(medewerker=persoon).aggregate(minuten=Sum(DUUR_IN_MINUTEN))["minuten"] or 0
    )

    beste = BesteScore.objects.filter(medewerker=persoon).first()
    plaats = None
    if beste:
        for nummer, medewerker_id in enumerate(ranglijst().values_list("medewerker_id", flat=True), start=1):
            if medewerker_id == persoon.pk:
                plaats = nummer
                break

    fotos = (
        Bijlage.objects.zichtbaar_voor(request.user)
        .filter(toegevoegd_door=persoon, soort=Bijlage.Soort.FOTO)
        .select_related("toegevoegd_door", "klus")
        .order_by("-datum", "-toegevoegd_op")
    )
    foto_posts, meer_url = _fotos_tot(request, fotos)

    return render(
        request,
        "team/persoon.html",
        {
            "persoon": persoon,
            "is_ik": request.user.pk == persoon.pk,
            "mag_uren_zien": mag_uren_zien,
            "totaal_uren": als_uren(totaal_minuten),
            "klussen": _klussen_van(persoon),
            "beste": beste,
            "plaats": plaats,
            "foto_posts": foto_posts,
            "meer_url": meer_url,
            "aantal_fotos": fotos.count(),
            "terug": request.get_full_path(),
        },
    )
