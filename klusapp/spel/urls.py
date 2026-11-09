from django.urls import path

from . import views

urlpatterns = [
    path("spel/", views.spel, name="spel"),
    path("spel/start/", views.spel_start, name="spel_start"),
    path("spel/score/", views.spel_score, name="spel_score"),
]
