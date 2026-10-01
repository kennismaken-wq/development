from django.contrib import admin

from .models import Bijlage, Klus, Notitie


@admin.register(Klus)
class KlusAdmin(admin.ModelAdmin):
    list_display = ["naam", "soort", "plaats", "actief"]
    list_filter = ["soort", "actief"]
    search_fields = ["naam", "opdrachtgever", "adres", "plaats"]


@admin.register(Bijlage)
class BijlageAdmin(admin.ModelAdmin):
    list_display = ["__str__", "soort", "klus", "datum", "toegevoegd_op"]
    list_filter = ["soort"]
    date_hierarchy = "datum"


@admin.register(Notitie)
class NotitieAdmin(admin.ModelAdmin):
    list_display = ["klus", "geschreven_door", "geschreven_op"]
    list_filter = ["klus"]
