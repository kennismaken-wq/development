from django.conf import settings


def testmelding(request):
    """TIJDELIJK / TEST: basis.html laadt static/js/pushmelding.js alleen als
    dit aan staat: ingelogd en op develop (settings.TESTFUNCTIES)."""
    return {"testmelding": settings.TESTFUNCTIES and request.user.is_authenticated}
