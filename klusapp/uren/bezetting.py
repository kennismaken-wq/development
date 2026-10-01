"""Wie is er op welke dag: het vaste rooster, met de afwijkingen erover.

Losse module omdat twee schermen dezelfde rekensom nodig hebben: de
werkplanning (het hele rooster) en het startscherm ("6 van 9 aanwezig").
Staat hij in één view, dan tellen die twee vroeg of laat verschillend.

Een cel heeft één van vier standen:

- aanwezig  groen; uit het rooster of zo gezet
- afwezig   rood; zo gezet, of een feestdag
- vrij      geen werkdag volgens het rooster, en niets gezet: een
            oproepkracht of een parttimer op zijn vrije dag
- buiten    nog niet of niet meer in dienst; niet aan te passen

`standaard` zegt of de stand uit het rooster komt of door iemand is gezet.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta

from medewerkers.models import Medewerker

from .kalender import kleur_van
from .models import Aanwezigheid, Inzet

AANWEZIG = "aanwezig"
AFWEZIG = "afwezig"
VRIJ = "vrij"
BUITEN = "buiten"


def pasen(jaar):
    """Paaszondag, met de rekenregel van Meeus/Jones/Butcher (gregoriaans)."""
    a = jaar % 19
    b, c = divmod(jaar, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    maand, dag = divmod(h + l - 7 * m + 114, 31)
    return date(jaar, maand, dag + 1)


def feestdagen(jaar):
    """De vrije feestdagen bij De Groene M, als {datum: naam}.

    Afgelezen uit de werkplanning van 2026: op deze dagen staat iedereen
    rood. Bevrijdingsdag en Goede Vrijdag niet — op 5 mei 2026 werd er gewoon
    gewerkt. Koningsdag schuift naar de 26e als de 27e op zondag valt.
    """
    paasdag = pasen(jaar)
    koningsdag = date(jaar, 4, 27)
    if koningsdag.weekday() == 6:
        koningsdag = date(jaar, 4, 26)
    return {
        date(jaar, 1, 1): "Nieuwjaarsdag",
        paasdag: "1e Paasdag",
        paasdag + timedelta(days=1): "2e Paasdag",
        koningsdag: "Koningsdag",
        paasdag + timedelta(days=39): "Hemelvaartsdag",
        paasdag + timedelta(days=49): "1e Pinksterdag",
        paasdag + timedelta(days=50): "2e Pinksterdag",
        date(jaar, 12, 25): "1e Kerstdag",
        date(jaar, 12, 26): "2e Kerstdag",
    }


def feestdagen_tussen(van, tot):
    gevonden = {}
    for jaar in range(van.year, tot.year + 1):
        gevonden.update(feestdagen(jaar))
    return {dag: naam for dag, naam in gevonden.items() if van <= dag <= tot}


def in_dienst_op(medewerker, dag):
    if medewerker.in_dienst_sinds and dag < medewerker.in_dienst_sinds:
        return False
    if medewerker.uit_dienst_sinds and dag >= medewerker.uit_dienst_sinds:
        return False
    return True


def medewerkers_tussen(van, tot):
    """Iedereen die ergens in deze periode in dienst is, in vaste volgorde."""
    return list(
        Medewerker.objects.exclude(uit_dienst_sinds__lte=van).exclude(in_dienst_sinds__gt=tot)
    )


@dataclass
class Cel:
    medewerker: Medewerker
    datum: date
    stand: str
    standaard: bool
    reden: str = ""
    opmerking: str = ""
    feestdag: str = ""
    # De klussen waar hij die dag heen gaat (Inzet), elk met een .kleur.
    klussen: list = field(default_factory=list)

    @property
    def klus_ids(self):
        return ",".join(str(k.pk) for k in self.klussen)

    @property
    def reden_tekst(self):
        if self.feestdag and self.standaard:
            return self.feestdag
        return Aanwezigheid.Reden(self.reden).label if self.reden else ""


def cel(medewerker, dag, registratie=None, feestdag=""):
    """De stand van één medewerker op één dag."""
    if not in_dienst_op(medewerker, dag):
        return Cel(medewerker, dag, BUITEN, True)
    if registratie is not None:
        return Cel(
            medewerker,
            dag,
            AANWEZIG if registratie.aanwezig else AFWEZIG,
            False,
            reden="" if registratie.aanwezig else registratie.reden,
            opmerking=registratie.opmerking,
            feestdag=feestdag,
        )
    if feestdag:
        return Cel(medewerker, dag, AFWEZIG, True, feestdag=feestdag)
    if dag.weekday() in (medewerker.vaste_werkdagen or []):
        return Cel(medewerker, dag, AANWEZIG, True)
    return Cel(medewerker, dag, VRIJ, True)


def rooster(medewerkers, dagen):
    """{(medewerker_id, datum): Cel} voor elke medewerker op elke dag, met
    één query voor alle afwijkingen en één voor de ingeplande klussen."""
    if not dagen:
        return {}
    van, tot = min(dagen), max(dagen)
    vrij = feestdagen_tussen(van, tot)
    registraties = {
        (r.medewerker_id, r.datum): r
        for r in Aanwezigheid.objects.filter(
            datum__range=(van, tot), medewerker__in=medewerkers
        )
    }
    ingepland = {}
    for inzet in Inzet.objects.filter(datum__range=(van, tot), medewerker__in=medewerkers).select_related("klus"):
        inzet.klus.kleur = kleur_van(inzet.klus)
        ingepland.setdefault((inzet.medewerker_id, inzet.datum), []).append(inzet.klus)
    uitkomst = {}
    for m in medewerkers:
        for dag in dagen:
            c = cel(m, dag, registraties.get((m.pk, dag)), vrij.get(dag, ""))
            # Op een rode dag geen klus, ook niet als er nog een in de
            # database staat (een feestdag die er later bij kwam, bv.).
            if c.stand not in (BUITEN, AFWEZIG):
                c.klussen = ingepland.get((m.pk, dag), [])
            uitkomst[(m.pk, dag)] = c
    return uitkomst


def aantal_aanwezig(dag):
    """Voor het startscherm: (aanwezig, in dienst) op deze dag."""
    medewerkers = [m for m in medewerkers_tussen(dag, dag) if in_dienst_op(m, dag)]
    cellen = rooster(medewerkers, [dag])
    aanwezig = sum(1 for c in cellen.values() if c.stand == AANWEZIG)
    return aanwezig, len(medewerkers)
