from django.contrib import admin

from perfiles.models import HabilidadCandidato, PerfilCandidato


class HabilidadInline(admin.TabularInline):
    model = HabilidadCandidato
    extra = 0


@admin.register(PerfilCandidato)
class PerfilCandidatoAdmin(admin.ModelAdmin):
    list_display = ("usuario", "confirmado", "actualizado_en")
    list_filter = ("confirmado",)
    inlines = [HabilidadInline]
