"""Welke week of dag een scherm laat zien, en hoe je een stap vooruit of
terug gaat.

Losse module omdat vier schermen dezelfde navigatie hebben: uren schrijven,
mijn overzicht, het planbord en de aanwezigheid. Zonder deze module staat
dezelfde weekberekening vier keer in views.py, en dan loopt hij vroeg of laat
uit elkaar.

`timezone.localdate()` en niet `date.today()`: met USE_TZ=True en
TIME_ZONE="Europe/Amsterdam" geeft `date.today()` op een UTC-server na 22:00 de
vorige dag terug — precies het moment waarop de mannen hun uren invullen.
"""

from datetime import date, timedelta

from django.utils import timezone


def vandaag():
    return timezone.localdate()


def gekozen_dag(request):
    """De dag uit ?dag=JJJJ-MM-DD, of vandaag.

    Een onleesbare datum is geen fout maar gewoon vandaag: dit komt uit een
    link, niet uit een formulier, en een foutpagina helpt niemand.
    """
    gevraagd = request.GET.get("dag")
    if gevraagd:
        try:
            return date.fromisoformat(gevraagd)
        except ValueError:
            pass
    return vandaag()


def week_van(dag):
    maandag = dag - timedelta(days=dag.weekday())
    return maandag, maandag + timedelta(days=6)


def week_context(request):
    """Alles wat een weekscherm nodig heeft om zichzelf te tekenen en om
    vooruit en terug te kunnen bladeren."""
    dag = gekozen_dag(request)
    nu = vandaag()
    maandag, zondag = week_van(dag)
    return {
        "dag": dag,
        "vandaag": nu,
        "maandag": maandag,
        "zondag": zondag,
        "dagen": [maandag + timedelta(days=n) for n in range(7)],
        "vorige": maandag - timedelta(days=7),
        "volgende": maandag + timedelta(days=7),
        "is_deze_week": maandag <= nu <= zondag,
    }
