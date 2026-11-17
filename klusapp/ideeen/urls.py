from django.urls import path

from . import views

urlpatterns = [
    path("ideeen/", views.ideeen, name="ideeen"),
    path("ideeen/nieuw/", views.idee_nieuw, name="idee_nieuw"),
    path("ideeen/<int:pk>/like/", views.idee_like, name="idee_like"),
    path("ideeen/<int:pk>/stand/", views.idee_stand, name="idee_stand"),
    path("ideeen/<int:pk>/verwijderen/", views.idee_verwijderen, name="idee_verwijderen"),
]
