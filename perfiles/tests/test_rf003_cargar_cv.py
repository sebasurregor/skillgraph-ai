"""HU-RF-003 · Cargar la hoja de vida, confirmar y guardar el perfil (SA-12)."""
import re
from pathlib import Path

import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from conftest import CLAVE
from perfiles import services
from perfiles.extraccion import extractor
from perfiles.models import HojaDeVida, PerfilCandidato, VersionPerfil

CV = Path(settings.BASE_DIR) / "docs" / "cv_ejemplo"
MENSAJE = "Favor ingresar información válida en los campos obligatorios"
ALERTA_VISIBLE = '<div id="alerta-form" class="alert alert-error" role="alert">'
URL_CARGA = "perfiles:cargar_cv"


def archivo(nombre, contenido=None, como=None):
    contenido = (CV / nombre).read_bytes() if contenido is None else contenido
    return SimpleUploadedFile(como or nombre, contenido)


def etiqueta(html, id_campo):
    return re.search(r'<(?:input|select|textarea)[^>]*\bid="%s"[^>]*>' % id_campo, html).group(0)


@pytest.fixture
def sesion(client, candidato, catalogo):
    client.force_login(candidato)
    return client


def subir(sesion, nombre="cv_plano.pdf", **kwargs):
    return sesion.post(reverse(URL_CARGA), {"archivo": archivo(nombre, **kwargs)}, follow=True)


def datos_confirmacion(catalogo, niveles, **cambios):
    datos = {"nombre_completo": "Camilo Zapata Ospina", "correo": "camilo.zapata@correo.com",
             "telefono": "3109876543", "experiencia": "Auxiliar de cargue", "educacion": "",
             "habilidades": [catalogo[n].pk for n in niveles]}
    datos.update({f"nivel_{catalogo[n].pk}": nivel for n, nivel in niveles.items()})
    datos.update(cambios)
    return datos


# ---- Criterio 1: acepta PDF y Word de hasta 5 MB, rechaza lo demás ------------

@pytest.mark.parametrize("nombre", ["cv_plano.pdf", "cv_harvard.docx"])
def test_rf003_acepta_pdf_y_word(sesion, nombre):
    respuesta = subir(sesion, nombre)
    hoja = HojaDeVida.objects.get()
    assert hoja.formato == nombre.rsplit(".", 1)[-1]
    assert hoja.nombre_original == nombre
    assert Path(hoja.archivo.path).read_bytes() == (CV / nombre).read_bytes()
    assert respuesta.redirect_chain[-1][0] == reverse("perfiles:confirmar_cv", args=[hoja.pk])


@pytest.mark.parametrize("nombre, contenido", [
    ("hoja_de_vida.txt", b"Nombre: Camilo"),
    ("hoja_de_vida.doc", b"\xd0\xcf\x11\xe0 formato antiguo de Word"),
    ("foto_cv.jpg", b"\xff\xd8\xff\xe0 imagen"),
    ("sin_extension", b"%PDF-1.4"),
    ("disfrazado.pdf", b"MZ esto es un ejecutable renombrado"),
])
def test_rf003_rechaza_otros_formatos_con_mensaje_claro(sesion, nombre, contenido):
    html = subir(sesion, contenido=contenido, como=nombre).content.decode()
    assert not HojaDeVida.objects.exists()
    assert "Formato no admitido. Suba su hoja de vida en PDF o en Word (.docx)." in html
    assert "data-error-archivo" in html


def test_rf003_rechaza_archivo_mayor_a_5mb(sesion):
    grande = b"%PDF-1.4\n" + b"0" * (5 * 1024 * 1024 + 1)
    html = subir(sesion, contenido=grande, como="pesado.pdf").content.decode()
    assert not HojaDeVida.objects.exists()
    assert "El archivo pesa 5.0 MB y el máximo permitido es 5 MB." in html


def test_rf003_acepta_archivo_de_exactamente_5mb(sesion):
    base = (CV / "cv_plano.pdf").read_bytes()
    justo = base + b"\n" * (5 * 1024 * 1024 - len(base))
    subir(sesion, contenido=justo, como="justo.pdf")
    assert HojaDeVida.objects.get().tamano == 5 * 1024 * 1024


def test_rf003_regla_archivo_faltante_o_invalido_mensaje_resaltado_y_foco(sesion):
    for datos in ({}, {"archivo": archivo("x.txt", contenido=b"hola", como="x.txt")}):
        html = sesion.post(reverse(URL_CARGA), datos).content.decode()
        assert ALERTA_VISIBLE in html
        assert f"<span>{MENSAJE}</span>" in html
        campo = etiqueta(html, "id_archivo")
        assert "is-invalid" in campo and "autofocus" in campo
        assert '<div class="drop is-invalid">' in html


def test_rf003_la_pantalla_de_carga_indica_formatos_y_tamano(sesion):
    html = sesion.get(reverse(URL_CARGA)).content.decode()
    assert "PDF o Word (.docx) · máximo 5 MB" in html
    assert 'enctype="multipart/form-data" novalidate data-validar' in html
    assert 'accept=".pdf,.docx' in html


# ---- Criterio 8: flujo resume-first -------------------------------------------

def test_rf003_tras_registrarse_lo_primero_es_subir_la_hoja_de_vida(client, catalogo):
    registro = {"rol": "candidato", "nombres": "Rosa", "apellidos": "Cuesta",
                "correo": "rosa@correo.com", "telefono": "3001112233", "ciudad": "Cali",
                "empresa": "", "clave": CLAVE, "clave2": CLAVE, "acepta_datos": "on"}
    client.post(reverse("cuentas:registro"), registro)
    respuesta = client.post(reverse("cuentas:ingresar_clave"), {"clave": CLAVE}, follow=True)

    assert respuesta.redirect_chain[-1][0] == reverse(URL_CARGA)
    html = respuesta.content.decode()
    assert "Empiece por su hoja de vida" in html
    assert 'type="file"' in html


def test_rf003_el_formulario_manual_es_secundario(sesion):
    html = sesion.get(reverse(URL_CARGA)).content.decode()
    # Acción principal: subir. El formulario manual es un enlace discreto.
    assert '<button class="btn btn-accent" type="submit">Subir y leer mi hoja de vida' in html
    assert f'<a class="btn btn-quiet" href="{reverse("perfiles:confirmar_manual")}"' in html


def test_rf003_candidato_con_perfil_confirmado_ya_no_es_enviado_a_la_carga(sesion, candidato):
    assert sesion.get("/").url == reverse(URL_CARGA)
    services.confirmar_perfil(services.perfil_de(candidato))
    assert sesion.get("/").url != reverse(URL_CARGA)


# ---- Criterio 5: formulario precargado, resalta lo que no se extrajo ----------

def test_rf003_muestra_los_datos_extraidos_en_un_formulario_precargado(sesion, catalogo):
    html = subir(sesion, "cv_plano.pdf").content.decode()
    assert 'value="Camilo Zapata Ospina"' in etiqueta(html, "id_nombre_completo")
    assert 'value="camilo.zapata@correo.com"' in etiqueta(html, "id_correo")
    assert 'value="3109876543"' in etiqueta(html, "id_telefono")
    assert "Auxiliar de cargue - Distribuidora El Paisa" in html
    assert "Bachiller académico" in html
    for nombre in ("Carga y descarga", "Puntualidad", "Trabajo en equipo"):
        assert f'name="habilidades" value="{catalogo[nombre].pk}" checked' in html
    assert f'name="habilidades" value="{catalogo["Python"].pk}" checked' not in html


def test_rf003_precarga_el_nivel_detectado(sesion, catalogo):
    html = subir(sesion, "cv_dos_columnas.pdf").content.decode()
    pk = catalogo["Corte de cabello"].pk
    selector = html.split(f'<select name="nivel_{pk}"')[1].split("</select>")[0]
    assert '<option value="5" selected>' in selector


def test_rf003_resalta_los_campos_que_no_se_pudieron_extraer(sesion):
    # Una hoja de vida de la que solo se pudo leer el nombre y el correo.
    texto = "Mariana Lopera Gil\nmariana@correo.com\nBusco empleo en lo que resulte."
    subir(sesion)
    hoja = HojaDeVida.objects.get()
    hoja.datos_extraidos = extractor.extraer(texto, []).como_dict()
    hoja.save()

    html = sesion.get(reverse("perfiles:confirmar_cv", args=[hoja.pk])).content.decode()
    assert "sin-extraer" not in etiqueta(html, "id_nombre_completo")
    assert "sin-extraer" not in etiqueta(html, "id_correo")
    for id_campo in ("id_telefono", "id_experiencia", "id_educacion"):
        assert "sin-extraer" in etiqueta(html, id_campo), id_campo
    assert 'data-sin-extraer="habilidades"' in html
    assert "No pudimos leer este dato en su hoja de vida." in html


def test_rf003_hoja_completa_no_resalta_nada(sesion):
    html = subir(sesion, "cv_diseno.pdf").content.decode()
    assert 'class="input sin-extraer"' not in html
    assert "data-sin-extraer" not in html


# ---- Criterio 6: información insuficiente → avisa y permite llenar a mano -----

def test_rf003_hoja_escaneada_avisa_y_permite_completar_manualmente(sesion, catalogo):
    respuesta = subir(sesion, "cv_escaneado.pdf")
    html = respuesta.content.decode()
    hoja = HojaDeVida.objects.get()

    assert not hoja.suficiente
    assert respuesta.redirect_chain[-1][0] == reverse("perfiles:confirmar_cv", args=[hoja.pk])
    assert "No logramos extraer información suficiente de su hoja de vida." in html
    assert "Complete sus datos manualmente." in html
    assert "sin-extraer" in etiqueta(html, "id_nombre_completo")

    datos = datos_confirmacion(catalogo, {"Puntualidad": 5})
    sesion.post(reverse("perfiles:confirmar_cv", args=[hoja.pk]), datos)
    assert PerfilCandidato.objects.get().confirmado


def test_rf003_archivo_danado_tambien_permite_completar_manualmente(sesion):
    respuesta = subir(sesion, contenido=b"%PDF-1.4 contenido corrupto", como="roto.pdf")
    assert HojaDeVida.objects.get().suficiente is False
    assert "No logramos extraer información suficiente" in respuesta.content.decode()


# ---- Criterios 4 y 7: crear el perfil y guardar la versión válida -------------

def test_rf003_confirmar_crea_el_perfil_con_los_datos_corregidos(sesion, catalogo, candidato):
    subir(sesion, "cv_plano.pdf")
    hoja = HojaDeVida.objects.get()
    assert not candidato.perfil.confirmado            # subir no modifica el perfil

    datos = datos_confirmacion(catalogo, {"Carga y descarga": 4, "Puntualidad": 5},
                               telefono="3000000000")
    respuesta = sesion.post(reverse("perfiles:confirmar_cv", args=[hoja.pk]), datos,
                            follow=True)

    perfil = PerfilCandidato.objects.get(usuario=candidato)
    assert perfil.confirmado
    assert perfil.telefono == "3000000000"             # la corrección del candidato manda
    assert services.niveles_de(perfil) == {"Carga y descarga": 4, "Puntualidad": 5}
    assert "Perfil confirmado. Guardamos la versión 1" in respuesta.content.decode()


def test_rf003_guarda_la_informacion_confirmada_como_version_valida(sesion, catalogo):
    subir(sesion, "cv_plano.pdf")
    hoja = HojaDeVida.objects.get()
    sesion.post(reverse("perfiles:confirmar_cv", args=[hoja.pk]),
                datos_confirmacion(catalogo, {"Puntualidad": 5}))

    version = VersionPerfil.objects.get()
    assert (version.numero, version.origen, version.hoja_de_vida) == (1, "cv", hoja)
    assert version.datos["nombre_completo"] == "Camilo Zapata Ospina"
    assert version.datos["habilidades"] == {"Puntualidad": 5}


def test_rf003_cada_confirmacion_crea_una_version_y_la_ultima_es_la_valida(
        sesion, catalogo, candidato):
    sesion.post(reverse("perfiles:confirmar_manual"),
                datos_confirmacion(catalogo, {"Puntualidad": 5}))
    sesion.post(reverse("perfiles:confirmar_manual"),
                datos_confirmacion(catalogo, {"Puntualidad": 5, "Excel": 2}))

    perfil = candidato.perfil
    assert [v.numero for v in perfil.versiones.all()] == [2, 1]
    vigente = services.version_vigente(perfil)
    assert vigente.origen == "manual"
    assert vigente.datos["habilidades"] == {"Excel": 2, "Puntualidad": 5}
    html = sesion.get(reverse("perfiles:mi_perfil")).content.decode()
    assert "Versión 2 confirmada" in html
    assert html.count('<span class="tag tag-ok">Válida</span>') == 1


def test_rf003_confirmar_sincroniza_al_candidato_en_el_grafo(sesion, catalogo, candidato, grafo):
    sesion.post(reverse("perfiles:confirmar_manual"),
                datos_confirmacion(catalogo, {"Carga y descarga": 4}))
    (_, params), = grafo.escrituras_con("MERGE (c)-[t:TIENE]->(s)")
    assert params["usuario_id"] == candidato.pk
    assert params["habilidades"] == [{"nombre": "Carga y descarga", "nivel": 4}]


def test_rf003_con_neo4j_caido_el_perfil_se_guarda_y_avisa(sesion, catalogo, grafo_caido):
    respuesta = sesion.post(reverse("perfiles:confirmar_manual"),
                            datos_confirmacion(catalogo, {"Puntualidad": 5}), follow=True)
    assert PerfilCandidato.objects.get().confirmado
    assert "data-aviso-grafo" in respuesta.content.decode()


def test_rf003_formulario_manual_parte_de_los_datos_de_la_cuenta(sesion):
    html = sesion.get(reverse("perfiles:confirmar_manual")).content.decode()
    assert 'value="Camilo Zapata Ospina"' in etiqueta(html, "id_nombre_completo")
    assert "sin-extraer" not in html
    assert "Sirven en cualquier oficio" in html
    assert "Belleza y estética" in html and "Seguridad y vigilancia" in html


# ---- Reglas de la sección 4 en la confirmación --------------------------------

def test_rf003_regla_confirmacion_mensaje_exacto_resaltado_y_foco(sesion, catalogo):
    datos = datos_confirmacion(catalogo, {"Puntualidad": 5}, nombre_completo="",
                               telefono="abc")
    html = sesion.post(reverse("perfiles:confirmar_manual"), datos).content.decode()
    assert ALERTA_VISIBLE in html
    assert f"<span>{MENSAJE}</span>" in html
    assert "is-invalid" in etiqueta(html, "id_nombre_completo")
    assert "is-invalid" in etiqueta(html, "id_telefono")
    assert "autofocus" in etiqueta(html, "id_nombre_completo")
    assert html.count(" autofocus") == 1
    assert not PerfilCandidato.objects.filter(confirmado=True).exists()
    # Conserva lo marcado.
    assert f'name="habilidades" value="{catalogo["Puntualidad"].pk}" checked' in html


def test_rf003_regla_exige_al_menos_una_habilidad(sesion, catalogo):
    html = sesion.post(reverse("perfiles:confirmar_manual"),
                       datos_confirmacion(catalogo, {})).content.decode()
    assert ALERTA_VISIBLE in html
    assert "Marque al menos una habilidad para calcular su ajuste." in html
    assert '<details class="grupo-habs is-invalid"' in html
    assert html.count(" autofocus") == 1


# ---- Acceso -------------------------------------------------------------------

def test_rf003_un_candidato_no_puede_usar_la_hoja_de_vida_de_otro(
        sesion, client, crear_usuario):
    subir(sesion)
    hoja = HojaDeVida.objects.get()
    client.force_login(crear_usuario(correo="otra@correo.com"))
    assert client.get(reverse("perfiles:confirmar_cv", args=[hoja.pk])).status_code == 404


def test_rf003_el_reclutador_no_carga_hojas_de_vida(client, reclutador):
    client.force_login(reclutador)
    assert client.get(reverse(URL_CARGA)).status_code == 403
