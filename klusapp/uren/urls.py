from django.urls import path

from . import views

urlpatterns = [
    path("uren/", views.mijn_uren, name="mijn_uren"),
    path("uren/nieuw/", views.uurblok_nieuw, name="uurblok_nieuw"),
    path("uren/<int:pk>/", views.uurblok_bewerken, name="uurblok_bewerken"),
    path("uren/<int:pk>/verwijderen/", views.uurblok_verwijderen, name="uurblok_verwijderen"),
    path("export/", views.urenexport, name="urenexport"),
]
