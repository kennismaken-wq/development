from django.urls import path

from . import views

urlpatterns = [
    # TIJDELIJK: nepmedewerkers met uren; zie medewerkers/testgegevens.py
    path("testgegevens/", views.testgegevens, name="testgegevens"),
    # TIJDELIJK: als medewerker meekijken om te testen; zie views.wissel_naar
    path("wissel/<int:pk>/", views.wissel_naar, name="wissel_naar"),
    path("wissel/terug/", views.wissel_terug, name="wissel_terug"),
    path("medewerkers/", views.medewerker_lijst, name="medewerkers"),
    path("medewerkers/nieuw/", views.medewerker_nieuw, name="medewerker_nieuw"),
    path("medewerkers/<int:pk>/", views.medewerker_bewerken, name="medewerker_bewerken"),
    path("medewerkers/<int:pk>/kaart/", views.medewerker_kaart, name="medewerker_kaart"),
    path("medewerkers/<int:pk>/wachtwoord/", views.medewerker_wachtwoord, name="medewerker_wachtwoord"),
    path("medewerkers/<int:pk>/dienst/", views.medewerker_dienst, name="medewerker_dienst"),
]
