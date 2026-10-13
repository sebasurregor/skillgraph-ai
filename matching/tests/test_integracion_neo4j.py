"""Integración con un Neo4j real. Opcional: el resto de pruebas usa un grafo simulado.

    $env:SKILLGRAPH_PRUEBAS_NEO4J = "1"        (PowerShell)
    pytest matching/tests/test_integracion_neo4j.py

Usa identificadores altos que no chocan con los datos reales y los borra al terminar.
"""
import os

import pytest

from GraphCore import servicio_grafo
from matching import services
from matching.tests.test_servicio_matching import ANA, BACKEND

pytestmark = pytest.mark.skipif(
    os.getenv("SKILLGRAPH_PRUEBAS_NEO4J") != "1",
    reason="Defina SKILLGRAPH_PRUEBAS_NEO4J=1 para probar contra el Neo4j del .env")

VACANTE, CANDIDATA, INEXISTENTE = 9_000_001, 9_000_001, 9_000_002


@pytest.fixture
def nodos_de_prueba(grafo_real):
    assert servicio_grafo.disponible(), "Neo4j no responde: revise el .env y el servidor"
    servicio_grafo.sincronizar_vacante(
        VACANTE, {"titulo": "Prueba de integración", "centralidad": 0.91}, BACKEND)
    servicio_grafo.sincronizar_candidato(
        CANDIDATA, {"titular": "Candidata de prueba"},
        [{"nombre": n, "nivel": v} for n, v in ANA.items()])
    yield
    servicio_grafo.retirar_vacante(VACANTE)
    servicio_grafo.retirar_candidato(CANDIDATA)


def test_neo4j_real_el_recorrido_del_grafo_reproduce_el_82_por_ciento(nodos_de_prueba):
    filas = servicio_grafo.recorrido_de_match([CANDIDATA], [VACANTE])
    assert len(filas) == len(BACKEND)

    niveles = {f["habilidad"]: f["nivel"] for f in filas if f["nivel"] is not None}
    requisitos = [{"nombre": f["habilidad"], "peso": f["peso"], "nivel_min": f["nivel_min"],
                   "obligatoria": f["obligatoria"]} for f in filas]
    match = services.calcular_match(niveles, {"Neo4j / Cypher"}, requisitos,
                                    filas[0]["centralidad"])
    assert match.pct == 82
    assert [f["nombre"] for f in match.faltantes] == ["Neo4j / Cypher"]


def test_neo4j_real_distingue_candidatos_presentes_y_ausentes(nodos_de_prueba):
    assert servicio_grafo.candidatos_presentes([CANDIDATA, INEXISTENTE]) == {CANDIDATA}


def test_neo4j_real_sincronizar_reemplaza_las_aristas(nodos_de_prueba):
    servicio_grafo.sincronizar_candidato(CANDIDATA, {}, [{"nombre": "Python", "nivel": 2}])
    filas = servicio_grafo.recorrido_de_match([CANDIDATA], [VACANTE])
    assert {f["habilidad"]: f["nivel"] for f in filas if f["nivel"] is not None} == {"Python": 2}


def test_neo4j_real_cuenta_candidatos_que_cubren(nodos_de_prueba):
    exigidas = [{"nombre": "Python", "nivel_min": 5}, {"nombre": "Git", "nivel_min": 5}]
    antes = servicio_grafo.contar_candidatos_que_cubren(exigidas, 2)
    servicio_grafo.retirar_candidato(CANDIDATA)
    assert servicio_grafo.contar_candidatos_que_cubren(exigidas, 2) == antes - 1
