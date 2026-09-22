"""Wat het aanmaakformulier al weet over de opdrachtgevers die er zijn.

Waarom dit bestaat: het adres hoort bij de klus en niet bij de opdrachtgever.
Bij een particulier vallen die samen, maar een VvE of een gemeente heeft één
naam en meerdere terreinen, elk met eigen uren en eigen foto's. Zou het adres
een eigenschap van de klant zijn, dan moet het datamodel bij de eerste VvE
weer open.

Dus: het adres blijft op `Klus` staan, en het formulier *stelt voor* wat het al
weet in plaats van iets over te erven. Deze module levert die kennis —
opdrachtgevers, hun bekende adressen, en welke klussen daar al staan — als een
structuur die zo naar JSON kan en verder door static/js/klusformulier.js wordt
gebruikt. Eén blok in de pagina, dus geen tweede verzoek en geen HTMX.

De structuur is nadrukkelijk plat: zodra er in fase 2 een echt klantbestand
komt (SPEC §3: contracttype en factuurperiode), wordt elke naam hier één rij in
een datamigratie. Tot die tijd houdt de suggestielijst de spelling consistent,
en dat is precies wat die migratie later makkelijk maakt.
"""

from .models import Klus


def _sleutel(tekst):
    """Vergelijken zonder op spelling te struikelen: "Fam. Vermeer" en
    "fam.  vermeer " zijn dezelfde opdrachtgever."""
    return " ".join(tekst.split()).casefold()


def bekende_opdrachtgevers(uitgezonderd=None):
    """Alle opdrachtgevers met hun adressen en de klussen die daar al staan.

    `uitgezonderd` is de klus die op dit moment bewerkt wordt: die moet niet in
    zijn eigen lijst opduiken, anders waarschuwt het formulier over zichzelf.

    Geeft een lijst van dicts (op naam gesorteerd, hoofdletterongevoelig):

        [{"naam": "Fam. Vermeer",
          "adressen": [{"adres": "Dijkweg 12", "plaats": "Maasdijk",
                        "klussen": [{"naam": ..., "soort": ..., "url": ...,
                                     "actief": True}]}]}]

    Een klus zonder adres levert één "adres" met twee lege strings op. Dat is
    bewust geen speciaal geval: het formulier kan er dan nog steeds op
    waarschuwen dat er al iets van deze opdrachtgever bestaat.
    """
    rijen = Klus.objects.exclude(opdrachtgever="").order_by("naam")
    if uitgezonderd is not None and uitgezonderd.pk:
        rijen = rijen.exclude(pk=uitgezonderd.pk)

    verzameld = {}
    for klus in rijen:
        # De eerst gevonden spelling van de naam wint en wordt de suggestie;
        # latere varianten schuiven hun adressen bij dezelfde opdrachtgever in.
        groep = verzameld.setdefault(
            _sleutel(klus.opdrachtgever), {"naam": klus.opdrachtgever.strip(), "adressen": {}}
        )
        adres = groep["adressen"].setdefault(
            (_sleutel(klus.adres), _sleutel(klus.plaats)),
            {"adres": klus.adres.strip(), "plaats": klus.plaats.strip(), "klussen": []},
        )
        adres["klussen"].append(
            {
                "naam": klus.naam,
                "soort": klus.get_soort_display(),
                "url": klus.get_absolute_url(),
                "actief": klus.actief,
            }
        )

    return sorted(
        (
            {"naam": groep["naam"], "adressen": list(groep["adressen"].values())}
            for groep in verzameld.values()
        ),
        key=lambda groep: groep["naam"].casefold(),
    )
