from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Medewerker


@admin.register(Medewerker)
class MedewerkerAdmin(UserAdmin):
    list_display = ["naam", "username", "rol", "is_active"]
    list_filter = ["rol", "is_active"]
    fieldsets = UserAdmin.fieldsets + (
        ("Klusapp", {"fields": ("rol", "telefoon", "kleur", "in_dienst_sinds", "uit_dienst_sinds")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Klusapp", {"fields": ("first_name", "last_name", "rol")}),
    )
