from django.contrib import admin

from .models import Bijlage, Klus


@admin.register(Klus)
class KlusAdmin(admin.ModelAdmin):
    list_display = ["naam", "soort", "plaats", "actief"]
    list_filter = ["soort", "actief"]
    search_fields = ["naam", "opdrachtgever", "adres", "plaats"]


@admin.register(Bijlage)
class BijlageAdmin(admin.ModelAdmin):
    list_display = ["__str__", "soort", "klus", "toegevoegd_op"]
    list_filter = ["soort"]
