"""TIJDELIJK — nepmedewerkers met uren, om schermen te kunnen beoordelen.

Bestaat omdat een leeg planbord niets zegt: je ziet pas of een scherm werkt
als er zes mensen in een week doorheen lopen. Alles wat hier wordt aangemaakt
is herkenbaar aan het voorvoegsel in de gebruikersnaam en met één knop weer
weg te halen.

Weghalen als het niet meer nodig is: dit bestand, de twee views in
medewerkers/views.py, de routes in medewerkers/urls.py en het blok onderaan
templates/menu.html.
"""

import random
from datetime import date, time, timedelta

from klussen.models import Klus
from uren.models import Uurblok

from .models import Medewerker

# Alles wat de knop aanmaakt begint hiermee, zodat opruimen precies weet wat
# van de test is en wat van de klant.
VOORVOEGSEL = "demo-"

PLOEG = [
    ("Tom", "Verhoef", "Voorman", "#95BF1D"),
    ("Joep", "Bakker", "Hovenier", "#5B8FA8"),
    ("Youssef", "el Amrani", "Hovenier", "#E07B5F"),
    ("Nick", "Molenaar", "Machinist", "#C9A227"),
    ("Wesley", "de Jong", "Leerling", "#7FA88F"),
]

WERKZAAMHEDEN = [
    "Bestrating uitgevlakt", "Beplanting gezet", "Snoeiwerk achtertuin",
    "Grond afgevoerd", "Vijverfolie gelegd", "Onderhoudsronde", "Haag geknipt",
    "Terras aangelegd", "Gazon ingezaaid",
]


def week_van(dag):
    maandag = dag - timedelta(days=dag.weekday())
    return maandag, maandag + timedelta(days=6)


def _klussen():
    """Bestaande klussen gebruiken; alleen als er nog geen zijn er drie maken."""
    bestaand = list(Klus.objects.filter(actief=True))
    if bestaand:
        return bestaand
    return [
        Klus.objects.create(naam="Tuin Vermeer", soort=Klus.Soort.AANLEG, plaats="Maasdijk"),
        Klus.objects.create(naam="Nieuwbouw Van Dijk", soort=Klus.Soort.AANLEG, plaats="Naaldwijk"),
        Klus.objects.create(naam="Onderhoud vaste klanten", soort=Klus.Soort.ONDERHOUD),
    ]


def aanmaken(dag_in_week):
    """Vijf medewerkers met uren over de week waar `dag_in_week` in valt.

    Draai je het twee keer voor dezelfde week, dan komen de uren niet dubbel:
    die van die week worden eerst weggehaald.
    """
    maandag, zondag = week_van(dag_in_week)
    klussen = _klussen()
    # Vaste toevalsreeks per week: opnieuw draaien geeft hetzelfde beeld,
    # zodat je een wijziging aan een scherm beoordeelt en niet nieuwe data.
    dobbel = random.Random(maandag.toordinal())

    mensen = []
    for voornaam, achternaam, functie, kleur in PLOEG:
        mw, _ = Medewerker.objects.get_or_create(
            username=f"{VOORVOEGSEL}{voornaam.lower()}",
            defaults={"rol": Medewerker.Rol.MEDEWERKER},
        )
        mw.first_name, mw.last_name, mw.functie, mw.kleur = voornaam, achternaam, functie, kleur
        mw.rol = Medewerker.Rol.MEDEWERKER
        mw.set_unusable_password()   # testaccounts horen niet te kunnen inloggen
        mw.save()
        mensen.append(mw)

    Uurblok.objects.filter(medewerker__in=mensen, datum__range=(maandag, zondag)).delete()

    blokken = 0
    for mw in mensen:
        for nummer in range(5):                      # maandag tot en met vrijdag
            dag = maandag + timedelta(days=nummer)
            if dobbel.random() < 0.12:               # af en toe een vrije dag
                continue
            begin = dobbel.choice([time(7, 0), time(7, 30), time(8, 0)])
            if dobbel.random() < 0.35:
                # onderhoudsdag: twee adressen achter elkaar
                middag = time(12, 30)
                paren = [(begin, middag), (time(13, 0), dobbel.choice([time(16, 0), time(16, 30)]))]
            else:
                paren = [(begin, dobbel.choice([time(15, 30), time(16, 0), time(16, 30), time(17, 0)]))]
            for van, tot in paren:
                Uurblok.objects.create(
                    medewerker=mw,
                    klus=dobbel.choice(klussen),
                    datum=dag,
                    begintijd=van,
                    eindtijd=tot,
                    toelichting=dobbel.choice(WERKZAAMHEDEN),
                )
                blokken += 1
    return len(mensen), blokken


def opruimen():
    """Alles weghalen wat de knop heeft aangemaakt."""
    mensen = Medewerker.objects.filter(username__startswith=VOORVOEGSEL)
    aantal = mensen.count()
    # Uurblok.medewerker staat op PROTECT, dus eerst de uren.
    Uurblok.objects.filter(medewerker__in=mensen).delete()
    mensen.delete()
    return aantal
