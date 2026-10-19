from django.urls import path

from . import views

urlpatterns = [
    # TIJDELIJK / TEST: pushmeldingen, zie pushberichten/models.py
    path("push/sleutel/", views.sleutel, name="push_sleutel"),
    path("push/aanmelden/", views.aanmelden, name="push_aanmelden"),
    path("push/status/", views.status, name="push_status"),
]
