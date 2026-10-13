from django.db import models

from perfiles.models import PerfilCandidato
from vacantes.models import Vacante


class Postulacion(models.Model):
    """Un candidato se postula a una vacante. Solo puede hacerlo una vez."""

    class Estado(models.TextChoices):
        ENVIADA = "enviada", "Enviada"
        EN_REVISION = "en_revision", "En revisión"
        PRESELECCIONADA = "preseleccionada", "Preseleccionada"
        DESCARTADA = "descartada", "Descartada"

    candidato = models.ForeignKey(PerfilCandidato, on_delete=models.CASCADE,
                                  related_name="postulaciones")
    vacante = models.ForeignKey(Vacante, on_delete=models.CASCADE, related_name="postulaciones")
    estado = models.CharField(max_length=16, choices=Estado.choices, default=Estado.ENVIADA)
    ajuste_al_postular = models.PositiveSmallIntegerField(
        help_text="Porcentaje de match en el momento de postularse.")
    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-creada_en"]
        verbose_name = "postulación"
        verbose_name_plural = "postulaciones"
        constraints = [models.UniqueConstraint(fields=["candidato", "vacante"],
                                               name="una_postulacion_por_vacante")]

    def __str__(self):
        return f"{self.candidato.usuario} → {self.vacante}"
