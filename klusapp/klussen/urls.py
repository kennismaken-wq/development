from django.urls import path, re_path

from . import views

urlpatterns = [
    path("klussen/", views.klus_lijst, name="klussen"),
    path("klussen/nieuw/", views.klus_nieuw, name="klus_nieuw"),
    path("klussen/<int:pk>/", views.klus_detail, name="klus_detail"),
    path("klussen/<int:pk>/bewerken/", views.klus_bewerken, name="klus_bewerken"),
    path("klussen/<int:pk>/uren-export/", views.klus_uren_export, name="klus_uren_export"),
    path("fotos/", views.fotos, name="fotos"),
    path("bijlagen/toevoegen/", views.bijlage_toevoegen, name="bijlage_toevoegen"),
    path("bijlagen/<int:pk>/verwijderen/", views.bijlage_verwijderen, name="bijlage_verwijderen"),
    # Geüploade bestanden gaan door Django heen voor de rechtencontrole; ze
    # staan bewust niet als statische map open.
    re_path(r"^media/(?P<pad>.+)$", views.media_bestand, name="media_bestand"),
]
