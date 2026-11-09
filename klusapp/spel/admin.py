from django.contrib import admin

from .models import BesteScore


@admin.register(BesteScore)
class BesteScoreAdmin(admin.ModelAdmin):
    list_display = ["medewerker", "punten", "behaald_op"]
