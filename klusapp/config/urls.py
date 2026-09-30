from django.contrib import admin
from django.conf import settings
from django.contrib.auth import views as auth_views
from django.urls import include, path, reverse_lazy

from medewerkers import views as medewerkers_views
from medewerkers.forms import NieuwWachtwoordForm, WachtwoordVergetenForm

# "Wachtwoord vergeten": Django's eigen reset-flow, met onze schermen en mail.
# De mail gaat via dezelfde SMTP-instellingen als de urenback-up (.env, zie
# docs/DEPLOY.md). Staan die er op de server niet, dan gaat er niets de deur
# uit; de schermen zeggen dat dan eerlijk in plaats van te doen alsof.
MAIL_NIET_INGESTELD = not settings.EMAIL_HOST and not settings.DEBUG

# Schermen die nog gebouwd worden. De naam staat hier al vast, zodat de rest van
# de app er nu al naar kan verwijzen en niemand later door de codebase hoeft om
# links om te hangen. Bouw je er een, haal 'm dan hier weg en zet de echte route
# in de urls.py van je eigen app — en haal "in_aanbouw" uit de tegel in
# medewerkers/views.py. Zie klusapp/CONTEXT.md voor wie wat doet.
#
# De lijst is leeg: alle schermen uit fase 1 zijn gebouwd. Hij blijft staan
# voor het volgende scherm dat alvast een naam nodig heeft.
nog_te_bouwen = []

urlpatterns = [
    path("", medewerkers_views.start, name="start"),
    path("inloggen/", auth_views.LoginView.as_view(redirect_authenticated_user=True), name="inloggen"),
    path("uitloggen/", auth_views.LogoutView.as_view(), name="uitloggen"),
    path(
        "wachtwoord-vergeten/",
        auth_views.PasswordResetView.as_view(
            form_class=WachtwoordVergetenForm,
            template_name="registration/wachtwoord_vergeten.html",
            email_template_name="registration/wachtwoord_mail.txt",
            subject_template_name="registration/wachtwoord_onderwerp.txt",
            success_url=reverse_lazy("wachtwoord_verstuurd"),
            extra_context={"mail_niet_ingesteld": MAIL_NIET_INGESTELD},
        ),
        name="wachtwoord_vergeten",
    ),
    path(
        "wachtwoord-vergeten/verstuurd/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="registration/wachtwoord_verstuurd.html",
            extra_context={"mail_niet_ingesteld": MAIL_NIET_INGESTELD},
        ),
        name="wachtwoord_verstuurd",
    ),
    path(
        "wachtwoord-herstellen/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            form_class=NieuwWachtwoordForm,
            template_name="registration/wachtwoord_nieuw.html",
            success_url=reverse_lazy("wachtwoord_klaar"),
        ),
        name="wachtwoord_herstellen",
    ),
    path(
        "wachtwoord-herstellen/klaar/",
        auth_views.PasswordResetCompleteView.as_view(template_name="registration/wachtwoord_klaar.html"),
        name="wachtwoord_klaar",
    ),
    path("loonstrook/", medewerkers_views.loonstrook, name="loonstrook"),
    path("mijn-profiel/", medewerkers_views.mijn_profiel, name="mijn_profiel"),
    path("", include("medewerkers.urls")),
    path("", include("uren.urls")),
    path("", include("klussen.urls")),
    *nog_te_bouwen,
    path("beheer/", admin.site.urls),
]
