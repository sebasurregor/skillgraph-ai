"""HU-RF-004 · Indicar preferencias laborales (SA-13)."""
import re
from io import StringIO

import pytest
from django.core.management import call_command
from django.urls import reverse

from matching import services as matching
from perfiles import services
from perfiles.models import PreferenciaLaboral
from vacantes.models import Vacante

URL = "perfiles:preferencias"
MENSAJE = "Favor ingresar información válida en los campos obligatorios"
ALERTA_VISIBLE = '<div id="alerta-form" class="alert alert-error" role="alert">'


def etiqueta(html, id_campo):
    return re.search(r'<(?:input|select|textarea)[^>]*\bid="%s"[^>]*>' % id_campo, html).group(0)


@pytest.fixture
def demo(db):
    """Las 16 vacantes de demostración y sus candidatos."""
    call_command("cargar_datos_demo", stdout=StringIO())


@pytest.fixture
def candidato(crear_usuario, demo):
    """Un candidato distinto de los de demostración."""
    return crear_usuario(correo="rosa.cuesta@correo.com", nombres="Rosa", apellidos="Cuesta")


@pytest.fixture
def sesion(client, candidato):
    services.confirmar_perfil(services.perfil_de(candidato))
    client.force_login(candidato)
    return client


def titulos(vacantes):
    return set(vacantes.values_list("titulo", flat=True))


def publicadas():
    return Vacante.objects.filter(estado=Vacante.Estado.PUBLICADA)


# ---- Criterio 1: múltiples cargos, ubicaciones y tipos de contrato -------------

def test_rf004_permite_seleccionar_multiples_cargos_ubicaciones_y_contratos(sesion, candidato):
    datos = {"cargos": ["Auxiliar logístico", "Mesero", "Guarda de seguridad"],
             "ubicaciones": ["Medellín", "Bogotá"],
             "tipos_contrato": ["Temporal", "Por turnos", "Medio tiempo"]}
    respuesta = sesion.post(reverse(URL), datos, follow=True)

    preferencias = PreferenciaLaboral.objects.get(perfil__usuario=candidato)
    assert preferencias.cargos == datos["cargos"]
    assert preferencias.ubicaciones == datos["ubicaciones"]
    assert preferencias.tipos_contrato == datos["tipos_contrato"]
    assert "Preferencias guardadas." in respuesta.content.decode()


def test_rf004_ofrece_cargos_de_oficios_no_tecnicos_y_tecnicos(sesion):
    html = sesion.get(reverse(URL)).content.decode()
    for cargo in ("Auxiliar logístico", "Mesero", "Estilista", "Guarda de seguridad",
                  "Oficial eléctrico", "Asesor comercial", "Backend Engineer"):
        assert f'name="cargos" value="{cargo}"' in html
    assert html.count('type="checkbox" name="cargos"') >= 15
    for ubicacion in ("Medellín", "Bogotá", "Remoto"):
        assert f'name="ubicaciones" value="{ubicacion}"' in html
    for contrato in ("Tiempo completo", "Temporal", "Por horas"):
        assert f'name="tipos_contrato" value="{contrato}"' in html


def test_rf004_rechaza_opciones_que_no_existen(sesion):
    sesion.post(reverse(URL), {"cargos": ["Astronauta"]})
    assert not PreferenciaLaboral.objects.exists()


# ---- Criterio 2: rango salarial esperado ---------------------------------------

def test_rf004_permite_establecer_un_rango_salarial(sesion):
    sesion.post(reverse(URL), {"salario_min": "1500000", "salario_max": "2500000"})
    preferencias = PreferenciaLaboral.objects.get()
    assert (preferencias.salario_min, preferencias.salario_max) == (1500000, 2500000)


def test_rf004_el_rango_puede_tener_solo_minimo_o_quedar_vacio(sesion):
    sesion.post(reverse(URL), {"salario_min": "1400000"})
    preferencias = PreferenciaLaboral.objects.get()
    assert (preferencias.salario_min, preferencias.salario_max) == (1400000, None)


def test_rf004_regla_rango_invalido_mensaje_exacto_resaltado_y_foco(sesion):
    html = sesion.post(reverse(URL), {"salario_min": "3000000", "salario_max": "2000000",
                                      "cargos": ["Mesero"]}).content.decode()
    assert not PreferenciaLaboral.objects.exists()
    assert ALERTA_VISIBLE in html
    assert f"<span>{MENSAJE}</span>" in html
    assert "El salario máximo no puede ser menor que el mínimo." in html
    campo = etiqueta(html, "id_salario_max")
    assert "is-invalid" in campo and "autofocus" in campo
    assert html.count(" autofocus") == 1
    assert 'name="cargos" value="Mesero"' in html and "checked" in html   # conserva lo marcado


def test_rf004_regla_salario_negativo_o_no_numerico(sesion):
    for valor in ("-5", "mucho"):
        html = sesion.post(reverse(URL), {"salario_min": valor}).content.decode()
        assert ALERTA_VISIBLE in html
        assert "is-invalid" in etiqueta(html, "id_salario_min")


# ---- Criterio 3: se guardan y se usan para filtrar las recomendaciones ---------

def test_rf004_sin_preferencias_no_se_filtra_nada(demo):
    assert matching.filtrar_por_preferencias(publicadas(), None).count() == 16
    assert matching.filtrar_por_preferencias(publicadas(), PreferenciaLaboral()).count() == 16


def test_rf004_filtra_por_cargos(demo):
    preferencias = PreferenciaLaboral(cargos=["Mesero", "Estilista"])
    assert titulos(matching.filtrar_por_preferencias(publicadas(), preferencias)) == {
        "Mesero para fines de semana", "Estilista profesional"}


def test_rf004_filtra_por_ubicaciones(demo):
    preferencias = PreferenciaLaboral(ubicaciones=["Bogotá"])
    resultado = matching.filtrar_por_preferencias(publicadas(), preferencias)
    assert set(resultado.values_list("ciudad", flat=True)) == {"Bogotá"}
    assert resultado.count() == 3


def test_rf004_la_ubicacion_remoto_incluye_las_vacantes_remotas(demo):
    preferencias = PreferenciaLaboral(ubicaciones=["Remoto"])
    assert titulos(matching.filtrar_por_preferencias(publicadas(), preferencias)) == {
        "Community manager", "Ingeniera de datos"}


def test_rf004_filtra_por_tipos_de_contrato(demo):
    preferencias = PreferenciaLaboral(tipos_contrato=["Temporal", "Por horas"])
    assert titulos(matching.filtrar_por_preferencias(publicadas(), preferencias)) == {
        "Auxiliar de bodega — temporada navideña", "Domiciliario en moto"}


def test_rf004_filtra_por_salario_minimo_y_no_descarta_las_que_pagan_mas(demo):
    preferencias = PreferenciaLaboral(salario_min=2500000, salario_max=3000000)
    resultado = matching.filtrar_por_preferencias(publicadas(), preferencias)
    assert min(resultado.values_list("salario", flat=True)) >= 2500000
    assert "Desarrollador Backend Senior" in titulos(resultado)      # paga más del máximo


def test_rf004_combina_todas_las_preferencias(demo):
    preferencias = PreferenciaLaboral(ubicaciones=["Medellín"], tipos_contrato=["Por turnos"],
                                      salario_min=1800000)
    assert titulos(matching.filtrar_por_preferencias(publicadas(), preferencias)) == {
        "Auxiliar de enfermería", "Guarda de seguridad", "Recepcionista de hotel"}


def test_rf004_las_preferencias_guardadas_son_las_que_filtran(sesion, candidato):
    sesion.post(reverse(URL), {"cargos": ["Mesero"]})
    guardadas = services.preferencias_de(candidato.perfil)
    assert titulos(matching.filtrar_por_preferencias(publicadas(), guardadas)) == {
        "Mesero para fines de semana"}


# ---- Criterio 4: editar o actualizar en cualquier momento ----------------------

def test_rf004_el_formulario_viene_con_las_preferencias_actuales(sesion):
    sesion.post(reverse(URL), {"cargos": ["Mesero"], "ubicaciones": ["Medellín"],
                               "salario_min": "1500000"})
    html = sesion.get(reverse(URL)).content.decode()
    assert re.search(r'name="cargos" value="Mesero"[^>]*checked', html)
    assert re.search(r'name="ubicaciones" value="Medellín"[^>]*checked', html)
    assert not re.search(r'name="cargos" value="Estilista"[^>]*checked', html)
    assert 'value="1500000"' in etiqueta(html, "id_salario_min")


def test_rf004_permite_actualizar_las_preferencias(sesion):
    sesion.post(reverse(URL), {"cargos": ["Mesero"], "salario_min": "1500000"})
    sesion.post(reverse(URL), {"cargos": ["Estilista", "Docente"], "ubicaciones": ["Remoto"]})

    preferencias = PreferenciaLaboral.objects.get()        # sigue siendo un solo registro
    assert preferencias.cargos == ["Estilista", "Docente"]
    assert preferencias.ubicaciones == ["Remoto"]
    assert preferencias.salario_min is None                # lo desmarcado se quita


def test_rf004_se_llega_a_preferencias_desde_el_perfil_y_la_barra(sesion):
    sesion.post(reverse(URL), {"cargos": ["Mesero"], "salario_min": "1500000"})
    html = sesion.get(reverse("perfiles:mi_perfil")).content.decode()
    assert html.count(reverse(URL)) >= 2
    assert "<b>Cargos:</b> Mesero" in html
    assert "desde $1.500.000" in html


def test_rf004_tras_confirmar_el_perfil_por_primera_vez_se_piden_las_preferencias(
        client, crear_usuario, demo, catalogo):
    nuevo = crear_usuario(correo="nueva@correo.com")
    client.force_login(nuevo)
    datos = {"nombre_completo": "Rosa Cuesta", "correo": "nueva@correo.com",
             "telefono": "3001112233", "habilidades": [catalogo["Puntualidad"].pk]}
    respuesta = client.post(reverse("perfiles:confirmar_manual"), datos, follow=True)
    assert respuesta.redirect_chain[-1][0] == reverse(URL)
    assert 'id="omitir-preferencias"' in respuesta.content.decode()

    client.post(reverse(URL), {"cargos": ["Mesero"]})
    respuesta = client.post(reverse("perfiles:confirmar_manual"), datos, follow=True)
    assert respuesta.redirect_chain[-1][0] != reverse(URL)      # ya no se le vuelve a pedir


def test_rf004_guarda_las_habilidades_que_quiere_aprender(sesion, candidato, catalogo):
    sesion.post(reverse(URL), {"por_aprender": [catalogo["Manejo de inventarios"].pk,
                                                catalogo["Manejo de caja"].pk]})
    assert set(candidato.perfil.por_aprender.values_list("nombre", flat=True)) == {
        "Manejo de inventarios", "Manejo de caja"}
    html = sesion.get(reverse(URL)).content.decode()
    assert re.search(r'name="por_aprender" value="%d" checked' % catalogo["Manejo de caja"].pk,
                     html)


def test_rf004_solo_el_candidato_tiene_preferencias(client, reclutador):
    client.force_login(reclutador)
    assert client.get(reverse(URL)).status_code == 403
