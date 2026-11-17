from django.contrib import admin

from .models import Idee


@admin.register(Idee)
class IdeeAdmin(admin.ModelAdmin):
    list_display = ("tekst", "stand", "gemaakt_op")
    list_filter = ("stand",)
