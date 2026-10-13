"""HU-RF-005 · Recomendar vacantes de empleo (SA-14)."""
import re
from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from cuentas.models import Usuario
from matching import services
from perfiles import services as perfiles
from vacantes import services as vacantes
from vacantes.models import Vacante

URL = "recomendaciones:lista"


@pytest.fixture
def ana(demo):
    return Usuario.objects.get(email="ana.rios@correo.com")


@pytest.fixture
def camilo(demo):
    return Usuario.objects.get(email="camilo.zapata@correo.com")


@pytest.fixture
def sesion_ana(client, ana):
    client.force_login(ana)
    return client


def tarjetas(html):
    """[(id de vacante, porcentaje)] en el orden en que aparecen."""
    return [(int(pk), int(pct)) for pk, pct in
            re.findall(r'<article class="job" data-vacante="(\d+)" data-pct="(\d+)">', html)]


def titulos(html):
    return re.findall(r"<h3>(.*?)</h3>", html.split('id="vacantes"')[1])


def pagina(client, **params):
    return client.get(reverse(URL), params).content.decode()


# ---- Criterio 1: lista de vacantes que coinciden con el perfil y preferencias --

def test_rf005_lista_las_vacantes_que_coinciden_con_el_perfil(sesion_ana):
    html = pagina(sesion_ana)
    mostradas = titulos(html)
    assert "Desarrollador Backend Senior" in mostradas
    assert "Ingeniera de datos" in mostradas
    # No comparte ninguna habilidad con estas: no se le recomiendan.
    assert "Estilista profesional" not in mostradas
    assert "Guarda de seguridad" not in mostradas
    assert "no coinciden con su perfil o sus preferencias" in html


def test_rf005_sirve_igual_para_un_perfil_no_tecnico(client, camilo):
    client.force_login(camilo)
    mostradas = titulos(pagina(client))
    assert mostradas[0] == "Asesor comercial de tienda"      # su 53 % del prototipo
    assert "Auxiliar de bodega — temporada navideña" in mostradas
    assert "Mesero para fines de semana" in mostradas
    assert "Desarrollador Backend Senior" not in mostradas


def test_rf005_aplica_las_preferencias_laborales(client, camilo):
    perfiles.guardar_preferencias(camilo.perfil, {"tipos_contrato": ["Temporal", "Por horas"]})
    client.force_login(camilo)
    html = pagina(client)
    assert set(titulos(html)) == {"Auxiliar de bodega — temporada navideña",
                                  "Domiciliario en moto"}
    assert "y con sus preferencias laborales" in html


def test_rf005_permite_ver_todas_las_vacantes(sesion_ana, ana):
    perfiles.guardar_preferencias(ana.perfil, {"cargos": ["Backend Engineer"]})
    assert len(tarjetas(pagina(sesion_ana))) == 1
    html = pagina(sesion_ana, ver="todas")
    assert len(tarjetas(html)) == 16
    assert "Todas las vacantes (16)" in html


def test_rf005_solo_recomienda_vacantes_publicadas(sesion_ana):
    vacantes.despublicar_vacante(Vacante.objects.get(titulo="Ingeniera de datos"))
    assert "Ingeniera de datos" not in titulos(pagina(sesion_ana, ver="todas"))


def test_rf005_sin_coincidencias_ofrece_salidas(sesion_ana, ana):
    perfiles.guardar_preferencias(ana.perfil, {"cargos": ["Estilista"]})
    html = pagina(sesion_ana)
    assert tarjetas(html) == []
    assert "Ninguna vacante coincide con su perfil y sus preferencias" in html
    assert 'href="?ver=todas"' in html


# ---- Criterio 2: filtrar u ordenar por fecha o relevancia ---------------------

def test_rf005_ordena_por_relevancia_de_mayor_a_menor(sesion_ana):
    html = pagina(sesion_ana)
    pcts = [pct for _, pct in tarjetas(html)]
    assert pcts == sorted(pcts, reverse=True)
    assert pcts[0] == 82
    assert titulos(html)[0] == "Desarrollador Backend Senior"


def test_rf005_ordena_por_fecha_de_la_mas_reciente_a_la_mas_antigua(sesion_ana):
    html = pagina(sesion_ana, orden="fecha", ver="todas")
    fechas = [Vacante.objects.get(pk=pk).publicada_en for pk, _ in tarjetas(html)]
    assert fechas == sorted(fechas, reverse=True)
    assert len(fechas) == 16


def test_rf005_la_vacante_recien_publicada_queda_primera_por_fecha(sesion_ana):
    antigua = Vacante.objects.get(titulo="Desarrollador Backend Senior")
    Vacante.objects.filter(pk=antigua.pk).update(publicada_en=timezone.now())
    assert titulos(pagina(sesion_ana, orden="fecha"))[0] == "Desarrollador Backend Senior"
    Vacante.objects.filter(pk=antigua.pk).update(
        publicada_en=timezone.now() - timedelta(days=90))
    assert titulos(pagina(sesion_ana, orden="fecha"))[-1] == "Desarrollador Backend Senior"


def test_rf005_la_pagina_ofrece_el_selector_de_orden(sesion_ana):
    html = pagina(sesion_ana, orden="fecha")
    assert '<option value="relevancia">Mayor ajuste</option>' in html
    assert '<option value="fecha" selected>Más recientes</option>' in html


def test_rf005_un_orden_desconocido_usa_relevancia(sesion_ana):
    assert tarjetas(pagina(sesion_ana, orden="xyz")) == tarjetas(pagina(sesion_ana))


# ---- Criterio 3: se actualizan cuando cambia el perfil o las preferencias -----

def test_rf005_se_actualiza_cuando_cambia_el_perfil(sesion_ana, ana):
    def pct_backend():
        return dict((Vacante.objects.get(pk=pk).titulo, pct)
                    for pk, pct in tarjetas(pagina(sesion_ana)))["Desarrollador Backend Senior"]
    assert pct_backend() == 82

    niveles = perfiles.niveles_de(ana.perfil)
    perfiles.confirmar_perfil(ana.perfil, niveles={**niveles, "Neo4j / Cypher": 4, "Django": 5})
    assert pct_backend() == 99


def test_rf005_aparecen_vacantes_nuevas_al_agregar_habilidades(sesion_ana, ana):
    assert "Estilista profesional" not in titulos(pagina(sesion_ana))
    niveles = perfiles.niveles_de(ana.perfil)
    perfiles.confirmar_perfil(ana.perfil, niveles={**niveles, "Corte de cabello": 4})
    assert "Estilista profesional" in titulos(pagina(sesion_ana))


def test_rf005_se_actualiza_cuando_cambian_las_preferencias(sesion_ana, ana):
    antes = len(tarjetas(pagina(sesion_ana)))
    sesion_ana.post(reverse("perfiles:preferencias"), {"ubicaciones": ["Bogotá"]})
    despues = titulos(pagina(sesion_ana))
    assert 0 < len(despues) < antes
    assert "Ingeniera de datos" in despues
    assert "Desarrollador Backend Senior" not in despues     # es en Medellín

    sesion_ana.post(reverse("perfiles:preferencias"), {})      # quita las preferencias
    assert len(tarjetas(pagina(sesion_ana))) == antes


def test_rf005_se_actualiza_cuando_se_publica_una_vacante(sesion_ana, catalogo):
    reclutador = Usuario.objects.get(rol=Usuario.Rol.RECLUTADOR)
    datos = {"titulo": "Analista SQL", "empresa": "Datos del Sur", "cargo": "Analista",
             "descripcion": "Consultas y reportes.", "ciudad": "Cali", "modalidad": "Remoto",
             "jornada": "Tiempo completo", "salario": 4000000,
             "area": catalogo["SQL"].areas.first()}
    requisitos = [{"habilidad": catalogo["SQL"], "peso": Decimal("1.00"), "nivel_minimo": 3,
                   "obligatoria": True}]
    vacantes.guardar_vacante(reclutador, datos, requisitos, publicar=True)
    assert "Analista SQL" in titulos(pagina(sesion_ana))


# ---- Criterio 4: muestra el porcentaje de coincidencia -------------------------

def test_rf005_muestra_el_porcentaje_de_coincidencia_de_cada_vacante(sesion_ana):
    html = pagina(sesion_ana)
    for _, pct in tarjetas(html):
        assert f">{pct}%</b>" in html
    assert html.count('<div class="ring">') == len(tarjetas(html))
    assert ">82%</b>" in html


def test_rf005_el_porcentaje_es_el_del_servicio_de_matching(sesion_ana, ana):
    resultado = services.recomendar(ana.perfil)
    esperado = [(i["vacante"].pk, i["match"].pct) for i in resultado["items"]]
    assert tarjetas(pagina(sesion_ana)) == esperado


# ---- Criterio 5: explicación del match -----------------------------------------

def explicacion(html, vacante):
    return html.split(f'data-explicacion="{vacante.pk}"')[1].split("</details>")[0]


def test_rf005_cada_vacante_permite_abrir_la_explicacion(sesion_ana):
    html = pagina(sesion_ana)
    assert html.count('<details class="porque">') == len(tarjetas(html))
    assert '<summary class="btn btn-ghost">Ver por qué 82 %</summary>' in html


def test_rf005_la_explicacion_desglosa_los_cuatro_componentes(sesion_ana):
    backend = Vacante.objects.get(titulo="Desarrollador Backend Senior")
    bloque = explicacion(pagina(sesion_ana), backend)
    for clave, nombre, detalle in (
            ("cobertura", "Cobertura ponderada de habilidades", "0.75 × 60 %"),
            ("nivel", "Nivel declarado vs. nivel exigido", "0.92 × 25 %"),
            ("centralidad", "Centralidad del rol en el grafo", "0.91 × 10 %"),
            ("adyacencia", "Afinidad con habilidades adyacentes", "1.00 × 5 %")):
        assert f'data-componente="{clave}"' in bloque
        assert nombre in bloque
        assert detalle in bloque
    assert 'data-componente="final"' in bloque and "82 %" in bloque


def test_rf005_la_explicacion_lista_cubiertas_y_faltantes_con_su_peso(sesion_ana):
    backend = Vacante.objects.get(titulo="Desarrollador Backend Senior")
    bloque = explicacion(pagina(sesion_ana), backend)
    cubiertas = bloque.split('data-lista="cubiertas"')[1].split('data-lista="faltantes"')[0]
    faltantes = bloque.split('data-lista="faltantes"')[1].split('class="mini-graph"')[0]

    assert "Habilidades que cubre (4)" in cubiertas
    for nombre, peso in (("Python", "0.30"), ("Django", "0.25"), ("Docker", "0.12"),
                         ("Scrum", "0.08")):
        assert re.search(rf"{nombre} ✓</span>\s*peso {peso}", cubiertas), nombre
    assert "su nivel 3 de 4 exigido" in cubiertas                  # Django
    assert "Habilidades que le faltan (1)" in faltantes
    assert re.search(r"Neo4j / Cypher · falta</span>\s*peso 0.25 · nivel mínimo 3", faltantes)
    assert "obligatoria" in faltantes


def test_rf005_la_explicacion_incluye_el_subgrafo_y_el_texto(sesion_ana):
    backend = Vacante.objects.get(titulo="Desarrollador Backend Senior")
    bloque = explicacion(pagina(sesion_ana), backend)
    assert bloque.count("<rect") == 5 + 1          # cinco habilidades y la vacante
    assert ":TIENE" in bloque and ":REQUIERE" in bloque
    assert "Usted cubre 4 de las 5 habilidades que exige esta vacante" in bloque
    assert "Cerrar esa brecha llevaría su ajuste de 82 % a 97 %." in bloque
    assert "Versión del algoritmo 1.0.0" in bloque


def test_rf005_api_devuelve_la_explicacion_en_json(sesion_ana):
    backend = Vacante.objects.get(titulo="Desarrollador Backend Senior")
    datos = sesion_ana.get(reverse("matching:explicacion", args=[backend.pk])).json()
    assert datos["pct"] == 82
    assert datos["vacante"]["titulo"] == "Desarrollador Backend Senior"
    assert [c["clave"] for c in datos["componentes"]] == [
        "cobertura", "nivel", "centralidad", "adyacencia"]
    assert datos["pesos"] == {"cobertura": 0.6, "nivel": 0.25, "centralidad": 0.1,
                              "adyacencia": 0.05}
    assert datos["obligatorias_faltantes"] == ["Neo4j / Cypher"]
    assert datos["faltantes"][0]["peso"] == 0.25


def test_rf005_api_solo_para_candidatos_y_vacantes_publicadas(client, sesion_ana, demo):
    borrador = Vacante.objects.get(titulo="Mesero para fines de semana")
    vacantes.despublicar_vacante(borrador)
    assert sesion_ana.get(reverse("matching:explicacion", args=[borrador.pk])).status_code == 404
    client.force_login(Usuario.objects.get(rol=Usuario.Rol.RECLUTADOR))
    otra = Vacante.objects.filter(estado="publicada").first()
    assert client.get(reverse("matching:explicacion", args=[otra.pk])).status_code == 403


# ---- Neo4j caído, acceso y flujo ------------------------------------------------

def test_rf005_con_neo4j_caido_recomienda_igual_y_muestra_un_aviso_discreto(
        sesion_ana, grafo, caplog):
    con_grafo = pagina(sesion_ana)
    assert "data-aviso-grafo" not in con_grafo

    grafo.caido = True
    services.servicio_grafo.reiniciar_estado()
    with caplog.at_level("WARNING"):
        sin_grafo = pagina(sesion_ana)
    assert tarjetas(sin_grafo) == tarjetas(con_grafo)
    assert '<p class="tiny muted" data-aviso-grafo' in sin_grafo
    assert "Cálculo hecho sin el grafo" in sin_grafo
    assert "respaldo en SQLite" in caplog.text


def test_rf005_el_candidato_con_perfil_llega_a_sus_recomendaciones_al_entrar(sesion_ana):
    assert sesion_ana.get("/").url == reverse(URL)


def test_rf003_al_confirmar_el_perfil_se_calcula_el_match_con_las_vacantes(
        client, crear_usuario, demo, catalogo):
    """Cierra el criterio de HU-RF-003: perfil creado → porcentaje de match automático."""
    nueva = crear_usuario(correo="valentina@correo.com", nombres="Valentina")
    client.force_login(nueva)
    datos = {"nombre_completo": "Valentina Restrepo", "correo": "valentina@correo.com",
             "telefono": "3205557788",
             "habilidades": [catalogo[n].pk for n in ("Corte de cabello", "Colorimetría")],
             f"nivel_{catalogo['Corte de cabello'].pk}": 5,
             f"nivel_{catalogo['Colorimetría'].pk}": 4}
    client.post(reverse("perfiles:confirmar_manual"), datos)

    html = client.get("/", follow=True).content.decode()
    assert titulos(html) == ["Estilista profesional"]
    assert tarjetas(html)[0][1] == 66


def test_rf005_solo_para_candidatos(client, demo):
    client.force_login(Usuario.objects.get(rol=Usuario.Rol.RECLUTADOR))
    assert client.get(reverse(URL)).status_code == 403
