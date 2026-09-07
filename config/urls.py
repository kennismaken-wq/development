from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from medewerkers import views as medewerkers_views

urlpatterns = [
    path("", medewerkers_views.start, name="start"),
    path("inloggen/", auth_views.LoginView.as_view(redirect_authenticated_user=True), name="inloggen"),
    path("uitloggen/", auth_views.LogoutView.as_view(), name="uitloggen"),
    path("beheer/", admin.site.urls),
]
