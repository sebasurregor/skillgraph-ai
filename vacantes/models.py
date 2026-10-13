from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class AreaOcupacional(models.Model):
    """Una de las 16 áreas del mercado laboral que cubre el sistema."""

    nombre = models.CharField(max_length=80, unique=True)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["orden", "nombre"]
        verbose_name = "área ocupacional"
        verbose_name_plural = "áreas ocupacionales"

    def __str__(self):
        return self.nombre


class Habilidad(models.Model):
    """Habilidad del catálogo. Corresponde a un nodo :Skill del grafo."""

    nombre = models.CharField(max_length=80, unique=True)
    transversal = models.BooleanField(
        default=False, help_text="Sirve en cualquier oficio, sin importar el área.")
    areas = models.ManyToManyField(AreaOcupacional, related_name="habilidades", blank=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name_plural = "habilidades"

    def __str__(self):
        return self.nombre

    @property
    def categoria(self):
        """Categoría del nodo :Skill: su primera área o «Transversal»."""
        area = self.areas.first()
        return area.nombre if area else "Transversal"


class Vacante(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        PUBLICADA = "publicada", "Publicada"

    MODALIDADES = [(m, m) for m in ("Presencial", "Híbrido", "Remoto")]
    JORNADAS = [(j, j) for j in ("Tiempo completo", "Medio tiempo", "Por turnos", "Temporal",
                                 "Por horas", "Prácticas o contrato de aprendizaje")]

    reclutador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name="vacantes")
    titulo = models.CharField("título", max_length=120)
    empresa = models.CharField(max_length=120, blank=True)
    cargo = models.CharField(max_length=80, blank=True)
    descripcion = models.TextField("descripción", blank=True)
    area = models.ForeignKey(AreaOcupacional, verbose_name="área ocupacional", null=True,
                             blank=True, on_delete=models.PROTECT, related_name="vacantes")
    ciudad = models.CharField(max_length=60, blank=True)
    modalidad = models.CharField(max_length=12, choices=MODALIDADES, blank=True)
    jornada = models.CharField("tipo de contrato", max_length=40, choices=JORNADAS, blank=True)
    salario = models.PositiveIntegerField("salario mensual", null=True, blank=True)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.BORRADOR)
    centralidad = models.FloatField(default=0.5)
    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)
    publicada_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-actualizada_en"]

    def __str__(self):
        return self.titulo

    @property
    def publicada(self):
        return self.estado == self.Estado.PUBLICADA

    @property
    def suma_pesos(self):
        return sum((r.peso for r in self.requisitos.all()), Decimal("0"))


class RequisitoVacante(models.Model):
    """Habilidad ponderada que exige una vacante. Arista :REQUIERE del grafo."""

    vacante = models.ForeignKey(Vacante, on_delete=models.CASCADE, related_name="requisitos")
    habilidad = models.ForeignKey(Habilidad, on_delete=models.PROTECT, related_name="requisitos")
    peso = models.DecimalField(
        max_digits=3, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(Decimal("1.00"))])
    nivel_minimo = models.PositiveSmallIntegerField(
        "nivel mínimo", default=3, validators=[MinValueValidator(1), MaxValueValidator(5)])
    obligatoria = models.BooleanField(default=False)

    class Meta:
        ordering = ["-peso", "id"]
        constraints = [models.UniqueConstraint(fields=["vacante", "habilidad"],
                                               name="requisito_unico_por_vacante")]

    def __str__(self):
        return f"{self.vacante} · {self.habilidad} ({self.peso})"
