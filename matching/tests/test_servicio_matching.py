"""Servicio único de matching: fórmula, grafo y respaldo en SQLite."""
import pytest

from cuentas.models import Usuario
from matching import services
from perfiles import services as perfiles
from vacantes.models import Vacante

BACKEND = [{"nombre": "Python", "peso": 0.30, "nivel_min": 4, "obligatoria": True},
           {"nombre": "Django", "peso": 0.25, "nivel_min": 4, "obligatoria": True},
           {"nombre": "Neo4j / Cypher", "peso": 0.25, "nivel_min": 3, "obligatoria": True},
           {"nombre": "Docker", "peso": 0.12, "nivel_min": 2, "obligatoria": False},
           {"nombre": "Scrum", "peso": 0.08, "nivel_min": 2, "obligatoria": False}]
ANA = {"Python": 5, "Django": 3, "SQL": 4, "Docker": 3, "Git": 5, "Scrum": 3, "Linux": 4}


def perfil_de(correo):
    return Usuario.objects.get(email=correo).perfil


def porcentajes(perfil):
    resultados, aviso = services.calcular_lote([perfil], services.vacantes_publicadas())
    return {Vacante.objects.get(pk=v).titulo: m.pct for (_, v), m in resultados.items()}, aviso


# ---- La fórmula ---------------------------------------------------------------

def test_matching_reproduce_el_ejemplo_del_prototipo_82_por_ciento():
    match = services.calcular_match(ANA, {"Neo4j / Cypher", "AWS"}, BACKEND, 0.91)
    assert match.pct == 82
    assert match.cobertura == pytest.approx(0.75)
    assert match.nivel == pytest.approx(0.6875 / 0.75)
    assert match.centralidad == 0.91
    assert match.adyacencia == pytest.approx(1.0)
    assert match.pct_potencial == 97


def test_matching_separa_habilidades_cubiertas_y_faltantes_con_su_peso():
    match = services.calcular_match(ANA, set(), BACKEND, 0.91)
    assert [(c["nombre"], c["peso"], c["nivel"]) for c in match.cubiertas] == [
        ("Python", 0.30, 5), ("Django", 0.25, 3), ("Docker", 0.12, 3), ("Scrum", 0.08, 3)]
    assert [(f["nombre"], f["peso"], f["nivel_min"]) for f in match.faltantes] == [
        ("Neo4j / Cypher", 0.25, 3)]
    assert [f["nombre"] for f in match.obligatorias_faltantes] == ["Neo4j / Cypher"]
    assert not match.cumple_obligatorias


def test_matching_el_nivel_por_encima_del_minimo_no_suma_de_mas():
    requisito = [{"nombre": "Python", "peso": 1.0, "nivel_min": 2, "obligatoria": False}]
    assert services.calcular_match({"Python": 5}, set(), requisito, 0.5).nivel == 1.0
    assert services.calcular_match({"Python": 1}, set(), requisito, 0.5).nivel == 0.5


def test_matching_la_adyacencia_premia_querer_aprender_lo_que_falta():
    sin_interes = services.calcular_match(ANA, set(), BACKEND, 0.91)
    con_interes = services.calcular_match(ANA, {"Neo4j / Cypher"}, BACKEND, 0.91)
    assert sin_interes.adyacencia == pytest.approx(0.1)
    assert con_interes.adyacencia == pytest.approx(1.0)
    assert con_interes.pct > sin_interes.pct


def test_matching_sin_brechas_ni_habilidades():
    completo = services.calcular_match({r["nombre"]: 5 for r in BACKEND}, set(), BACKEND, 0.91)
    assert completo.faltantes == [] and completo.cumple_obligatorias
    assert completo.adyacencia == 0.9
    assert completo.pct == 99
    assert "No tiene brechas" in completo.texto

    nada = services.calcular_match({}, set(), BACKEND, 0.91)
    assert (nada.cobertura, nada.nivel, nada.cubiertas) == (0.0, 0.0, [])
    assert nada.pct == 10          # solo centralidad y adyacencia mínima


def test_matching_usa_los_pesos_de_la_configuracion(settings):
    antes = services.calcular_match(ANA, set(), BACKEND, 0.91).pct
    settings.W_COBERTURA, settings.W_NIVEL = 0.25, 0.60
    assert services.calcular_match(ANA, set(), BACKEND, 0.91).pct != antes
    assert services.pesos()["cobertura"] == 0.25


def test_matching_redondea_como_el_prototipo():
    assert services._porcentaje(0.825) == 83     # round() de Python daría 82
    assert services._porcentaje(0.8249) == 82


def test_matching_el_texto_explica_la_brecha_principal():
    texto = services.calcular_match(ANA, {"Neo4j / Cypher"}, BACKEND, 0.91).texto
    assert texto.startswith("Usted cubre 4 de las 5 habilidades que exige esta vacante")
    assert "concentran el 75 % del peso" in texto
    assert "Le falta Neo4j / Cypher (peso 0.25, nivel mínimo 3)" in texto
    assert "de 82 % a 97 %" in texto


# ---- Paridad con el prototipo sobre los datos de demostración -----------------

def test_matching_ana_maria_obtiene_82_en_su_mejor_vacante(demo):
    pcts, aviso = porcentajes(perfil_de("ana.rios@correo.com"))
    assert max(pcts.values()) == 82
    assert pcts["Desarrollador Backend Senior"] == 82
    assert aviso == ""


def test_matching_camilo_obtiene_53_en_su_mejor_vacante(demo):
    pcts, _ = porcentajes(perfil_de("camilo.zapata@correo.com"))
    assert max(pcts.values()) == 53
    assert len(pcts) == 16


# ---- Grafo y respaldo ---------------------------------------------------------

def test_matching_lee_los_datos_recorriendo_el_grafo(demo, grafo):
    grafo.lecturas.clear()
    porcentajes(perfil_de("ana.rios@correo.com"))
    consultas = " ".join(c for c, _ in grafo.lecturas)
    assert "MATCH (v:Vacante)-[r:REQUIERE]->(s:Skill)" in consultas
    assert "-[t:TIENE]->(s)" in consultas


def test_matching_el_respaldo_en_sqlite_da_exactamente_el_mismo_resultado(demo, grafo):
    ana, camilo = perfil_de("ana.rios@correo.com"), perfil_de("camilo.zapata@correo.com")
    vacantes = list(services.vacantes_publicadas())
    con_grafo, aviso_grafo = services.calcular_lote([ana, camilo], vacantes)

    grafo.caido = True
    services.servicio_grafo.reiniciar_estado()
    sin_grafo, aviso_respaldo = services.calcular_lote([ana, camilo], vacantes)

    assert len(con_grafo) == 32
    assert {k: m.como_dict() for k, m in con_grafo.items()} == \
           {k: m.como_dict() for k, m in sin_grafo.items()}
    assert aviso_grafo == "" and aviso_respaldo == services.AVISO_RESPALDO


def test_matching_con_neo4j_caido_no_falla_y_lo_registra(demo, grafo_caido, caplog):
    with caplog.at_level("WARNING"):
        pcts, aviso = porcentajes(perfil_de("ana.rios@correo.com"))
    assert max(pcts.values()) == 82
    assert aviso == services.AVISO_RESPALDO
    assert "respaldo en SQLite" in caplog.text


def test_matching_usa_sqlite_para_lo_que_todavia_no_esta_en_el_grafo(demo, grafo):
    """Un perfil confirmado mientras Neo4j estaba caído no existe aún como nodo."""
    ana = perfil_de("ana.rios@correo.com")
    del grafo.candidatos[ana.usuario_id]
    pcts, aviso = porcentajes(ana)
    assert pcts["Desarrollador Backend Senior"] == 82       # no 0 % por faltar el nodo
    assert aviso == services.AVISO_RESPALDO


def test_matching_una_sola_implementacion_del_calculo():
    """HU-RF-005 y HU-RF-013 comparten `calcular_match`; no hay otra fórmula en el proyecto."""
    from pathlib import Path

    from django.conf import settings
    fuentes = [p for app in ("matching", "vacantes", "perfiles", "postulaciones", "cuentas")
               for p in (Path(settings.BASE_DIR) / app).glob("*.py")]
    con_formula = [p.name for p in fuentes if "W_COBERTURA" in p.read_text(encoding="utf-8")]
    assert con_formula == ["services.py"]


def test_matching_match_de_un_par(demo):
    ana = perfil_de("ana.rios@correo.com")
    vacante = Vacante.objects.get(titulo="Ingeniera de datos")
    match, aviso = services.match_de(ana, vacante)
    assert match.pct == 75 and aviso == ""
    assert perfiles.niveles_de(ana)["SQL"] == 4
