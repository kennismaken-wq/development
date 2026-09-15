from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from medewerkers import views as medewerkers_views

# Schermen die nog gebouwd worden. De naam staat hier al vast, zodat de rest van
# de app er nu al naar kan verwijzen en niemand later door de codebase hoeft om
# links om te hangen. Bouw je er een, haal 'm dan hier weg en zet de echte route
# in de urls.py van je eigen app — en haal "in_aanbouw" uit de tegel in
# medewerkers/views.py. Zie klusapp/CONTEXT.md voor wie wat doet.
nog_te_bouwen = [
    path("aanwezigheid/", medewerkers_views.in_aanbouw, name="aanwezigheid"),
]

urlpatterns = [
    path("", medewerkers_views.start, name="start"),
    path("inloggen/", auth_views.LoginView.as_view(redirect_authenticated_user=True), name="inloggen"),
    path("uitloggen/", auth_views.LogoutView.as_view(), name="uitloggen"),
    path("loonstrook/", medewerkers_views.loonstrook, name="loonstrook"),
    path("", include("uren.urls")),
    path("", include("klussen.urls")),
    *nog_te_bouwen,
    path("beheer/", admin.site.urls),
]
