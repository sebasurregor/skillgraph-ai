"""HU-RF-011 · Publicar vacante con habilidades ponderadas (SA-30)."""
import re
from decimal import Decimal

import pytest
from django.urls import reverse

from vacantes import services
from vacantes.models import RequisitoVacante, Vacante

MENSAJE = "Favor ingresar información válida en los campos obligatorios"
ALERTA_VISIBLE = '<div id="alerta-form" class="alert alert-error" role="alert">'
ERROR_SUMA = "La suma de los pesos debe ser igual a 1.00. Actualmente suma {}."

BODEGA = [("Manejo de inventarios", "0.40", 2, True),
          ("Picking y packing", "0.35", 2, True),
          ("Puntualidad", "0.25", 3, False)]


def datos_post(catalogo, requisitos=BODEGA, accion="publicar", **cambios):
    datos = {
        "accion": accion, "titulo": "Auxiliar de bodega", "empresa": "Logística Express S.A.S.",
        "cargo": "Auxiliar logístico", "area": catalogo["Picking y packing"].areas.first().pk,
        "ciudad": "Medellín", "modalidad": "Presencial", "jornada": "Temporal",
        "salario": "1600000", "descripcion": "Alistamiento de pedidos en temporada.",
        "req-TOTAL_FORMS": str(len(requisitos)), "req-INITIAL_FORMS": "0",
        "req-MIN_NUM_FORMS": "0", "req-MAX_NUM_FORMS": "1000",
    }
    for i, (nombre, peso, nivel, obligatoria) in enumerate(requisitos):
        datos[f"req-{i}-habilidad"] = catalogo[nombre].pk if nombre else ""
        datos[f"req-{i}-peso"] = peso
        datos[f"req-{i}-nivel_minimo"] = nivel
        if obligatoria:
            datos[f"req-{i}-obligatoria"] = "on"
    datos.update(cambios)
    return datos


def etiqueta(html, id_campo):
    return re.search(r'<(?:input|select|textarea)[^>]*\bid="%s"[^>]*>' % id_campo, html).group(0)


@pytest.fixture
def sesion(client, reclutador):
    client.force_login(reclutador)
    return client


@pytest.fixture
def borrador(reclutador, catalogo):
    vacante, _ = services.guardar_vacante(
        reclutador, {"titulo": "Mesero para fines de semana"},
        [{"habilidad": catalogo["Servicio a la mesa"], "peso": Decimal("0.60"),
          "nivel_minimo": 2, "obligatoria": True}],
        publicar=False)
    return vacante


# ---- Criterio 1: varias habilidades con nivel mínimo, peso y obligatoriedad --

def test_rf011_permite_agregar_varias_habilidades_con_nivel_peso_y_obligatoriedad(
        sesion, catalogo):
    respuesta = sesion.post(reverse("vacantes:nueva"), datos_post(catalogo))
    assert respuesta.status_code == 302

    guardados = {r.habilidad.nombre: (str(r.peso), r.nivel_minimo, r.obligatoria)
                 for r in Vacante.objects.get().requisitos.all()}
    assert guardados == {"Manejo de inventarios": ("0.40", 2, True),
                         "Picking y packing": ("0.35", 2, True),
                         "Puntualidad": ("0.25", 3, False)}


def test_rf011_el_formulario_ofrece_agregar_y_quitar_habilidades(sesion, catalogo):
    html = sesion.get(reverse("vacantes:nueva")).content.decode()
    assert 'id="agregar-requisito"' in html
    assert '<template id="fila-vacia">' in html
    for campo in ("habilidad", "peso", "nivel_minimo", "obligatoria"):
        assert f'name="req-__prefix__-{campo}"' in html
    assert "js/vacante_form.js" in html


def test_rf011_el_catalogo_ofrece_habilidades_de_oficios_no_tecnicos(sesion, catalogo):
    html = sesion.get(reverse("vacantes:nueva")).content.decode()
    for habilidad in ("Picking y packing", "Manipulación de alimentos", "Colorimetría",
                      "Curso de vigilancia", "Trabajo en alturas", "Manejo de caja", "Python"):
        assert f">{habilidad}</option>" in html


def test_rf011_no_permite_repetir_una_habilidad(sesion, catalogo):
    repetidas = [("Puntualidad", "0.50", 3, False), ("Puntualidad", "0.50", 4, True)]
    html = sesion.post(reverse("vacantes:nueva"),
                       datos_post(catalogo, repetidas)).content.decode()
    assert not Vacante.objects.exists()
    assert "Cada habilidad solo puede aparecer una vez: Puntualidad." in html


def test_rf011_la_fila_quitada_no_se_guarda(sesion, catalogo):
    filas = BODEGA + [("Excel", "0.90", 1, False)]
    sesion.post(reverse("vacantes:nueva"), datos_post(catalogo, filas, **{"req-3-DELETE": "on"}))
    nombres = set(Vacante.objects.get().requisitos.values_list("habilidad__nombre", flat=True))
    assert nombres == {"Manejo de inventarios", "Picking y packing", "Puntualidad"}


# ---- Criterio 2: la suma de los pesos debe ser 1.00 para publicar ------------

@pytest.mark.parametrize("pesos, suma", [
    (("0.40", "0.35", "0.15"), "0.90"),
    (("0.40", "0.35", "0.30"), "1.05"),
    (("0.40", "0.35", "0.24"), "0.99"),
])
def test_rf011_no_publica_si_los_pesos_no_suman_1(sesion, catalogo, pesos, suma):
    filas = [(n, p, nivel, o) for (n, _, nivel, o), p in zip(BODEGA, pesos)]
    html = sesion.post(reverse("vacantes:nueva"), datos_post(catalogo, filas)).content.decode()

    assert not Vacante.objects.exists()
    assert ERROR_SUMA.format(suma) in html


@pytest.mark.parametrize("pesos", [
    ("0.40", "0.35", "0.25"),
    ("0.10", "0.20", "0.70"),     # en coma flotante 0.1 + 0.2 + 0.7 no da 1.0 exacto
    ("0.33", "0.33", "0.34"),
])
def test_rf011_publica_cuando_los_pesos_suman_exactamente_1(sesion, catalogo, pesos):
    filas = [(n, p, nivel, o) for (n, _, nivel, o), p in zip(BODEGA, pesos)]
    sesion.post(reverse("vacantes:nueva"), datos_post(catalogo, filas))
    vacante = Vacante.objects.get()
    assert vacante.publicada
    assert vacante.suma_pesos == Decimal("1.00")


def test_rf011_el_servicio_tambien_valida_la_suma(reclutador, catalogo):
    requisitos = [{"habilidad": catalogo["Excel"], "peso": Decimal("0.70"),
                   "nivel_minimo": 3, "obligatoria": True}]
    datos = {"titulo": "Auxiliar contable", "empresa": "Grupo Sartor", "descripcion": "x",
             "area": catalogo["Excel"].areas.first(), "ciudad": "Bogotá",
             "modalidad": "Híbrido", "jornada": "Tiempo completo", "salario": 2700000}
    with pytest.raises(services.ErrorDeNegocio) as error:
        services.guardar_vacante(reclutador, datos, requisitos, publicar=True)
    assert error.value.errores == [ERROR_SUMA.format("0.70")]
    assert not Vacante.objects.exists()


def test_rf011_no_publica_sin_habilidades(sesion, catalogo):
    html = sesion.post(reverse("vacantes:nueva"), datos_post(catalogo, [])).content.decode()
    assert not Vacante.objects.exists()
    assert "Agregue al menos una habilidad con su peso antes de publicar." in html


def test_rf011_publicar_un_borrador_desde_la_lista_valida_la_suma(sesion, borrador):
    respuesta = sesion.post(reverse("vacantes:publicar", args=[borrador.pk]), follow=True)
    borrador.refresh_from_db()
    assert not borrador.publicada
    assert respuesta.redirect_chain[-1][0] == reverse("vacantes:editar", args=[borrador.pk])
    assert "No se pudo publicar" in respuesta.content.decode()


def test_rf011_el_formulario_muestra_la_suma_de_pesos_en_vivo(sesion, catalogo):
    html = sesion.get(reverse("vacantes:nueva")).content.decode()
    assert 'id="suma-pesos"' in html
    assert "Los pesos deben sumar exactamente 1.00 para publicar." in html


# ---- Criterio 3: previsualización de candidatos potenciales ------------------

def test_rf011_el_formulario_incluye_la_previsualizacion(sesion, catalogo):
    html = sesion.get(reverse("vacantes:nueva")).content.decode()
    assert 'id="previsualizacion"' in html
    assert f'data-url="{reverse("matching:candidatos_potenciales")}"' in html


# (El cálculo de la previsualización se prueba en matching/tests/test_rf011_previsualizacion.py)


# ---- Criterio 4: guardar como borrador antes de publicar ---------------------

def test_rf011_guarda_borrador_solo_con_el_titulo(sesion, catalogo):
    datos = {"accion": "borrador", "titulo": "Estilista profesional",
             "req-TOTAL_FORMS": "0", "req-INITIAL_FORMS": "0",
             "req-MIN_NUM_FORMS": "0", "req-MAX_NUM_FORMS": "1000"}
    respuesta = sesion.post(reverse("vacantes:nueva"), datos, follow=True)

    vacante = Vacante.objects.get()
    assert vacante.estado == Vacante.Estado.BORRADOR
    assert vacante.publicada_en is None
    assert "Vacante guardada como borrador." in respuesta.content.decode()


def test_rf011_el_borrador_no_exige_que_los_pesos_sumen_1(sesion, catalogo):
    filas = [("Corte de cabello", "0.30", 4, True)]
    sesion.post(reverse("vacantes:nueva"), datos_post(catalogo, filas, accion="borrador"))
    vacante = Vacante.objects.get()
    assert not vacante.publicada
    assert vacante.suma_pesos == Decimal("0.30")


def test_rf011_el_borrador_no_llega_al_grafo(sesion, catalogo, grafo):
    sesion.post(reverse("vacantes:nueva"), datos_post(catalogo, accion="borrador"))
    assert grafo.escrituras_con("REQUIERE") == []


def test_rf011_el_borrador_se_puede_completar_y_publicar_despues(sesion, catalogo, borrador):
    sesion.post(reverse("vacantes:editar", args=[borrador.pk]), datos_post(catalogo))
    borrador.refresh_from_db()
    assert borrador.publicada
    assert borrador.publicada_en is not None
    assert borrador.titulo == "Auxiliar de bodega"
    assert Vacante.objects.count() == 1


def test_rf011_el_formulario_tiene_botones_de_borrador_y_de_publicar(sesion, catalogo):
    html = sesion.get(reverse("vacantes:nueva")).content.decode()
    assert 'name="accion" value="borrador"' in html
    assert 'name="accion" value="publicar"' in html


def test_rf011_publicar_exige_los_datos_de_la_vacante(sesion, catalogo):
    html = sesion.post(reverse("vacantes:nueva"),
                       datos_post(catalogo, ciudad="", salario="")).content.decode()
    assert not Vacante.objects.exists()
    assert "is-invalid" in etiqueta(html, "id_ciudad")
    assert "is-invalid" in etiqueta(html, "id_salario")


# ---- Sincronización con el grafo --------------------------------------------

def test_rf011_publicar_sincroniza_la_vacante_y_sus_requiere_en_neo4j(sesion, catalogo, grafo):
    sesion.post(reverse("vacantes:nueva"), datos_post(catalogo))
    vacante = Vacante.objects.get()
    (_, params), = grafo.escrituras_con("REQUIERE")
    assert params["vacante_id"] == vacante.pk
    assert params["datos"]["estado"] == "publicada"
    assert {"nombre": "Picking y packing", "peso": 0.35, "nivel_min": 2,
            "obligatoria": True} in params["requisitos"]
    assert len(params["requisitos"]) == 3


def test_rf011_despublicar_y_eliminar_retiran_la_vacante_del_grafo(sesion, catalogo, grafo):
    sesion.post(reverse("vacantes:nueva"), datos_post(catalogo))
    pk = Vacante.objects.get().pk
    sesion.post(reverse("vacantes:despublicar", args=[pk]))
    assert grafo.escrituras_con("DETACH DELETE v")[-1][1] == {"vacante_id": pk}
    assert not Vacante.objects.get().publicada


def test_rf011_con_neo4j_caido_publica_igual_y_avisa(sesion, catalogo, grafo_caido, caplog):
    with caplog.at_level("WARNING"):
        respuesta = sesion.post(reverse("vacantes:nueva"), datos_post(catalogo), follow=True)
    html = respuesta.content.decode()

    assert respuesta.status_code == 200
    assert Vacante.objects.get().publicada
    assert "Vacante publicada." in html
    assert "data-aviso-grafo" in html
    assert "El grafo de Neo4j no está disponible" in html
    assert "Neo4j no disponible" in caplog.text


def test_rf011_la_centralidad_refleja_la_demanda_de_las_habilidades(reclutador, catalogo):
    sin_referencia = services.calcular_centralidad([catalogo["Puntualidad"]])
    assert sin_referencia == 0.5

    datos = {"titulo": "Guarda", "empresa": "Vigilancia Antioquia", "descripcion": "x",
             "area": catalogo["Control de acceso"].areas.first(), "ciudad": "Medellín",
             "modalidad": "Presencial", "jornada": "Por turnos", "salario": 1800000}
    services.guardar_vacante(
        reclutador, datos,
        [{"habilidad": catalogo["Puntualidad"], "peso": Decimal("1.00"), "nivel_minimo": 4,
          "obligatoria": True}], publicar=True)

    assert services.calcular_centralidad([catalogo["Puntualidad"]]) == 1.0
    assert services.calcular_centralidad([catalogo["Colorimetría"]]) == 0.5


# ---- Reglas de la sección 4 en el formulario de vacante ----------------------

def test_rf011_regla_mensaje_exacto_resaltado_y_foco(sesion, catalogo):
    html = sesion.post(reverse("vacantes:nueva"),
                       datos_post(catalogo, titulo="", ciudad="")).content.decode()
    assert ALERTA_VISIBLE in html
    assert f"<span>{MENSAJE}</span>" in html
    assert "is-invalid" in etiqueta(html, "id_titulo")
    assert "is-invalid" in etiqueta(html, "id_ciudad")
    assert "autofocus" in etiqueta(html, "id_titulo")
    assert html.count(" autofocus") == 1


def test_rf011_regla_pesos_invalidos_se_resaltan_y_reciben_el_foco(sesion, catalogo):
    filas = [("Puntualidad", "0.50", 3, False), ("Excel", "0.20", 2, False)]
    html = sesion.post(reverse("vacantes:nueva"), datos_post(catalogo, filas)).content.decode()
    assert ALERTA_VISIBLE in html
    assert f"<span>{MENSAJE}</span>" in html
    assert "is-invalid" in etiqueta(html, "id_req-0-peso")
    assert "is-invalid" in etiqueta(html, "id_req-1-peso")
    assert "autofocus" in etiqueta(html, "id_req-0-peso")
    assert html.count(" autofocus") == 1


def test_rf011_regla_fila_incompleta_se_resalta(sesion, catalogo):
    filas = [("Puntualidad", "", 3, False)]
    html = sesion.post(reverse("vacantes:nueva"), datos_post(catalogo, filas)).content.decode()
    assert ALERTA_VISIBLE in html
    assert "is-invalid" in etiqueta(html, "id_req-0-peso")
    assert not RequisitoVacante.objects.exists()


def test_rf011_regla_el_formulario_no_muestra_la_alerta_antes_de_enviar(sesion, catalogo):
    html = sesion.get(reverse("vacantes:nueva")).content.decode()
    assert 'class="alert alert-error hidden" role="alert"' in html
    assert "novalidate data-validar" in html
    assert 'data-validar-solo="#id_titulo"' in html
