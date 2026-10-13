import pytest

from cuentas import services
from cuentas.models import Usuario

CLAVE = "clave12345"


@pytest.fixture(autouse=True)
def _transporte_local(settings):
    """Las pruebas usan HTTP aunque el `.env` de la máquina tenga DJANGO_DEBUG=False."""
    settings.SECURE_SSL_REDIRECT = False
    settings.SESSION_COOKIE_SECURE = False
    settings.CSRF_COOKIE_SECURE = False


@pytest.fixture
def crear_usuario(db):
    def _crear(correo="camilo.zapata@correo.com", rol=Usuario.Rol.CANDIDATO, **extra):
        datos = dict(clave=CLAVE, nombres="Camilo", apellidos="Zapata Ospina",
                     telefono="3109876543", ciudad="Medellín", rol=rol,
                     empresa="Logística Express S.A.S." if rol == Usuario.Rol.RECLUTADOR else "")
        datos.update(extra)
        return services.registrar_usuario(correo=correo, **datos)
    return _crear


@pytest.fixture
def candidato(crear_usuario):
    return crear_usuario()


@pytest.fixture
def reclutador(crear_usuario):
    return crear_usuario(correo="reclutador@correo.com", rol=Usuario.Rol.RECLUTADOR,
                         nombres="Laura", apellidos="Gómez")
