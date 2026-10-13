from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from vacantes.models import Habilidad


class PerfilCandidato(models.Model):
    """Perfil laboral de un candidato. Corresponde a un nodo :Candidato del grafo."""

    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name="perfil")
    nombre_completo = models.CharField(max_length=150, blank=True)
    correo = models.EmailField("correo de contacto", blank=True)
    telefono = models.CharField("teléfono", max_length=10, blank=True)
    experiencia = models.TextField(blank=True)
    educacion = models.TextField("educación", blank=True)
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


class HojaDeVida(models.Model):
    """Archivo original que subió el candidato y lo que el sistema extrajo de él."""

    class Formato(models.TextChoices):
        PDF = "pdf", "PDF"
        DOCX = "docx", "Word (.docx)"

    perfil = models.ForeignKey(PerfilCandidato, on_delete=models.CASCADE,
                               related_name="hojas_de_vida")
    archivo = models.FileField(upload_to="hojas_de_vida/%Y/%m/")
    nombre_original = models.CharField(max_length=255)
    formato = models.CharField(max_length=4, choices=Formato.choices)
    tamano = models.PositiveIntegerField("tamaño en bytes")
    texto = models.TextField(blank=True)
    datos_extraidos = models.JSONField(default=dict)
    suficiente = models.BooleanField(
        default=False, help_text="Se logró extraer información suficiente para precargar.")
    subida_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-subida_en"]
        verbose_name = "hoja de vida"
        verbose_name_plural = "hojas de vida"

    def __str__(self):
        return self.nombre_original

    @property
    def faltantes(self):
        return self.datos_extraidos.get("faltantes", [])


class VersionPerfil(models.Model):
    """Fotografía del perfil cada vez que el candidato lo confirma. La última es la válida."""

    class Origen(models.TextChoices):
        HOJA_DE_VIDA = "cv", "Hoja de vida"
        MANUAL = "manual", "Formulario manual"

    perfil = models.ForeignKey(PerfilCandidato, on_delete=models.CASCADE,
                               related_name="versiones")
    numero = models.PositiveIntegerField()
    origen = models.CharField(max_length=6, choices=Origen.choices)
    hoja_de_vida = models.ForeignKey(HojaDeVida, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name="versiones")
    datos = models.JSONField()
    confirmada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-numero"]
        constraints = [models.UniqueConstraint(fields=["perfil", "numero"],
                                               name="version_unica_por_perfil")]
        verbose_name = "versión del perfil"
        verbose_name_plural = "versiones del perfil"

    def __str__(self):
        return f"{self.perfil} · versión {self.numero}"


class PreferenciaLaboral(models.Model):
    """Qué busca el candidato (HU-RF-004). Filtra sus recomendaciones."""

    perfil = models.OneToOneField(PerfilCandidato, on_delete=models.CASCADE,
                                  related_name="preferencias")
    cargos = models.JSONField(default=list, blank=True)
    ubicaciones = models.JSONField(default=list, blank=True)
    tipos_contrato = models.JSONField(default=list, blank=True)
    salario_min = models.PositiveIntegerField("salario mínimo esperado", null=True, blank=True)
    salario_max = models.PositiveIntegerField("salario máximo esperado", null=True, blank=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "preferencia laboral"
        verbose_name_plural = "preferencias laborales"

    def __str__(self):
        return f"Preferencias de {self.perfil.usuario}"

    @property
    def vacias(self):
        return not (self.cargos or self.ubicaciones or self.tipos_contrato
                    or self.salario_min or self.salario_max)
