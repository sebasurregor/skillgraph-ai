from django.contrib import admin

from postulaciones.models import Postulacion


@admin.register(Postulacion)
class PostulacionAdmin(admin.ModelAdmin):
    list_display = ("candidato", "vacante", "estado", "ajuste_al_postular", "creada_en")
    list_filter = ("estado",)
