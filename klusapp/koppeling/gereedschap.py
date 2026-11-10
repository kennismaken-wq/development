"""Wat Claude kan opvragen. Alleen lezen: geen enkele functie hier schrijft.

Elke tool is een gewone functie die een dict teruggeeft (of, voor een
bestand, een lijst MCP-inhoudsblokken). `mcp.py` maakt er JSON-RPC van.

Twee vuistregels:

- Medewerkers worden op naam gevonden, niet op id: Maarten vraagt "waar was
  Henk", en Claude moet dat zonder tussenstap kunnen doorgeven.
- Lijsten hebben een plafond. Een jaar uren is duizenden blokken; dat past
  niet in een antwoord en Claude heeft dan toch de totalen nodig. Die
  totalen kloppen altijd over de hele selectie, ook als de lijst eronder is
  afgekapt — dat staat er dan bij.
"""

import base64
import io
import json
import zipfile
from collections import defaultdict
from datetime import date, timedelta
from xml.etree import ElementTree

from django.db.models import Q
from django.utils import timezone

from klussen.models import Bijlage, Klus, Notitie
from klussen.opdrachtgevers import _sleutel
from medewerkers.models import Medewerker
from uren import bezetting
from uren.models import Dagnotitie, Inzet, Klusdag, Uurblok

DAGNAMEN = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
MAX_UURBLOKKEN = 300
MAX_LIJST = 100


class Fout(Exception):
    """Een vraag die niet te beantwoorden is zoals hij is gesteld. De tekst
    gaat naar Claude, die hem kan herstellen ("bedoelt u Sam of Samira?")."""


# ── hulpjes ───────────────────────────────────────────────────────────────


def _datum(waarde, standaard, veld):
    if waarde in (None, ""):
        return standaard
    try:
        return date.fromisoformat(str(waarde))
    except ValueError:
        raise Fout(f"{veld} moet een datum zijn als JJJJ-MM-DD, niet {waarde!r}.")


def _periode(argumenten, van, tot, max_dagen):
    van = _datum(argumenten.get("van"), van, "van")
    tot = _datum(argumenten.get("tot"), tot, "tot")
    if tot < van:
        raise Fout("'tot' ligt vóór 'van'.")
    if (tot - van).days + 1 > max_dagen:
        raise Fout(f"Vraag hooguit {max_dagen} dagen tegelijk op; dit zijn er {(tot - van).days + 1}.")
    return van, tot


def _dag(d):
    return {"datum": d.isoformat(), "dag": DAGNAMEN[d.weekday()]}


def _uren(minuten):
    return round(minuten / 60, 2)


def _tijd(t):
    return t.strftime("%H:%M")


def _naam(persoon):
    return persoon.naam if persoon else "onbekend"


def _medewerker(naam):
    """Op voornaam, achternaam, volle naam of gebruikersnaam. Precies één
    treffer of een fout die de kandidaten noemt."""
    naam = " ".join(str(naam or "").split())
    if not naam:
        return None
    iedereen = list(Medewerker.objects.all())
    sleutel = naam.casefold()
    exact = [
        m
        for m in iedereen
        if sleutel in (m.naam.casefold(), m.username.casefold(), m.first_name.casefold(), m.last_name.casefold())
    ]
    if len(exact) == 1:
        return exact[0]
    kandidaten = exact or [m for m in iedereen if sleutel in m.naam.casefold() or sleutel in m.username.casefold()]
    if len(kandidaten) == 1:
        return kandidaten[0]
    if not kandidaten:
        raise Fout(f"Geen medewerker gevonden met de naam {naam!r}. Wel: {', '.join(m.naam for m in iedereen)}.")
    raise Fout(f"{naam!r} kan meerdere mensen zijn: {', '.join(m.naam for m in kandidaten)}. Welke bedoelt u?")


def _klus(klus_id):
    if klus_id in (None, ""):
        return None
    try:
        return Klus.objects.get(pk=int(klus_id))
    except (ValueError, TypeError, Klus.DoesNotExist):
        raise Fout(f"Er is geen klus met id {klus_id!r}. Zoek hem eerst op met zoek_klussen.")


def _klus_kort(klus):
    return {
        "klus_id": klus.pk,
        "naam": klus.naam,
        "soort": klus.get_soort_display(),
        "opdrachtgever": klus.opdrachtgever,
        "adres": ", ".join(deel for deel in (klus.adres, klus.plaats) if deel),
        "status": "actief" if klus.actief else "afgerond",
    }


def _bestand_kort(b):
    return {
        "bestand_id": b.pk,
        "naam": b.toonnaam,
        "soort": "foto" if b.is_foto else "document",
        "bestandstype": b.extensie,
        "datum": b.datum.isoformat(),
        "toelichting": b.toelichting,
        "klus_id": b.klus_id,
        "klus": b.klus.naam if b.klus_id else "(algemeen, niet aan een klus gekoppeld)",
        "toegevoegd_door": _naam(b.toegevoegd_door),
        "alleen_zichtbaar_voor": [m.naam for m in b.zichtbaar_voor.all()],
    }


def _medewerkerfilter(argumenten):
    return _medewerker(argumenten.get("medewerker"))


# ── tools ─────────────────────────────────────────────────────────────────


def vandaag(argumenten):
    nu = timezone.localdate()
    jaar, week, _ = nu.isocalendar()
    return {**_dag(nu), "weeknummer": week, "jaar": jaar, "tijd": timezone.localtime().strftime("%H:%M")}


def zoek_klussen(argumenten):
    rijen = Klus.objects.all()
    status = argumenten.get("status") or "alle"
    if status == "actief":
        rijen = rijen.filter(actief=True)
    elif status == "afgerond":
        rijen = rijen.filter(actief=False)
    soort = argumenten.get("soort")
    if soort:
        geldig = {waarde for waarde, _ in Klus.Soort.choices}
        if soort not in geldig:
            raise Fout(f"soort moet een van {', '.join(sorted(geldig))} zijn.")
        rijen = rijen.filter(soort=soort)
    for woord in str(argumenten.get("zoekterm") or "").split():
        rijen = rijen.filter(
            Q(naam__icontains=woord)
            | Q(opdrachtgever__icontains=woord)
            | Q(adres__icontains=woord)
            | Q(plaats__icontains=woord)
            | Q(beschrijving__icontains=woord)
        )
    plaats = argumenten.get("plaats")
    if plaats:
        rijen = rijen.filter(plaats__icontains=plaats)
    totaal = rijen.count()
    klussen = []
    for k in rijen[:MAX_LIJST]:
        rij = _klus_kort(k)
        rij["startdatum"] = k.startdatum.isoformat() if k.startdatum else None
        rij["afgerond_op"] = k.afgerond_op.isoformat() if k.afgerond_op else None
        klussen.append(rij)
    return {"aantal": totaal, "getoond": len(klussen), "klussen": klussen}


def klus_dossier(argumenten):
    klus = _klus(argumenten.get("klus_id"))
    if klus is None:
        raise Fout("klus_id is verplicht.")
    nu = timezone.localdate()

    blokken = list(Uurblok.objects.filter(klus=klus).select_related("medewerker").order_by("-datum", "-begintijd"))
    per_persoon = defaultdict(int)
    for b in blokken:
        per_persoon[b.medewerker.naam] += b.duur_minuten

    klusdagen = Klusdag.objects.filter(klus=klus)
    ingepland = defaultdict(list)
    for inzet in Inzet.objects.filter(klus=klus, datum__gte=nu).select_related("medewerker"):
        ingepland[inzet.datum].append(inzet.medewerker.naam)
    gepland = sorted({kd.datum for kd in klusdagen.filter(datum__gte=nu)} | set(ingepland))
    notitie_per_dag = {kd.datum: kd.notitie for kd in klusdagen}

    bestanden = klus.bijlagen.select_related("toegevoegd_door", "klus").prefetch_related("zichtbaar_voor")
    notities = klus.notities.select_related("geschreven_door")

    return {
        **_klus_kort(klus),
        "email_opdrachtgever": klus.email,
        "startdatum": klus.startdatum.isoformat() if klus.startdatum else None,
        "afgerond_op": klus.afgerond_op.isoformat() if klus.afgerond_op else None,
        "beschrijving": klus.beschrijving,
        "uren": {
            "totaal": _uren(sum(per_persoon.values())),
            "per_medewerker": {naam: _uren(m) for naam, m in sorted(per_persoon.items())},
            "eerste_dag": blokken[-1].datum.isoformat() if blokken else None,
            "laatste_dag": blokken[0].datum.isoformat() if blokken else None,
            "laatste_uurblokken": [
                {
                    **_dag(b.datum),
                    "medewerker": b.medewerker.naam,
                    "van": _tijd(b.begintijd),
                    "tot": _tijd(b.eindtijd),
                    "uren": _uren(b.duur_minuten),
                    "toelichting": b.toelichting,
                    "extra_werk": b.extra_werk,
                }
                for b in blokken[:20]
            ],
        },
        "planning_vanaf_vandaag": [
            {**_dag(d), "notitie": notitie_per_dag.get(d, ""), "ingepland": ingepland.get(d, [])} for d in gepland
        ],
        "notities": [
            {"geschreven_op": timezone.localtime(n.geschreven_op).strftime("%Y-%m-%d %H:%M"), "door": _naam(n.geschreven_door), "tekst": n.tekst}
            for n in notities[:50]
        ],
        "aantal_bestanden": bestanden.count(),
        "bestanden": [_bestand_kort(b) for b in bestanden[:MAX_LIJST]],
    }


def opdrachtgevers(argumenten):
    zoekterm = str(argumenten.get("zoekterm") or "").casefold()
    minuten_per_klus = defaultdict(int)
    for b in Uurblok.objects.only("klus_id", "datum", "begintijd", "eindtijd"):
        minuten_per_klus[b.klus_id] += b.duur_minuten

    groepen = {}
    for k in Klus.objects.order_by("naam"):
        naam = k.opdrachtgever.strip() or "(geen opdrachtgever ingevuld)"
        groep = groepen.setdefault(
            _sleutel(naam), {"opdrachtgever": naam, "emails": set(), "adressen": set(), "klussen": [], "minuten": 0}
        )
        if k.email:
            groep["emails"].add(k.email)
        adres = ", ".join(deel for deel in (k.adres, k.plaats) if deel)
        if adres:
            groep["adressen"].add(adres)
        groep["klussen"].append({"klus_id": k.pk, "naam": k.naam, "soort": k.get_soort_display(), "status": "actief" if k.actief else "afgerond"})
        groep["minuten"] += minuten_per_klus[k.pk]

    uitkomst = []
    for groep in sorted(groepen.values(), key=lambda g: g["opdrachtgever"].casefold()):
        tekst = " ".join([groep["opdrachtgever"], *groep["adressen"], *groep["emails"], *(k["naam"] for k in groep["klussen"])])
        if zoekterm and zoekterm not in tekst.casefold():
            continue
        uitkomst.append(
            {
                "opdrachtgever": groep["opdrachtgever"],
                "emails": sorted(groep["emails"]),
                "adressen": sorted(groep["adressen"]),
                "uren_totaal": _uren(groep.pop("minuten")),
                "klussen": groep["klussen"],
            }
        )
    return {"aantal": len(uitkomst), "opdrachtgevers": uitkomst}


def medewerkers(argumenten):
    iedereen = Medewerker.objects.all()
    if not argumenten.get("ook_uit_dienst"):
        iedereen = iedereen.exclude(uit_dienst_sinds__lte=timezone.localdate())
    return {
        "medewerkers": [
            {
                "naam": m.naam,
                "gebruikersnaam": m.username,
                "functie": m.functie,
                "rol": m.get_rol_display(),
                "vaste_werkdagen": [DAGNAMEN[d] for d in sorted(m.vaste_werkdagen or [])],
                "in_dienst_sinds": m.in_dienst_sinds.isoformat() if m.in_dienst_sinds else None,
                "uit_dienst_sinds": m.uit_dienst_sinds.isoformat() if m.uit_dienst_sinds else None,
            }
            for m in iedereen
        ]
    }


def uren(argumenten):
    nu = timezone.localdate()
    van, tot = _periode(argumenten, nu - timedelta(days=nu.weekday()), nu, 366)
    rijen = Uurblok.objects.filter(datum__range=(van, tot)).select_related("medewerker", "klus")
    persoon = _medewerkerfilter(argumenten)
    if persoon:
        rijen = rijen.filter(medewerker=persoon)
    klus = _klus(argumenten.get("klus_id"))
    if klus:
        rijen = rijen.filter(klus=klus)
    if argumenten.get("opdrachtgever"):
        rijen = rijen.filter(klus__opdrachtgever__icontains=argumenten["opdrachtgever"])
    for woord in str(argumenten.get("zoekterm") or "").split():
        rijen = rijen.filter(Q(toelichting__icontains=woord) | Q(extra_werk__icontains=woord) | Q(klus__naam__icontains=woord))
    blokken = list(rijen.order_by("datum", "medewerker__first_name", "begintijd"))

    per_persoon = defaultdict(lambda: {"minuten": 0, "dagen": set()})
    per_klus = {}
    for b in blokken:
        p = per_persoon[b.medewerker.naam]
        p["minuten"] += b.duur_minuten
        p["dagen"].add(b.datum)
        k = per_klus.setdefault(b.klus_id, {**_klus_kort(b.klus), "minuten": 0})
        k["minuten"] += b.duur_minuten

    return {
        "van": van.isoformat(),
        "tot": tot.isoformat(),
        "totaal_uren": _uren(sum(b.duur_minuten for b in blokken)),
        "per_medewerker": [
            {"medewerker": naam, "uren": _uren(p["minuten"]), "dagen_gewerkt": len(p["dagen"])}
            for naam, p in sorted(per_persoon.items())
        ],
        "per_klus": [
            {**{k: v for k, v in rij.items() if k != "minuten"}, "uren": _uren(rij["minuten"])}
            for rij in sorted(per_klus.values(), key=lambda r: -r["minuten"])
        ],
        "aantal_uurblokken": len(blokken),
        "afgekapt": len(blokken) > MAX_UURBLOKKEN,
        "uurblokken": [
            {
                **_dag(b.datum),
                "medewerker": b.medewerker.naam,
                "klus_id": b.klus_id,
                "klus": b.klus.naam,
                "van": _tijd(b.begintijd),
                "tot": _tijd(b.eindtijd),
                "uren": _uren(b.duur_minuten),
                "toelichting": b.toelichting,
                "extra_werk": b.extra_werk,
            }
            for b in blokken[:MAX_UURBLOKKEN]
        ],
    }


def werkplanning(argumenten):
    nu = timezone.localdate()
    van, tot = _periode(argumenten, nu, nu + timedelta(days=13), 93)
    persoon = _medewerkerfilter(argumenten)
    klus = _klus(argumenten.get("klus_id"))

    klusdagen = Klusdag.objects.filter(datum__range=(van, tot)).select_related("klus")
    inzet = Inzet.objects.filter(datum__range=(van, tot)).select_related("klus", "medewerker")
    if klus:
        klusdagen = klusdagen.filter(klus=klus)
        inzet = inzet.filter(klus=klus)
    if persoon:
        inzet = inzet.filter(medewerker=persoon)

    per_dag = defaultdict(dict)
    if not persoon:
        for kd in klusdagen:
            per_dag[kd.datum][kd.klus_id] = {**_klus_kort(kd.klus), "notitie": kd.notitie, "ingepland": []}
    for i in inzet:
        rij = per_dag[i.datum].setdefault(i.klus_id, {**_klus_kort(i.klus), "notitie": "", "ingepland": []})
        rij["ingepland"].append(i.medewerker.naam)
    if persoon:
        for kd in klusdagen.filter(datum__in=list(per_dag)):
            if kd.klus_id in per_dag[kd.datum]:
                per_dag[kd.datum][kd.klus_id]["notitie"] = kd.notitie

    notities = {d.datum: d.tekst for d in Dagnotitie.objects.filter(datum__range=(van, tot))}
    feest = bezetting.nederlandse_feestdagen_tussen(van, tot)
    dagen = []
    d = van
    while d <= tot:
        if per_dag.get(d) or d in notities or d in feest:
            dagen.append(
                {
                    **_dag(d),
                    "feestdag": feest[d][0] if d in feest else "",
                    "dagnotitie": notities.get(d, ""),
                    "klussen": list(per_dag.get(d, {}).values()),
                }
            )
        d += timedelta(days=1)
    return {
        "van": van.isoformat(),
        "tot": tot.isoformat(),
        "medewerker": persoon.naam if persoon else None,
        "uitleg": "Alleen dagen waarop iets gepland staat. 'ingepland' = wie er die dag heen gaat.",
        "dagen": dagen,
    }


def aanwezigheid(argumenten):
    nu = timezone.localdate()
    maandag = nu - timedelta(days=nu.weekday())
    van, tot = _periode(argumenten, maandag, maandag + timedelta(days=6), 62)
    persoon = _medewerkerfilter(argumenten)
    mensen = [persoon] if persoon else bezetting.medewerkers_tussen(van, tot)
    dagen = [van + timedelta(days=i) for i in range((tot - van).days + 1)]
    cellen = bezetting.rooster(mensen, dagen)

    uitkomst = []
    for m in mensen:
        telling = defaultdict(int)
        regels = []
        for d in dagen:
            c = cellen[(m.pk, d)]
            if c.stand in (bezetting.VRIJ, bezetting.BUITEN):
                continue
            telling[c.stand] += 1
            regel = {**_dag(d), "stand": c.stand}
            if c.reden_tekst:
                regel["reden"] = c.reden_tekst
            if c.opmerking:
                regel["opmerking"] = c.opmerking
            if c.klussen:
                regel["klussen"] = [k.naam for k in c.klussen]
            regels.append(regel)
        uitkomst.append({"medewerker": m.naam, "telling": dict(telling), "dagen": regels})
    return {
        "van": van.isoformat(),
        "tot": tot.isoformat(),
        "uitleg": (
            "stand: aanwezig (zo gezet of ingepland op een klus), afwezig (vakantie, ziek, vrij, "
            "feestdag), onbekend (werkdag volgens rooster, nog niets ingevuld). Dagen waarop iemand "
            "volgens rooster niet werkt of niet in dienst is, staan er niet bij."
        ),
        "medewerkers": uitkomst,
    }


def zoek_notities(argumenten):
    rijen = Notitie.objects.select_related("klus", "geschreven_door")
    klus = _klus(argumenten.get("klus_id"))
    if klus:
        rijen = rijen.filter(klus=klus)
    for woord in str(argumenten.get("zoekterm") or "").split():
        rijen = rijen.filter(Q(tekst__icontains=woord) | Q(klus__naam__icontains=woord) | Q(klus__opdrachtgever__icontains=woord))
    if argumenten.get("van") or argumenten.get("tot"):
        van = _datum(argumenten.get("van"), date.min, "van")
        tot = _datum(argumenten.get("tot"), date.max, "tot")
        rijen = rijen.filter(geschreven_op__date__range=(van, tot))
    totaal = rijen.count()
    return {
        "aantal": totaal,
        "getoond": min(totaal, MAX_LIJST),
        "notities": [
            {
                "geschreven_op": timezone.localtime(n.geschreven_op).strftime("%Y-%m-%d %H:%M"),
                "door": _naam(n.geschreven_door),
                "klus_id": n.klus_id,
                "klus": n.klus.naam,
                "tekst": n.tekst,
            }
            for n in rijen[:MAX_LIJST]
        ],
    }


def zoek_bestanden(argumenten):
    rijen = Bijlage.objects.select_related("klus", "toegevoegd_door").prefetch_related("zichtbaar_voor")
    klus = _klus(argumenten.get("klus_id"))
    if klus:
        rijen = rijen.filter(klus=klus)
    if argumenten.get("alleen_algemeen"):
        rijen = rijen.filter(klus__isnull=True)
    soort = argumenten.get("soort")
    if soort in ("foto", "document"):
        rijen = rijen.filter(soort=soort)
    for woord in str(argumenten.get("zoekterm") or "").split():
        rijen = rijen.filter(
            Q(originele_naam__icontains=woord) | Q(toelichting__icontains=woord) | Q(klus__naam__icontains=woord)
        )
    if argumenten.get("van") or argumenten.get("tot"):
        van = _datum(argumenten.get("van"), date.min, "van")
        tot = _datum(argumenten.get("tot"), date.max, "tot")
        rijen = rijen.filter(datum__range=(van, tot))
    totaal = rijen.count()
    return {"aantal": totaal, "getoond": min(totaal, MAX_LIJST), "bestanden": [_bestand_kort(b) for b in rijen[:MAX_LIJST]]}


# ── een bestand openen ────────────────────────────────────────────────────

# Groot genoeg om een tekening te lezen, klein genoeg dat een antwoord niet
# megabytes wordt. Claude verkleint zelf ook tot ongeveer deze maat.
BEELD_ZIJDE = 1568
MAX_TEKST = 60_000
MAX_PDF_PAGINAS = 40
MAX_RIJEN = 300


def _als_beeld(gegevens):
    from PIL import Image, ImageOps

    with Image.open(io.BytesIO(gegevens)) as plaatje:
        plaatje = ImageOps.exif_transpose(plaatje).convert("RGB")
        plaatje.thumbnail((BEELD_ZIJDE, BEELD_ZIJDE))
        uit = io.BytesIO()
        plaatje.save(uit, "JPEG", quality=80)
    return {"type": "image", "data": base64.b64encode(uit.getvalue()).decode(), "mimeType": "image/jpeg"}


def _kap(tekst):
    if len(tekst) > MAX_TEKST:
        return tekst[:MAX_TEKST] + f"\n\n[… afgekapt, het bestand is langer dan {MAX_TEKST} tekens]"
    return tekst


def _pdf(gegevens):
    import pymupdf

    blokken = []
    with pymupdf.open(stream=gegevens, filetype="pdf") as pdf:
        delen = [f"--- pagina {i + 1} ---\n{pdf[i].get_text()}" for i in range(min(len(pdf), MAX_PDF_PAGINAS))]
        tekst = "\n".join(delen)
        if len(pdf) > MAX_PDF_PAGINAS:
            tekst += f"\n\n[… alleen de eerste {MAX_PDF_PAGINAS} van {len(pdf)} pagina's]"
        if len(tekst.split()) < 20 * min(len(pdf), 3):
            # Een scan of een tekening: weinig tekst, dus kijken in plaats van lezen.
            for i in range(min(len(pdf), 3)):
                blokken.append(_als_beeld(pdf[i].get_pixmap(dpi=110).tobytes("png")))
    return [{"type": "text", "text": _kap(tekst)}] + blokken


def _xlsx(gegevens):
    from openpyxl import load_workbook

    boek = load_workbook(io.BytesIO(gegevens), read_only=True, data_only=True)
    delen = []
    for blad in boek.worksheets:
        regels = []
        for n, rij in enumerate(blad.iter_rows(values_only=True)):
            if n >= MAX_RIJEN:
                regels.append(f"[… meer rijen dan {MAX_RIJEN}]")
                break
            if any(cel not in (None, "") for cel in rij):
                regels.append("\t".join("" if cel is None else str(cel) for cel in rij).rstrip())
        delen.append(f"--- blad {blad.title} ---\n" + "\n".join(regels))
    boek.close()
    return [{"type": "text", "text": _kap("\n\n".join(delen))}]


def _docx(gegevens):
    w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(io.BytesIO(gegevens)) as archief:
        boom = ElementTree.fromstring(archief.read("word/document.xml"))
    alineas = ["".join(t.text or "" for t in p.iter(f"{w}t")) for p in boom.iter(f"{w}p")]
    return [{"type": "text", "text": _kap("\n".join(alineas))}]


def bekijk_bestand(argumenten):
    """Geeft MCP-inhoudsblokken terug in plaats van een dict."""
    try:
        bijlage = Bijlage.objects.select_related("klus", "toegevoegd_door").get(pk=int(argumenten.get("bestand_id")))
    except (ValueError, TypeError, Bijlage.DoesNotExist):
        raise Fout("Er is geen bestand met dit id. Zoek het op met zoek_bestanden of klus_dossier.")
    kop = {"type": "text", "text": json.dumps(_bestand_kort(bijlage), ensure_ascii=False, indent=1)}
    naam = (bijlage.originele_naam or bijlage.bestand.name).lower()
    try:
        with bijlage.bestand.open("rb") as f:
            gegevens = f.read()
    except OSError:
        raise Fout("Het bestand staat niet (meer) op de server.")

    try:
        if bijlage.weergave == "foto":
            return [kop, _als_beeld(gegevens)]
        if naam.endswith(".pdf"):
            return [kop, *_pdf(gegevens)]
        if naam.endswith((".xlsx", ".xlsm")):
            return [kop, *_xlsx(gegevens)]
        if naam.endswith(".docx"):
            return [kop, *_docx(gegevens)]
        if naam.endswith((".txt", ".csv", ".md")):
            return [kop, {"type": "text", "text": _kap(gegevens.decode("utf-8", errors="replace"))}]
    except Exception:  # noqa: BLE001 — een kapot bestand mag de koppeling niet omgooien
        raise Fout("Dit bestand kon niet worden gelezen; het is mogelijk beschadigd.")
    raise Fout(f"De inhoud van een {bijlage.extensie or 'onbekend'}-bestand kan Claude niet lezen; alleen de gegevens hierboven.")


# ── de lijst die Claude te zien krijgt ────────────────────────────────────

_PERIODE = {
    "van": {"type": "string", "description": "Begindatum, JJJJ-MM-DD."},
    "tot": {"type": "string", "description": "Einddatum (inclusief), JJJJ-MM-DD."},
}
_MEDEWERKER = {"type": "string", "description": "Naam van de medewerker (voornaam is genoeg)."}
_KLUS_ID = {"type": "integer", "description": "Id van de klus, uit zoek_klussen."}


def _schema(**velden):
    return {"type": "object", "properties": velden, "additionalProperties": False}


TOOLS = [
    {
        "name": "vandaag",
        "title": "Datum van vandaag",
        "description": "De datum, dag en het weeknummer van vandaag in Nederland. Gebruik dit om 'gisteren', 'vorige week' of 'deze maand' om te rekenen naar datums.",
        "inputSchema": _schema(),
        "functie": vandaag,
    },
    {
        "name": "zoek_klussen",
        "title": "Klussen zoeken",
        "description": "Zoek klussen op naam, opdrachtgever, adres, plaats of beschrijving. Geeft per klus het klus_id voor de andere tools.",
        "inputSchema": _schema(
            zoekterm={"type": "string", "description": "Woorden die in naam, opdrachtgever, adres, plaats of beschrijving staan."},
            plaats={"type": "string", "description": "Alleen klussen in deze plaats, bv. Leiden."},
            soort={"type": "string", "enum": ["aanleg", "onderhoud", "van_ee"]},
            status={"type": "string", "enum": ["actief", "afgerond", "alle"], "description": "Standaard alle."},
        ),
        "functie": zoek_klussen,
    },
    {
        "name": "klus_dossier",
        "title": "Klusdossier",
        "description": "Alles van één klus: gegevens, opdrachtgever, uren (totaal en per medewerker, laatste uurblokken), planning vanaf vandaag, notities en de lijst bestanden.",
        "inputSchema": {**_schema(klus_id=_KLUS_ID), "required": ["klus_id"]},
        "functie": klus_dossier,
    },
    {
        "name": "opdrachtgevers",
        "title": "Opdrachtgevers",
        "description": "Alle opdrachtgevers met hun e-mail, adressen, klussen en totaal geschreven uren.",
        "inputSchema": _schema(zoekterm={"type": "string", "description": "Deel van naam, adres of e-mail."}),
        "functie": opdrachtgevers,
    },
    {
        "name": "medewerkers",
        "title": "Medewerkers",
        "description": "Wie er in dienst is: naam, functie, rol en vaste werkdagen.",
        "inputSchema": _schema(ook_uit_dienst={"type": "boolean", "description": "Ook wie uit dienst is."}),
        "functie": medewerkers,
    },
    {
        "name": "uren",
        "title": "Geschreven uren",
        "description": "Gewerkte uren in een periode, met totalen per medewerker en per klus en de losse uurblokken (wie, waar, van-tot, toelichting, extra werk). Zonder periode: deze week tot en met vandaag. Maximaal een jaar.",
        "inputSchema": _schema(
            **_PERIODE,
            medewerker=_MEDEWERKER,
            klus_id=_KLUS_ID,
            opdrachtgever={"type": "string", "description": "Deel van de naam van de opdrachtgever."},
            zoekterm={"type": "string", "description": "Woorden in toelichting of extra werk."},
        ),
        "functie": uren,
    },
    {
        "name": "werkplanning",
        "title": "Werkplanning",
        "description": "Wat er gepland staat: per dag de klussen, wie er ingepland is, notities bij de dag en feestdagen. Zonder periode: vandaag en de komende twee weken. Maximaal 93 dagen.",
        "inputSchema": _schema(**_PERIODE, medewerker=_MEDEWERKER, klus_id=_KLUS_ID),
        "functie": werkplanning,
    },
    {
        "name": "aanwezigheid",
        "title": "Aanwezigheid",
        "description": "Wie er per dag aanwezig of afwezig is (vakantie, ziek, vrij, feestdag), volgens rooster en wat de eigenaar heeft ingevuld. Zonder periode: deze week. Maximaal 62 dagen.",
        "inputSchema": _schema(**_PERIODE, medewerker=_MEDEWERKER),
        "functie": aanwezigheid,
    },
    {
        "name": "zoek_notities",
        "title": "Notities zoeken",
        "description": "Zoek in de notities van klusdossiers ('hek staat open, sleutel bij de buren').",
        "inputSchema": _schema(zoekterm={"type": "string"}, klus_id=_KLUS_ID, **_PERIODE),
        "functie": zoek_notities,
    },
    {
        "name": "zoek_bestanden",
        "title": "Foto's en documenten zoeken",
        "description": "Zoek foto's en documenten op naam, toelichting, klus of datum. Geeft per bestand het bestand_id voor bekijk_bestand.",
        "inputSchema": _schema(
            zoekterm={"type": "string"},
            klus_id=_KLUS_ID,
            soort={"type": "string", "enum": ["foto", "document"]},
            alleen_algemeen={"type": "boolean", "description": "Alleen bestanden die niet aan een klus hangen (de fotodropbox)."},
            **_PERIODE,
        ),
        "functie": zoek_bestanden,
    },
    {
        "name": "bekijk_bestand",
        "title": "Bestand bekijken",
        "description": "Open één foto of document: een foto als afbeelding, een pdf, Word- of Excel-bestand als tekst (een gescande pdf als afbeelding).",
        "inputSchema": {**_schema(bestand_id={"type": "integer"}), "required": ["bestand_id"]},
        "functie": bekijk_bestand,
    },
]

for _tool in TOOLS:
    _tool["annotations"] = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}

PER_NAAM = {tool["name"]: tool for tool in TOOLS}
