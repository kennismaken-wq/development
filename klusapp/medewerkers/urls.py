from django.urls import path

from . import views

urlpatterns = [
    # TIJDELIJK: tweede beginscherm om te vergelijken; zie views.menu_demo
    path("menu/", views.menu_demo, name="menu_demo"),
    # TIJDELIJK: nepmedewerkers met uren; zie medewerkers/testgegevens.py
    path("menu/testgegevens/", views.testgegevens, name="testgegevens"),
    path("medewerkers/", views.medewerker_lijst, name="medewerkers"),
    path("medewerkers/nieuw/", views.medewerker_nieuw, name="medewerker_nieuw"),
    path("medewerkers/<int:pk>/", views.medewerker_bewerken, name="medewerker_bewerken"),
    path("medewerkers/<int:pk>/wachtwoord/", views.medewerker_wachtwoord, name="medewerker_wachtwoord"),
    path("medewerkers/<int:pk>/dienst/", views.medewerker_dienst, name="medewerker_dienst"),
]
