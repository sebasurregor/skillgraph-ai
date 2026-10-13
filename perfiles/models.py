from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from vacantes.models import Habilidad


class PerfilCandidato(models.Model):
    """Perfil laboral de un candidato. Corresponde a un nodo :Candidato del grafo."""

    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name="perfil")
    confirmado = models.BooleanField(
        default=False, help_text="El candidato ya confirmó los datos de su perfil.")
    por_aprender = models.ManyToManyField(
        Habilidad, blank=True, related_name="interesados",
        help_text="Habilidades que está dispuesto a aprender o certificar.")
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "perfil de candidato"
        verbose_name_plural = "perfiles de candidatos"

    def __str__(self):
        return f"Perfil de {self.usuario}"


class HabilidadCandidato(models.Model):
    """Habilidad declarada con su nivel de 1 a 5. Arista :TIENE del grafo."""

    perfil = models.ForeignKey(PerfilCandidato, on_delete=models.CASCADE,
                               related_name="habilidades")
    habilidad = models.ForeignKey(Habilidad, on_delete=models.PROTECT, related_name="candidatos")
    nivel = models.PositiveSmallIntegerField(
        default=3, validators=[MinValueValidator(1), MaxValueValidator(5)])

    class Meta:
        ordering = ["habilidad__nombre"]
        constraints = [models.UniqueConstraint(fields=["perfil", "habilidad"],
                                               name="habilidad_unica_por_perfil")]

    def __str__(self):
        return f"{self.perfil.usuario} · {self.habilidad} ({self.nivel})"
