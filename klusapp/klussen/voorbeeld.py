"""De gewaaierde inhoudspreview van een klus: een handvol foto's/documenten
plus eventueel de klusnotitie, gebruikt op zowel het foto's-scherm
(klussen/views.py:fotos) als de klussenslider op het startscherm
(medewerkers/views.py:start) — vandaar een eigen module in plaats van de een
of de ander te laten importeren uit views.py."""


def items_voor_stapel(klus, cap=3):
    """Tot `cap` stukjes inhoud voor de gewaaierde stapel op een klustegel.

    Eerst de nieuwste foto's/documenten (uit de al-geprefetchte
    `voorbeeld_bijlagen`, nieuw->oud); is er nog ruimte binnen de cap, dan de
    notitie (klus.beschrijving) als achterste laag — een notitie verdringt
    dus nooit al aanwezige foto's/documenten.

    Geeft (items, aantal_meer) terug. `items` staat achter-naar-voor: het
    eerste item is de achterste laag, het laatste de voorste — zo loopt de
    template 'm door met forloop.revcounter voor de laagklasse.
    """
    media = klus.voorbeeld_bijlagen
    heeft_notitie = bool(klus.beschrijving.strip())
    ruimte_voor_media = cap - (1 if heeft_notitie else 0)
    getoonde_media = media[:ruimte_voor_media]
    items = list(reversed(getoonde_media))  # oud -> nieuw, dus nieuwste laatst (voorste)
    if heeft_notitie:
        items.insert(0, {"soort": "notitie", "tekst": klus.beschrijving})
    totaal = len(media) + (1 if heeft_notitie else 0)
    return items, totaal - len(items)
