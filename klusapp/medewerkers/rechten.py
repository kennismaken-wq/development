"""Rechtencontroles die op meer dan één plek nodig zijn."""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import Http404


def alleen_eigenaar(view):
    """Schermen waar alleen de eigenaar bij mag: klussen aanmaken, planbord,
    aanwezigheid, export.

    Geeft bewust een 404 en geen 403: een medewerker hoeft niet te weten dat
    het scherm bestaat. Dat is ook hoe de uurblokken het doen — een blok van
    een ander bestaat voor jou niet.
    """

    @wraps(view)
    @login_required
    def binnen(request, *args, **kwargs):
        if not request.user.is_eigenaar:
            raise Http404
        return view(request, *args, **kwargs)

    return binnen
