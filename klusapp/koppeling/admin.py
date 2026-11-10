from django.contrib import admin

from .models import Client, Koppeling


@admin.register(Koppeling)
class KoppelingAdmin(admin.ModelAdmin):
    list_display = ["medewerker", "client", "aangemaakt_op", "laatst_gebruikt_op", "ingetrokken_op"]
    # Geen tokens tonen of bewerken: er staat alleen een hash, en daar valt
    # niets aan te wijzigen dat ergens goed voor is.
    exclude = ["access_hash", "refresh_hash"]
    readonly_fields = ["medewerker", "client", "access_verloopt_op", "aangemaakt_op", "laatst_gebruikt_op"]


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ["naam", "client_id", "aangemaakt_op"]
    readonly_fields = ["client_id", "redirect_uris", "aangemaakt_op"]
