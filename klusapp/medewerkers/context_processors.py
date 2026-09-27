from .models import Medewerker
from .tegels import zichtbare_tegels


def tegels(request):
    """Navigatie-tegels op elke pagina, niet alleen het startscherm — de
    zijbalk in basis.html staat op elk scherm dat er van erft."""
    if not request.user.is_authenticated:
        return {}
    return {"tegels": zichtbare_tegels(request.user)}


def wissel(request):
    """TIJDELIJK: wie je eigenlijk bent als je als medewerker meekijkt, zodat
    basis.html op elk scherm de terugknop kan tonen. Zie views.wissel_naar."""
    if not request.user.is_authenticated:
        return {}
    eigen_pk = request.session.get("gewisseld_van")
    if not eigen_pk:
        return {}
    return {"gewisseld_van": Medewerker.objects.filter(pk=eigen_pk).first()}
