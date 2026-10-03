"""Wie is er op welke dag: het vaste rooster, met de afwijkingen erover.

Losse module omdat twee schermen dezelfde rekensom nodig hebben: de
werkplanning (het hele rooster) en het startscherm ("6 van 9 aanwezig").
Staat hij in één view, dan tellen die twee vroeg of laat verschillend.

Een cel heeft één van vijf standen:

- aanwezig  groen; zo gezet, of ingepland op een klus
- onbekend  nog niet ingevuld: een werkdag volgens het rooster waar niemand
            iets heeft gezet. Telt niet als aanwezig. Tot 03-10-2026 stond
            zo'n dag vanzelf op aanwezig; Floris wilde dat niet meer.
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
from .models import Aanwezigheid, Inzet, Uurblok

AANWEZIG = "aanwezig"
ONBEKEND = "onbekend"
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


def nederlandse_feestdagen(jaar):
    """Alle Nederlandse feestdagen van een jaar, als {datum: (naam, vrij)}.

    `vrij` zegt of De Groene M dan dicht is. Afgelezen uit de werkplanning
    van 2026: op die dagen staat iedereen rood. Goede Vrijdag en
    Bevrijdingsdag staan er wel bij, maar als werkdag — op 5 mei 2026 werd er
    gewoon gewerkt. Koningsdag schuift naar de 26e als de 27e op zondag valt.
    """
    paasdag = pasen(jaar)
    koningsdag = date(jaar, 4, 27)
    if koningsdag.weekday() == 6:
        koningsdag = date(jaar, 4, 26)
    return {
        date(jaar, 1, 1): ("Nieuwjaarsdag", True),
        paasdag - timedelta(days=2): ("Goede Vrijdag", False),
        paasdag: ("1e Paasdag", True),
        paasdag + timedelta(days=1): ("2e Paasdag", True),
        koningsdag: ("Koningsdag", True),
        date(jaar, 5, 5): ("Bevrijdingsdag", False),
        paasdag + timedelta(days=39): ("Hemelvaartsdag", True),
        paasdag + timedelta(days=49): ("1e Pinksterdag", True),
        paasdag + timedelta(days=50): ("2e Pinksterdag", True),
        date(jaar, 12, 25): ("1e Kerstdag", True),
        date(jaar, 12, 26): ("2e Kerstdag", True),
    }


def feestdagen(jaar):
    """Alleen de vrije feestdagen, als {datum: naam}: daarop staat iedereen
    volgens zijn vaste werkdagen op afwezig."""
    return {dag: naam for dag, (naam, vrij) in nederlandse_feestdagen(jaar).items() if vrij}


def _tussen(van, tot, per_jaar):
    gevonden = {}
    for jaar in range(van.year, tot.year + 1):
        gevonden.update(per_jaar(jaar))
    return {dag: waarde for dag, waarde in gevonden.items() if van <= dag <= tot}


def feestdagen_tussen(van, tot):
    return _tussen(van, tot, feestdagen)


def nederlandse_feestdagen_tussen(van, tot):
    return _tussen(van, tot, nederlandse_feestdagen)


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
    if dag.weekday() not in (medewerker.vaste_werkdagen or []):
        # Geen werkdag voor hem, feestdag of niet: een oproepkracht op
        # Kerst is gewoon vrij, niet afwezig.
        return Cel(medewerker, dag, VRIJ, True)
    if feestdag:
        return Cel(medewerker, dag, AFWEZIG, True, feestdag=feestdag)
    return Cel(medewerker, dag, ONBEKEND, True)


def werkdag(medewerker, dag, feestdag=""):
    """Werkt hij deze dag volgens zijn rooster (geen weekend of vaste vrije
    dag, geen vrije feestdag, in dienst)? Los van wat er is ingevuld."""
    return cel(medewerker, dag, feestdag=feestdag).stand == ONBEKEND


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
                # Ingepland op een klus = er die dag zijn, ook als niemand de
                # aanwezigheid apart heeft ingevuld (planning van vóór
                # 03-10-2026 heeft daar geen rij voor).
                if c.klussen and c.stand == ONBEKEND:
                    c.stand = AANWEZIG
            uitkomst[(m.pk, dag)] = c
    return uitkomst


def aantal_aanwezig(dag):
    """Voor het startscherm: (aanwezig, in dienst) op deze dag."""
    medewerkers = [m for m in medewerkers_tussen(dag, dag) if in_dienst_op(m, dag)]
    cellen = rooster(medewerkers, [dag])
    aanwezig = sum(1 for c in cellen.values() if c.stand == AANWEZIG)
    return aanwezig, len(medewerkers)


def ingepland_zonder_uren(van, tot, vandaag):
    """{(medewerker_id, datum)} — wie op een dag op een klus ingepland stond
    (werkplanning) maar die dag geen uren schreef. Alleen dagen vóór vandaag:
    uren worden 's avonds geschreven, en 's ochtends zou het anders bij
    iedereen staan. Voor het weekoverzicht (U9, Floris 03-10-2026: "ingepland
    maar nog geen uren")."""
    tot = min(tot, vandaag - timedelta(days=1))
    if tot < van:
        return set()
    ingepland = set(Inzet.objects.filter(datum__range=(van, tot)).values_list("medewerker_id", "datum"))
    geschreven = set(Uurblok.objects.filter(datum__range=(van, tot)).values_list("medewerker_id", "datum"))
    return ingepland - geschreven
