"""De ideeënbus: lijst, insturen, liken, en voor de eigenaar de stand."""

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Count, Exists, OuterRef
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from medewerkers.rechten import alleen_eigenaar

from .models import Idee, Like

DUBBEL_BINNEN = timedelta(seconds=30)
MAX_LENGTE = Idee._meta.get_field("tekst").max_length


@login_required
@require_GET
def ideeen(request):
    """Nieuwste eerst, of ?op=likes: meeste likes eerst."""
    volgorde = "likes" if request.GET.get("op") == "likes" else "nieuw"
    lijst = Idee.objects.select_related("door").annotate(
        aantal_likes=Count("likes"),
        door_mij_geliket=Exists(Like.objects.filter(idee=OuterRef("pk"), medewerker=request.user)),
    )
    lijst = lijst.order_by("-aantal_likes", "-gemaakt_op") if volgorde == "likes" else lijst.order_by("-gemaakt_op")
    return render(
        request,
        "ideeen/ideeen.html",
        {"ideeen": lijst, "volgorde": volgorde, "standen": Idee.Stand.choices, "max_lengte": MAX_LENGTE},
    )


@login_required
@require_POST
def idee_nieuw(request):
    tekst = request.POST.get("tekst", "").strip()
    anoniem = request.POST.get("anoniem") == "1"
    if not tekst:
        messages.error(request, "Typ eerst je idee.")
    elif len(tekst) > MAX_LENGTE:
        messages.error(request, f"Een idee mag hooguit {MAX_LENGTE} tekens zijn.")
    else:
        with transaction.atomic():
            request.user.vergrendel()
            # Dubbel tikken op Insturen. Bij anoniem kunnen we dat niet aan
            # jou koppelen; dan op tekst alleen.
            dubbel = Idee.objects.filter(tekst=tekst, gemaakt_op__gte=timezone.now() - DUBBEL_BINNEN)
            if not anoniem:
                dubbel = dubbel.filter(door=request.user)
            if not dubbel.exists():
                Idee.objects.create(tekst=tekst, door=None if anoniem else request.user)
                messages.success(request, "Je idee staat erin. Dank je!")
    return redirect("ideeen")


@login_required
@require_POST
def idee_like(request, pk):
    """Like aan of uit. Je eigen idee liken mag ook, net als overal."""
    idee = get_object_or_404(Idee, pk=pk)
    bestaand = Like.objects.filter(idee=idee, medewerker=request.user)
    if bestaand.exists():
        bestaand.delete()
        geliket = False
    else:
        try:
            with transaction.atomic():
                Like.objects.create(idee=idee, medewerker=request.user)
        except IntegrityError:  # twee tikken tegelijk
            pass
        geliket = True
    if request.headers.get("X-Idee") == "1":
        return JsonResponse({"geliket": geliket, "aantal": idee.likes.count()})
    return redirect(reverse("ideeen") + f"#idee-{idee.pk}")


@alleen_eigenaar
@require_POST
def idee_stand(request, pk):
    idee = get_object_or_404(Idee, pk=pk)
    stand = request.POST.get("stand", "")
    if stand in Idee.Stand.values:
        idee.stand = stand
    idee.reactie = request.POST.get("reactie", "").strip()[:300]
    idee.save(update_fields=["stand", "reactie"])
    return redirect(reverse("ideeen") + f"#idee-{idee.pk}")


@login_required
@require_POST
def idee_verwijderen(request, pk):
    idee = get_object_or_404(Idee, pk=pk)
    if not idee.mag_verwijderen(request.user):
        raise Http404
    idee.delete()
    messages.success(request, "Idee weggehaald.")
    return redirect("ideeen")
