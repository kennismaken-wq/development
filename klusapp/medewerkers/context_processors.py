from .tegels import zichtbare_tegels


def tegels(request):
    """Navigatie-tegels op elke pagina, niet alleen het startscherm — de
    zijbalk in basis.html staat op elk scherm dat er van erft."""
    if not request.user.is_authenticated:
        return {}
    return {"tegels": zichtbare_tegels(request.user)}
