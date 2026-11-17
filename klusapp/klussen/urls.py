from django.urls import path, re_path

from . import chat, views

urlpatterns = [
    path("klussen/", views.klus_lijst, name="klussen"),
    path("klussen/nieuw/", views.klus_nieuw, name="klus_nieuw"),
    path("klussen/<int:pk>/", views.klus_detail, name="klus_detail"),
    path("klussen/<int:pk>/bewerken/", views.klus_bewerken, name="klus_bewerken"),
    path("klussen/<int:pk>/uren-export/", views.klus_uren_export, name="klus_uren_export"),
    path("klussen/<int:pk>/chat/", chat.chat, name="klus_chat"),
    path("klussen/<int:pk>/chat/nieuw/", chat.chat_nieuw, name="klus_chat_nieuw"),
    path("klussen/<int:pk>/notities/", chat.notitie_toevoegen, name="notitie_toevoegen"),
    path("klussen/<int:pk>/meedoen/", views.klus_meedoen, name="klus_meedoen"),
    path("notities/<int:pk>/verwijderen/", chat.notitie_verwijderen, name="notitie_verwijderen"),
    path("fotos/", views.fotos, name="fotos"),
    path("bijlagen/toevoegen/", views.bijlage_toevoegen, name="bijlage_toevoegen"),
    path("bijlagen/<int:pk>/verwijderen/", views.bijlage_verwijderen, name="bijlage_verwijderen"),
    path("bijlagen/<int:pk>/zichtbaar/", views.bijlage_zichtbaarheid, name="bijlage_zichtbaarheid"),
    path("bijlagen/post/<uuid:batch>/verwijderen/", views.post_verwijderen, name="post_verwijderen"),
    # Geüploade bestanden gaan door Django heen voor de rechtencontrole; ze
    # staan bewust niet als statische map open.
    re_path(r"^media/(?P<pad>.+)$", views.media_bestand, name="media_bestand"),
]
