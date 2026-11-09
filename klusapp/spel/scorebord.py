"""Het scorebord van het springspel."""

from uren.kalender import medewerker_kleur_van

from .models import BesteScore


def ranglijst():
    """Iedereen die nu in dienst is, hoogste score eerst; bij gelijke stand
    staat wie het eerst zo hoog kwam bovenaan."""
    return (
        BesteScore.objects.filter(
            medewerker__is_active=True,
            medewerker__uit_dienst_sinds__isnull=True,
            medewerker__verborgen=False,
        )
        .select_related("medewerker")
        .order_by("-punten", "behaald_op")
    )


def vlaggen(gebruiker):
    """De vlaggetjes in het spel: op welke hoogte elke collega zit, en jij."""
    return [
        {
            "naam": rij.medewerker.first_name or rij.medewerker.naam,
            "punten": rij.punten,
            "kleur": medewerker_kleur_van(rij.medewerker),
            "ik": rij.medewerker_id == gebruiker.pk,
        }
        for rij in ranglijst()
    ]
