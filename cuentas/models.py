from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UsuarioManager(BaseUserManager):
    use_in_migrations = True

    def _crear(self, email, password, **extra):
        if not email:
            raise ValueError("El correo electrónico es obligatorio")
        usuario = self.model(email=self.normalize_email(email).lower(), **extra)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._crear(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra["is_staff"] = True
        extra["is_superuser"] = True
        return self._crear(email, password, **extra)


class Usuario(AbstractUser):
    """Cuenta del sistema. Se identifica por correo y tiene un único rol."""

    class Rol(models.TextChoices):
        CANDIDATO = "candidato", "Candidato"
        RECLUTADOR = "reclutador", "Reclutador"

    username = None
    email = models.EmailField("correo electrónico", unique=True)
    rol = models.CharField(max_length=12, choices=Rol.choices, default=Rol.CANDIDATO)
    telefono = models.CharField("teléfono", max_length=10)
    ciudad = models.CharField(max_length=60)
    empresa = models.CharField(max_length=120, blank=True)
    acepta_tratamiento_datos = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UsuarioManager()

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"

    def __str__(self):
        return self.email

    @property
    def es_candidato(self):
        return self.rol == self.Rol.CANDIDATO

    @property
    def es_reclutador(self):
        return self.rol == self.Rol.RECLUTADOR

    @property
    def iniciales(self):
        return ((self.first_name[:1] or "?") + self.last_name[:1]).upper()
