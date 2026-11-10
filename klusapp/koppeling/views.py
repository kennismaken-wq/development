"""Het scherm Koppeling met Claude: uitleg, het adres om te plakken, en wie er
gekoppeld is, met een knop om dat in te trekken. Alleen voor de eigenaar."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from medewerkers.rechten import alleen_eigenaar

from .models import Koppeling
from .oauth import resource_url


@alleen_eigenaar
def koppelingen(request):
    return render(
        request,
        "koppeling/koppelingen.html",
        {
            "adres": resource_url(request),
            # Van alle eigenaren: Maarten moet ook een koppeling kunnen
            # intrekken die een andere eigenaar ooit maakte.
            "koppelingen": Koppeling.objects.actief().select_related("medewerker", "client"),
        },
    )


@require_POST
@alleen_eigenaar
def intrekken(request, pk):
    koppeling = get_object_or_404(Koppeling.objects.actief(), pk=pk)
    koppeling.ingetrokken_op = timezone.now()
    koppeling.save(update_fields=["ingetrokken_op"])
    messages.success(request, "De koppeling is ingetrokken. Claude kan vanaf nu niets meer lezen.")
    return redirect("claude_koppeling")
