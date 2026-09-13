from django.contrib import admin

from .models import Aanwezigheid, Uurblok


@admin.register(Uurblok)
class UurblokAdmin(admin.ModelAdmin):
    list_display = ["datum", "medewerker", "klus", "begintijd", "eindtijd"]
    list_filter = ["medewerker", "klus"]
    date_hierarchy = "datum"


@admin.register(Aanwezigheid)
class AanwezigheidAdmin(admin.ModelAdmin):
    list_display = ["datum", "medewerker", "aanwezig", "opmerking"]
    list_filter = ["aanwezig", "medewerker"]
