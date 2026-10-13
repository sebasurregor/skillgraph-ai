"""HU-RF-013 · Ver postulaciones priorizadas por match (SA-33)."""
import re
from pathlib import Path

import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from cuentas.models import Usuario
from matching import services as matching
from perfiles import services as perfiles
from postulaciones import services
from postulaciones.models import Postulacion
from vacantes.models import Vacante

CV = Path(settings.BASE_DIR) / "docs" / "cv_ejemplo"


@pytest.fixture
def backend(demo):
    return Vacante.objects.get(titulo="Desarrollador Backend Senior")


@pytest.fixture
def crear_candidato(crear_usuario, catalogo):
    def _crear(correo, nombre, niveles, experiencia=""):
        usuario = crear_usuario(correo=correo, nombres=nombre, apellidos="Prueba")
        datos = {"nombre_completo": f"{nombre} Prueba", "correo": correo,
                 "telefono": "3001112233", "experiencia": experiencia, "educacion": "Bachiller"}
        perfiles.confirmar_perfil(perfiles.perfil_de(usuario), datos, niveles)
        return usuario
    return _crear


@pytest.fixture
def postulados(backend, crear_candidato):
    """Cuatro postulados a la vacante de backend, con ajustes bien distintos."""
    ana = Usuario.objects.get(email="ana.rios@correo.com")
    experta = crear_candidato("experta@correo.com", "Elena", {
        "Python": 5, "Django": 5, "Neo4j / Cypher": 4, "Docker": 3, "Scrum": 3},
        experiencia="Ocho años como desarrolladora backend.")
    aprendiz = crear_candidato("aprendiz@correo.com", "Andrés", {"Python": 2, "Scrum": 2})
    camilo = Usuario.objects.get(email="camilo.zapata@correo.com")
    # Se postulan en desorden: el orden de llegada no debe decidir la prioridad.
    for usuario in (camilo, aprendiz, ana, experta):
        services.postular(usuario, backend.pk)
    return {"ana": ana, "experta": experta, "aprendiz": aprendiz, "camilo": camilo}


@pytest.fixture
def sesion(client, backend):
    client.force_login(backend.reclutador)
    return client


def pagina(client, vacante, **params):
    return client.get(reverse("postulaciones:de_vacante", args=[vacante.pk]),
                      params).content.decode()


def orden(html):
    """[(nombre, porcentaje)] en el orden en que aparecen los candidatos."""
    return [(nombre, int(pct)) for pct, nombre in re.findall(
        r'<article class="job" data-postulacion="\d+" data-pct="(\d+)".*?<h3>(.*?)</h3>',
        html, re.S)]


def tarjeta(html, nombre):
    return [t for t in html.split("<article ")[1:] if f"<h3>{nombre}</h3>" in t][0]


# ---- Criterio 1: ordenadas de mayor a menor porcentaje de match ----------------

def test_rf013_lista_las_postulaciones_de_mayor_a_menor_match(sesion, backend, postulados):
    candidatos = orden(pagina(sesion, backend))
    assert [n for n, _ in candidatos] == ["Elena Prueba", "Ana María Ríos Bedoya",
                                          "Andrés Prueba", "Camilo Zapata Ospina"]
    pcts = [p for _, p in candidatos]
    assert pcts == sorted(pcts, reverse=True)
    assert pcts[:2] == [99, 82]


def test_rf013_usa_el_mismo_servicio_de_matching_que_las_recomendaciones(
        backend, postulados):
    ana = postulados["ana"].perfil
    en_recomendaciones = {i["vacante"].pk: i["match"].pct
                          for i in matching.recomendar(ana)["items"]}[backend.pk]
    en_postulaciones = {i["perfil"].pk: i["match"].pct
                        for i in services.priorizadas(backend)["items"]}[ana.pk]
    assert en_recomendaciones == en_postulaciones == 82


def test_rf013_el_orden_se_actualiza_si_el_candidato_mejora_su_perfil(
        sesion, backend, postulados):
    aprendiz = postulados["aprendiz"].perfil
    perfiles.confirmar_perfil(aprendiz, niveles={
        "Python": 5, "Django": 5, "Neo4j / Cypher": 5, "Docker": 5, "Scrum": 5})
    candidatos = orden(pagina(sesion, backend))
    assert candidatos[0][0] in ("Andrés Prueba", "Elena Prueba")
    assert dict(candidatos)["Andrés Prueba"] == 99


def test_rf013_se_llega_desde_la_accion_de_mis_vacantes(sesion, backend, postulados):
    html = sesion.get(reverse("vacantes:lista")).content.decode()
    enlace = reverse("postulaciones:de_vacante", args=[backend.pk])
    assert f'href="{enlace}">Ver postulaciones (4)</a>' in html
    assert html.count("Ver postulaciones (0)") == 15


# ---- Criterio 2: primero las habilidades que hacen match exacto, con su peso ---

def test_rf013_muestra_primero_las_habilidades_que_coinciden_con_su_peso(
        sesion, backend, postulados):
    ana = tarjeta(pagina(sesion, backend), "Ana María Ríos Bedoya")
    coincidencias = ana.split('data-lista="coincidencias"')[1].split("</div>")[0]

    for texto in ("Python · peso 0.30 · nivel 5/4 · obligatoria",
                  "Django · peso 0.25 · nivel 3/4 · obligatoria",
                  "Docker · peso 0.12 · nivel 3/2", "Scrum · peso 0.08 · nivel 3/2"):
        assert texto in coincidencias
    # Solo las que pide la vacante: Git, SQL y Linux no son coincidencias.
    assert "Git" not in coincidencias and "Linux" not in coincidencias
    # Y van de mayor a menor peso.
    pesos = [float(p) for p in re.findall(r"peso (\d\.\d\d)", coincidencias)]
    assert pesos == sorted(pesos, reverse=True)


def test_rf013_las_coincidencias_van_antes_que_cualquier_otra_informacion(
        sesion, backend, postulados):
    ana = tarjeta(pagina(sesion, backend), "Ana María Ríos Bedoya")
    assert ana.index('data-lista="coincidencias"') < ana.index('data-nivel="2"')
    assert ana.index('data-lista="coincidencias"') < ana.index("Datos personales")


def test_rf013_candidato_sin_coincidencias(sesion, backend, postulados):
    camilo = tarjeta(pagina(sesion, backend), "Camilo Zapata Ospina")
    assert "Ninguna habilidad coincide con las requeridas." in camilo


# ---- Criterio 3: señala las obligatorias que le faltan --------------------------

def test_rf013_senala_claramente_las_obligatorias_que_faltan(sesion, backend, postulados):
    ana = tarjeta(pagina(sesion, backend), "Ana María Ríos Bedoya")
    alerta = ana.split("data-alerta-obligatorias")[1].split("</div>")[0]
    assert 'class="alert alert-error" data-alerta-obligatorias' in ana
    assert "Le faltan habilidades obligatorias:" in alerta
    assert "<b>Neo4j / Cypher</b> (peso 0.25)" in alerta
    # Docker y Scrum no son obligatorias: aunque faltaran no irían en la alerta.
    assert "Docker" not in alerta


def test_rf013_senala_las_obligatorias_que_tiene_por_debajo_del_nivel(
        sesion, backend, postulados):
    ana = tarjeta(pagina(sesion, backend), "Ana María Ríos Bedoya")
    assert "Obligatorias por debajo del nivel exigido:" in ana
    assert "<b>Django</b> (nivel 3 de 4)" in ana


def test_rf013_quien_cumple_todo_no_tiene_alerta(sesion, backend, postulados):
    elena = tarjeta(pagina(sesion, backend), "Elena Prueba")
    assert "data-alerta-obligatorias" not in elena
    assert "Cumple todas las habilidades obligatorias." in elena
    assert 'data-cumple="si"' in elena


def test_rf013_lista_todas_las_obligatorias_faltantes(sesion, backend, postulados):
    camilo = tarjeta(pagina(sesion, backend), "Camilo Zapata Ospina")
    for nombre in ("Python", "Django", "Neo4j / Cypher"):
        assert f"<b>{nombre}</b>" in camilo


# ---- Criterio 4: información secundaria en un segundo nivel ---------------------

def test_rf013_la_informacion_secundaria_queda_tras_ver_perfil_completo(
        sesion, backend, postulados):
    elena = tarjeta(pagina(sesion, backend), "Elena Prueba")
    primer_nivel, segundo_nivel = elena.split('<details class="porque" data-nivel="2">')

    assert '<summary class="btn btn-ghost">Ver perfil completo</summary>' in segundo_nivel
    for secundario in ("experta@correo.com", "3001112233",
                       "Ocho años como desarrolladora backend.", "Hoja de vida original",
                       "Todas sus habilidades"):
        assert secundario in segundo_nivel
        assert secundario not in primer_nivel


def test_rf013_el_perfil_completo_permite_descargar_la_hoja_de_vida_original(
        sesion, backend, crear_candidato, client):
    usuario = crear_candidato("con.cv@correo.com", "Valentina", {"Python": 4})
    perfil = usuario.perfil
    contenido = (CV / "cv_harvard.docx").read_bytes()
    hoja = perfiles.procesar_hoja_de_vida(perfil,
                                          SimpleUploadedFile("mi_cv.docx", contenido))
    perfiles.confirmar_perfil(perfil, hoja=hoja)
    postulacion, _ = services.postular(usuario, backend.pk)

    html = pagina(sesion, backend)
    url = reverse("postulaciones:hoja_de_vida", args=[postulacion.pk])
    assert f'href="{url}">Descargar mi_cv.docx</a>' in html

    respuesta = sesion.get(url)
    assert b"".join(respuesta.streaming_content) == contenido
    assert 'filename="mi_cv.docx"' in respuesta["Content-Disposition"]


def test_rf013_sin_archivo_lo_indica_y_no_ofrece_descarga(sesion, backend, postulados):
    elena = tarjeta(pagina(sesion, backend), "Elena Prueba")
    assert "Llenó su perfil a mano; no subió archivo." in elena
    postulacion = Postulacion.objects.get(candidato=postulados["experta"].perfil)
    assert sesion.get(reverse("postulaciones:hoja_de_vida",
                              args=[postulacion.pk])).status_code == 404


def test_rf013_el_perfil_completo_incluye_como_se_calculo_el_match(
        sesion, backend, postulados):
    ana = tarjeta(pagina(sesion, backend), "Ana María Ríos Bedoya")
    segundo_nivel = ana.split('data-nivel="2"')[1]
    assert "Cómo se calculó el 82 %" in segundo_nivel
    assert 'data-componente="cobertura"' in segundo_nivel
    assert "Usted cubre" not in segundo_nivel        # el texto en segunda persona es del candidato


# ---- Criterio 5: filtrar los que cumplen todas las obligatorias -----------------

def test_rf013_permite_filtrar_los_que_cumplen_todas_las_obligatorias(
        sesion, backend, postulados):
    html = pagina(sesion, backend, filtro="obligatorias")
    assert orden(html) == [("Elena Prueba", 99)]
    assert "Cumplen todas las obligatorias (1)" in html
    assert "Todos (4)" in html


def test_rf013_tener_la_habilidad_sin_el_nivel_minimo_no_es_cumplir(backend, postulados):
    """Ana tiene Django, pero en nivel 3 y la vacante exige 4."""
    resultado = services.priorizadas(backend, solo_obligatorias=True)
    nombres = [i["perfil"].nombre_completo for i in resultado["items"]]
    assert "Ana María Ríos Bedoya" not in nombres
    assert (resultado["total"], resultado["cumplen"]) == (4, 1)


def test_rf013_el_filtro_conserva_el_orden_por_match(sesion, backend, postulados):
    perfiles.confirmar_perfil(postulados["ana"].perfil, niveles={
        "Python": 4, "Django": 4, "Neo4j / Cypher": 3})
    candidatos = orden(pagina(sesion, backend, filtro="obligatorias"))
    assert [n for n, _ in candidatos] == ["Elena Prueba", "Ana María Ríos Bedoya"]
    assert candidatos[0][1] > candidatos[1][1]


def test_rf013_filtro_sin_resultados_ofrece_ver_todos(sesion, backend, postulados):
    Postulacion.objects.filter(candidato=postulados["experta"].perfil).delete()
    html = pagina(sesion, backend, filtro="obligatorias")
    assert "Ningún candidato cumple todas las habilidades obligatorias" in html
    assert "Quite el filtro para ver a los 3 postulados." in html


def test_rf013_vacante_sin_postulaciones(sesion, backend):
    html = pagina(sesion, backend)
    assert "Todavía no hay postulaciones" in html


# ---- Estado, acceso y Neo4j caído -----------------------------------------------

def test_rf013_el_reclutador_cambia_el_estado_de_una_postulacion(
        sesion, backend, postulados):
    postulacion = Postulacion.objects.get(candidato=postulados["experta"].perfil)
    respuesta = sesion.post(reverse("postulaciones:cambiar_estado", args=[postulacion.pk]),
                            {"estado": "preseleccionada"}, follow=True)
    postulacion.refresh_from_db()
    assert postulacion.estado == Postulacion.Estado.PRESELECCIONADA
    assert "Estado de la postulación actualizado." in respuesta.content.decode()
    assert '<option value="preseleccionada" selected>' in respuesta.content.decode()


def test_rf013_rechaza_un_estado_que_no_existe(sesion, backend, postulados):
    postulacion = Postulacion.objects.first()
    sesion.post(reverse("postulaciones:cambiar_estado", args=[postulacion.pk]),
                {"estado": "contratado-ya"})
    postulacion.refresh_from_db()
    assert postulacion.estado == Postulacion.Estado.ENVIADA


def test_rf013_un_reclutador_no_ve_postulaciones_de_vacantes_ajenas(
        client, backend, postulados, crear_usuario):
    client.force_login(crear_usuario(correo="otro@correo.com", rol=Usuario.Rol.RECLUTADOR))
    postulacion = Postulacion.objects.first()
    assert client.get(reverse("postulaciones:de_vacante",
                              args=[backend.pk])).status_code == 404
    assert client.get(reverse("postulaciones:hoja_de_vida",
                              args=[postulacion.pk])).status_code == 404
    assert client.post(reverse("postulaciones:cambiar_estado", args=[postulacion.pk]),
                       {"estado": "descartada"}).status_code == 404


def test_rf013_un_candidato_no_ve_a_los_demas_postulados(client, backend, postulados):
    client.force_login(postulados["ana"])
    assert client.get(reverse("postulaciones:de_vacante",
                              args=[backend.pk])).status_code == 403


def test_rf013_con_neo4j_caido_prioriza_igual_y_avisa(sesion, backend, postulados, grafo):
    con_grafo = orden(pagina(sesion, backend))
    grafo.caido = True
    matching.servicio_grafo.reiniciar_estado()
    html = pagina(sesion, backend)
    assert orden(html) == con_grafo
    assert "data-aviso-grafo" in html
