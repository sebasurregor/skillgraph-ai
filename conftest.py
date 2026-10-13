import pytest
from neo4j.exceptions import ServiceUnavailable

from cuentas import services
from cuentas.models import Usuario
from GraphCore import servicio_grafo
from GraphCore.neo4j_driver import Neo4jConnection
from vacantes import services as vacantes
from vacantes.models import Habilidad

CLAVE = "clave12345"
# Método real, para las pruebas que verifican GraphCore sin el simulador.
VERIFY_REAL = Neo4jConnection.verify


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


class GrafoSimulado:
    """Sustituye a Neo4j en las pruebas: registra las consultas y puede simular una caída."""

    def __init__(self):
        self.caido = False
        self.escrituras = []
        self.lecturas = []
        self.respuesta_lectura = [{"total": 0}]

    def _fallar_si_caido(self):
        if self.caido:
            raise ServiceUnavailable("Neo4j simulado fuera de servicio")

    def verify(self):
        return (False, "Servidor de Neo4j no disponible") if self.caido else (True, "ok")

    def write(self, cypher, **params):
        self._fallar_si_caido()
        self.escrituras.append((cypher, params))
        return []

    def read(self, cypher, **params):
        self._fallar_si_caido()
        self.lecturas.append((cypher, params))
        return self.respuesta_lectura

    def escrituras_con(self, texto):
        return [(c, p) for c, p in self.escrituras if texto in c]


@pytest.fixture(autouse=True)
def grafo(monkeypatch):
    """Ninguna prueba toca el Neo4j real."""
    simulado = GrafoSimulado()
    for metodo in ("verify", "write", "read"):
        monkeypatch.setattr(Neo4jConnection, metodo, getattr(simulado, metodo))
    servicio_grafo.reiniciar_estado()
    yield simulado
    servicio_grafo.reiniciar_estado()


@pytest.fixture
def grafo_caido(grafo):
    grafo.caido = True
    return grafo


@pytest.fixture
def catalogo(db):
    vacantes.cargar_catalogo()
    return {h.nombre: h for h in Habilidad.objects.all()}
