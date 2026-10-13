from django.contrib import admin

from vacantes.models import AreaOcupacional, Habilidad, RequisitoVacante, Vacante


class RequisitoInline(admin.TabularInline):
    model = RequisitoVacante
    extra = 0


@admin.register(Vacante)
class VacanteAdmin(admin.ModelAdmin):
    list_display = ("titulo", "empresa", "area", "estado", "actualizada_en")
    list_filter = ("estado", "area")
    search_fields = ("titulo", "empresa")
    inlines = [RequisitoInline]


@admin.register(Habilidad)
class HabilidadAdmin(admin.ModelAdmin):
    list_display = ("nombre", "transversal")
    list_filter = ("transversal", "areas")
    search_fields = ("nombre",)


admin.site.register(AreaOcupacional)
