from django.contrib import admin

from cuentas.models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ("email", "first_name", "last_name", "rol", "ciudad", "is_active")
    list_filter = ("rol", "is_active")
    search_fields = ("email", "first_name", "last_name")
    exclude = ("password",)
