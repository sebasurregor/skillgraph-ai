"""Servicio de grafo: modelo en Neo4j y tolerancia a la caída del servidor."""
import pytest

from GraphCore import servicio_grafo
from GraphCore.servicio_grafo import GrafoNoDisponible

REQUISITOS = [{"nombre": "Picking y packing", "peso": 0.6, "nivel_min": 2, "obligatoria": True},
              {"nombre": "Puntualidad", "peso": 0.4, "nivel_min": 3, "obligatoria": False}]


def test_grafo_vacante_se_modela_con_requiere_y_sus_propiedades(grafo):
    assert servicio_grafo.sincronizar_vacante(7, {"titulo": "Auxiliar"}, REQUISITOS) is True
    cypher, params = grafo.escrituras[-1]
    assert "MERGE (v:Vacante {vacante_id: $vacante_id})" in cypher
    assert "MERGE (v)-[r:REQUIERE]->(s)" in cypher
    for propiedad in ("r.peso", "r.nivel_min", "r.obligatoria"):
        assert propiedad in cypher
    assert params["vacante_id"] == 7
    assert params["requisitos"] == REQUISITOS


def test_grafo_candidato_se_modela_con_tiene_y_su_nivel(grafo):
    habilidades = [{"nombre": "Puntualidad", "nivel": 5}]
    assert servicio_grafo.sincronizar_candidato(3, {"titular": "Camilo"}, habilidades) is True
    cypher, params = grafo.escrituras[-1]
    assert "MERGE (c:Candidato {usuario_id: $usuario_id})" in cypher
    assert "MERGE (c)-[t:TIENE]->(s)" in cypher
    assert "t.nivel = h.nivel" in cypher
    assert params == {"usuario_id": 3, "datos": {"titular": "Camilo"}, "habilidades": habilidades}


def test_grafo_respeta_las_claves_unicas_de_init_graph(grafo):
    """Los nodos se crean con MERGE sobre la propiedad que init_graph declara única."""
    servicio_grafo.sincronizar_habilidades([{"nombre": "Excel", "categoria": "Transversal"}])
    servicio_grafo.sincronizar_vacante(1, {}, REQUISITOS)
    servicio_grafo.sincronizar_candidato(1, {}, [])
    todo = " ".join(c for c, _ in grafo.escrituras)
    assert "CREATE" not in todo
    assert todo.count("MERGE (s:Skill {nombre:") == 3


def test_grafo_sincronizar_reemplaza_las_aristas_anteriores(grafo):
    servicio_grafo.sincronizar_vacante(1, {}, REQUISITOS)
    servicio_grafo.sincronizar_candidato(1, {}, [])
    assert "OPTIONAL MATCH (v)-[anterior:REQUIERE]->(:Skill)" in grafo.escrituras[0][0]
    assert "OPTIONAL MATCH (c)-[anterior:TIENE]->(:Skill)" in grafo.escrituras[1][0]


def test_grafo_retirar_vacante_la_borra_del_grafo(grafo):
    assert servicio_grafo.retirar_vacante(9) is True
    cypher, params = grafo.escrituras[-1]
    assert "DETACH DELETE v" in cypher and params == {"vacante_id": 9}


def test_grafo_caido_las_escrituras_devuelven_false_sin_lanzar_error(grafo_caido):
    assert servicio_grafo.sincronizar_vacante(1, {}, REQUISITOS) is False
    assert servicio_grafo.sincronizar_candidato(1, {}, []) is False
    assert servicio_grafo.retirar_vacante(1) is False
    assert servicio_grafo.sincronizar_habilidades([]) is False


def test_grafo_caido_las_lecturas_avisan_para_usar_el_respaldo(grafo_caido):
    with pytest.raises(GrafoNoDisponible):
        servicio_grafo.contar_candidatos_que_cubren([{"nombre": "Excel", "nivel_min": 1}], 1)


def test_grafo_caido_se_registra_en_el_log_una_sola_vez(grafo_caido, caplog):
    with caplog.at_level("WARNING"):
        servicio_grafo.retirar_vacante(1)
        servicio_grafo.retirar_vacante(2)
    avisos = [r for r in caplog.records if "Neo4j no disponible" in r.getMessage()]
    assert len(avisos) == 1


def test_grafo_no_vuelve_a_comprobar_la_conexion_en_cada_operacion(grafo, monkeypatch):
    comprobaciones = []
    original = grafo.verify
    monkeypatch.setattr("GraphCore.servicio_grafo.Neo4jConnection.verify",
                        lambda: comprobaciones.append(1) or original())
    servicio_grafo.retirar_vacante(1)
    servicio_grafo.retirar_vacante(2)
    assert len(comprobaciones) == 1


def test_grafo_falla_a_mitad_de_operacion_tambien_se_tolera(grafo):
    assert servicio_grafo.disponible() is True
    grafo.caido = True    # se cae después de la comprobación
    assert servicio_grafo.retirar_vacante(1) is False
    assert servicio_grafo.disponible() is False


def test_grafo_cuenta_candidatos_que_cubren_las_habilidades(grafo):
    grafo.respuesta_lectura = [{"total": 4}]
    exigidas = [{"nombre": "Excel", "nivel_min": 2}]
    assert servicio_grafo.contar_candidatos_que_cubren(exigidas, 1) == 4
    cypher, params = grafo.lecturas[-1]
    assert "(c:Candidato)-[t:TIENE]->(:Skill {nombre: q.nombre})" in cypher
    assert "t.nivel >= q.nivel_min" in cypher
    assert params == {"exigidas": exigidas, "minimo": 1}
