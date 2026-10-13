from io import StringIO

import pytest
from django.core.management import call_command
from neo4j.exceptions import ServiceUnavailable

from cuentas import services
from cuentas.models import Usuario
from GraphCore import servicio_grafo
from GraphCore.neo4j_driver import Neo4jConnection
from vacantes import services as vacantes
from vacantes.models import Habilidad

CLAVE = "clave12345"
# Métodos reales, para las pruebas que verifican GraphCore sin el simulador.
VERIFY_REAL = Neo4jConnection.verify
NEO4J_REAL = {m: getattr(Neo4jConnection, m) for m in ("verify", "write", "read")}


@pytest.fixture(autouse=True)
def _transporte_local(settings):
    """Las pruebas usan HTTP aunque el `.env` de la máquina tenga DJANGO_DEBUG=False."""
    settings.SECURE_SSL_REDIRECT = False
    settings.SESSION_COOKIE_SECURE = False
    settings.CSRF_COOKIE_SECURE = False


@pytest.fixture(autouse=True)
def _hash_rapido(request, settings):
    """bcrypt con costo 12 tarda a propósito; solo lo usan las pruebas que lo verifican."""
    if not request.node.get_closest_marker("hash_real"):
        settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture(autouse=True)
def _archivos_temporales(settings, tmp_path):
    """Las hojas de vida que suben las pruebas no se mezclan con las reales."""
    settings.MEDIA_ROOT = tmp_path / "media"


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
        self.vacantes = {}      # vacante_id → {centralidad, requisitos}
        self.candidatos = {}    # usuario_id → {habilidad: nivel}

    def _fallar_si_caido(self):
        if self.caido:
            raise ServiceUnavailable("Neo4j simulado fuera de servicio")

    def verify(self):
        return (False, "Servidor de Neo4j no disponible") if self.caido else (True, "ok")

    def write(self, cypher, **params):
        self._fallar_si_caido()
        self.escrituras.append((cypher, params))
        if "MERGE (v:Vacante" in cypher:
            self.vacantes[params["vacante_id"]] = {
                "centralidad": params["datos"].get("centralidad"),
                "requisitos": params["requisitos"]}
        elif "DETACH DELETE v" in cypher:
            self.vacantes.pop(params["vacante_id"], None)
        elif "MERGE (c:Candidato {usuario_id: $usuario_id})\n          SET c +=" in cypher:
            self.candidatos[params["usuario_id"]] = {
                h["nombre"]: h["nivel"] for h in params["habilidades"]}
        elif "DETACH DELETE c" in cypher:
            self.candidatos.pop(params["usuario_id"], None)
        return []

    def read(self, cypher, **params):
        self._fallar_si_caido()
        self.lecturas.append((cypher, params))
        if "AS presentes" in cypher:
            return [{"presentes": [u for u in params["candidatos"] if u in self.candidatos]}]
        if "OPTIONAL MATCH (c:Candidato {usuario_id: usuario_id})-[t:TIENE]->(s)" in cypher:
            return self._recorrido(params["candidatos"], params["vacantes"])
        return self.respuesta_lectura

    def _recorrido(self, candidatos, vacantes):
        """Lo que devolvería Neo4j para Vacante → REQUIERE → Skill ← TIENE ← Candidato."""
        return [
            {"usuario_id": usuario, "vacante_id": vacante,
             "centralidad": self.vacantes[vacante]["centralidad"], "habilidad": r["nombre"],
             "peso": r["peso"], "nivel_min": r["nivel_min"], "obligatoria": r["obligatoria"],
             "nivel": self.candidatos.get(usuario, {}).get(r["nombre"])}
            for vacante in vacantes if vacante in self.vacantes
            for r in self.vacantes[vacante]["requisitos"]
            for usuario in candidatos
        ]

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
def grafo_real(grafo, monkeypatch):
    """Usa el Neo4j de verdad. Solo para las pruebas de integración opcionales."""
    for metodo, real in NEO4J_REAL.items():
        monkeypatch.setattr(Neo4jConnection, metodo, real)
    servicio_grafo.reiniciar_estado()


@pytest.fixture
def demo(db):
    """Datos de demostración: 16 vacantes, reclutador, Ana María y Camilo."""
    call_command("cargar_datos_demo", stdout=StringIO())


@pytest.fixture
def grafo_caido(grafo):
    grafo.caido = True
    return grafo


@pytest.fixture
def catalogo(db):
    vacantes.cargar_catalogo()
    return {h.nombre: h for h in Habilidad.objects.all()}
