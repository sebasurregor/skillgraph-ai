"""Comando cargar_datos_demo (sección 7)."""
from decimal import Decimal
from io import StringIO

import pytest
from django.contrib.auth import authenticate
from django.core.management import call_command
from django.core.management.base import CommandError

from cuentas.models import Usuario
from perfiles.models import PerfilCandidato
from vacantes.models import AreaOcupacional, Habilidad, Vacante

NO_TECNICAS = ["Logística y bodega", "Alimentos y restaurantes", "Belleza y estética",
               "Seguridad y vigilancia", "Construcción y oficios", "Ventas y comercio"]


@pytest.fixture
def demo(db):
    """Aquí interesa además lo que el comando imprime."""
    salida = StringIO()
    call_command("cargar_datos_demo", stdout=salida)
    return salida.getvalue()


def test_demo_carga_el_catalogo_de_las_16_areas(demo):
    assert AreaOcupacional.objects.count() == 16
    assert Habilidad.objects.filter(transversal=True).count() == 8
    assert Habilidad.objects.count() > 100
    for area in AreaOcupacional.objects.all():
        assert area.habilidades.exists(), area.nombre


def test_demo_habilidad_compartida_queda_una_sola_vez(demo):
    excel = Habilidad.objects.get(nombre="Excel")
    assert excel.transversal
    assert excel.areas.filter(nombre="Administración y finanzas").exists()


def test_demo_crea_al_menos_15_vacantes_publicadas_y_bien_ponderadas(demo):
    publicadas = Vacante.objects.filter(estado=Vacante.Estado.PUBLICADA)
    assert publicadas.count() >= 15
    for vacante in publicadas:
        assert vacante.suma_pesos == Decimal("1.00"), vacante.titulo
        assert vacante.requisitos.filter(obligatoria=True).exists(), vacante.titulo
        assert vacante.publicada_en is not None


def test_demo_vacantes_de_sectores_tecnicos_y_no_tecnicos(demo):
    areas = set(Vacante.objects.values_list("area__nombre", flat=True))
    assert len(areas) >= 12
    assert "Tecnología e informática" in areas
    for area in NO_TECNICAS:
        assert area in areas


def test_demo_crea_un_reclutador_de_prueba(demo):
    reclutador = Usuario.objects.get(rol=Usuario.Rol.RECLUTADOR)
    assert authenticate(username=reclutador.email, password="skillgraph2026") == reclutador
    assert reclutador.vacantes.count() >= 15


def test_demo_crea_a_ana_maria_con_perfil_tecnologico(demo):
    ana = authenticate(username="ana.rios@correo.com", password="skillgraph2026")
    assert ana.get_full_name() == "Ana María Ríos Bedoya"
    assert ana.es_candidato and ana.perfil.confirmado
    assert dict(ana.perfil.habilidades.values_list("habilidad__nombre", "nivel")) == {
        "Python": 5, "Django": 3, "SQL": 4, "Docker": 3, "Git": 5, "Scrum": 3, "Linux": 4}
    assert set(ana.perfil.por_aprender.values_list("nombre", flat=True)) == {
        "Neo4j / Cypher", "AWS"}


def test_demo_crea_a_camilo_con_perfil_de_temporada(demo):
    camilo = authenticate(username="camilo.zapata@correo.com", password="skillgraph2026")
    assert camilo.es_candidato and camilo.perfil.confirmado
    assert dict(camilo.perfil.habilidades.values_list("habilidad__nombre", "nivel")) == {
        "Trabajo en equipo": 4, "Puntualidad": 5, "Atención al cliente": 3,
        "Carga y descarga": 3, "Alistamiento de pedidos": 2}


@pytest.mark.hash_real
def test_demo_las_contrasenas_quedan_cifradas(demo):
    for usuario in Usuario.objects.all():
        assert usuario.password.startswith("bcrypt_sha256$$2b$12$")


def test_demo_carga_el_grafo(demo, grafo):
    assert "Neo4j: grafo sincronizado." in demo
    assert len(grafo.escrituras_con("CREATE CONSTRAINT")) == 4      # init_graph
    assert len(grafo.escrituras_con("MERGE (v)-[r:REQUIERE]->(s)")) == Vacante.objects.count()
    assert len(grafo.escrituras_con("MERGE (c)-[t:TIENE]->(s)")) == 2
    (_, params), = grafo.escrituras_con("SET s.categoria")
    assert len(params["habilidades"]) == Habilidad.objects.count()


def test_demo_se_puede_ejecutar_varias_veces(demo):
    antes = (Usuario.objects.count(), Vacante.objects.count(), Habilidad.objects.count(),
             PerfilCandidato.objects.count())
    call_command("cargar_datos_demo", stdout=StringIO())
    assert antes == (Usuario.objects.count(), Vacante.objects.count(),
                     Habilidad.objects.count(), PerfilCandidato.objects.count())


@pytest.mark.django_db
def test_demo_funciona_con_neo4j_caido(grafo_caido):
    salida = StringIO()
    call_command("cargar_datos_demo", stdout=salida)
    assert Vacante.objects.filter(estado=Vacante.Estado.PUBLICADA).count() >= 15
    assert "Neo4j no está disponible" in salida.getvalue()
    assert "sincronizar_grafo" in salida.getvalue()


def test_sincronizar_grafo_reconstruye_el_grafo_desde_sqlite(demo, grafo):
    grafo.escrituras.clear()
    salida = StringIO()
    call_command("sincronizar_grafo", stdout=salida)
    assert "16 vacantes y 2 candidatos" in salida.getvalue()
    assert len(grafo.escrituras_con("REQUIERE")) == 16


def test_sincronizar_grafo_falla_con_mensaje_claro_si_neo4j_esta_caido(demo, grafo):
    grafo.caido = True
    from GraphCore import servicio_grafo
    servicio_grafo.reiniciar_estado()
    with pytest.raises(CommandError, match="Neo4j no está disponible"):
        call_command("sincronizar_grafo", stdout=StringIO())
