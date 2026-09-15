"""Lijniconen voor de navigatie-zijbalk.

Zelfde tekenstijl als de knoppen die net bij de fotodropbox zijn toegevoegd
(zie templates/klussen/_fotoraster.html): 24x24 viewBox, stroke="currentColor",
stroke-width 1.8, ronde lijnuiteinden. Hier alleen de binnenkant van de
<svg> — de buitenkant staat één keer in templates/_icoon.html.

Handgeschreven, statische strings zonder gebruikersinvoer — veilig om als
mark_safe in een template te zetten (zie templatetags/pictogrammen.py).
"""

PICTOGRAMMEN = {
    "start": (
        '<path d="M4 11.5L12 4l8 7.5"/>'
        '<path d="M6 10v9a1 1 0 0 0 1 1h3v-5h4v5h3a1 1 0 0 0 1-1v-9"/>'
    ),
    "uren": (
        '<circle cx="12" cy="12" r="9"/>'
        '<line x1="12" y1="12" x2="12" y2="7"/>'
        '<line x1="12" y1="12" x2="15.5" y2="14"/>'
    ),
    "klussen": (
        '<rect x="3" y="7" width="18" height="12" rx="2"/>'
        '<path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>'
        '<line x1="3" y1="12" x2="21" y2="12"/>'
    ),
    "overzicht": (
        '<line x1="4" y1="6" x2="20" y2="6"/>'
        '<line x1="4" y1="12" x2="16" y2="12"/>'
        '<line x1="4" y1="18" x2="12" y2="18"/>'
    ),
    "planbord": (
        '<rect x="3" y="4" width="5" height="16" rx="1.5"/>'
        '<rect x="9.5" y="4" width="5" height="10" rx="1.5"/>'
        '<rect x="16" y="4" width="5" height="13" rx="1.5"/>'
    ),
    "export": (
        '<line x1="5" y1="20" x2="5" y2="10"/>'
        '<line x1="12" y1="20" x2="12" y2="4"/>'
        '<line x1="19" y1="20" x2="19" y2="14"/>'
        '<line x1="3" y1="20" x2="21" y2="20"/>'
    ),
    "aanwezigheid": (
        '<circle cx="12" cy="12" r="9"/>'
        '<path d="M8 12.5l2.5 2.5L16 9.5"/>'
    ),
    "fotos": (
        '<rect x="3" y="4" width="18" height="16" rx="2.5"/>'
        '<circle cx="8.5" cy="9.5" r="1.7"/>'
        '<path d="M4 17l5-5 3 3 3-3.5 5 5.5"/>'
    ),
    "loonstrook": (
        '<circle cx="12" cy="12" r="9"/>'
        '<path d="M15 8.7c-.7-.6-1.6-1-2.7-1-2.2 0-4 1.9-4 4.3s1.8 4.3 4 4.3c1.1 0 2-.4 2.7-1"/>'
        '<line x1="7.5" y1="11" x2="13.5" y2="11"/>'
        '<line x1="7.5" y1="13.3" x2="13.5" y2="13.3"/>'
    ),
    "beheer": (
        '<circle cx="12" cy="12" r="2.8"/>'
        '<path d="M12 3.5v2.3M12 18.2v2.3M20.5 12h-2.3M5.8 12H3.5'
        'M17.8 6.2l-1.6 1.6M7.8 16.2l-1.6 1.6M17.8 17.8l-1.6-1.6M7.8 7.8L6.2 6.2"/>'
    ),
    "meer": (
        '<circle cx="6" cy="12" r="1.6"/>'
        '<circle cx="12" cy="12" r="1.6"/>'
        '<circle cx="18" cy="12" r="1.6"/>'
    ),
}
