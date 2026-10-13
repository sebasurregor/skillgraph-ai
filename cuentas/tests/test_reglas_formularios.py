"""Reglas no negociables de los formularios (sección 4): mensaje exacto, resaltado y foco."""
import re

import pytest
from django.urls import reverse

from skillgraph.formularios import MSG_OBLIGATORIOS

MENSAJE = "Favor ingresar información válida en los campos obligatorios"
ALERTA_VISIBLE = '<div id="alerta-form" class="alert alert-error" role="alert"'
ALERTA_OCULTA = '<div id="alerta-form" class="alert alert-error hidden" role="alert"'


def _etiqueta(html, id_campo):
    """Devuelve la etiqueta HTML del control con ese id."""
    return re.search(r'<(?:input|select|textarea)[^>]*\bid="%s"[^>]*>' % id_campo, html).group(0)


def _con_correo(client, correo="alguien@correo.com"):
    sesion = client.session
    sesion["correo_ingreso"] = correo
    sesion.save()


@pytest.fixture
def formularios(client, db):
    """(url, datos inválidos, primer campo inválido, otro campo inválido o None)."""
    _con_correo(client)
    return [
        (reverse("cuentas:ingresar"), {"correo": ""}, "id_correo", None),
        (reverse("cuentas:ingresar"), {"correo": "sin-arroba"}, "id_correo", None),
        (reverse("cuentas:ingresar_clave"), {"clave": ""}, "id_clave", None),
        (reverse("cuentas:registro"), {"rol": "candidato", "correo": "a@correo.com"},
         "id_nombres", "id_apellidos"),
    ]


def test_regla_el_mensaje_es_exactamente_el_exigido():
    assert MSG_OBLIGATORIOS == MENSAJE


def test_regla_muestra_el_mensaje_exacto_con_campos_vacios_o_invalidos(client, formularios):
    for url, datos, _, _ in formularios:
        html = client.post(url, datos).content.decode()
        assert ALERTA_VISIBLE in html, url
        # Texto exacto: sin punto final ni texto adicional dentro de la alerta.
        assert f"<span>{MENSAJE}</span>" in html, url


def test_regla_no_muestra_el_mensaje_antes_de_enviar(client, formularios):
    for url, _, _, _ in formularios:
        html = client.get(url).content.decode()
        assert ALERTA_OCULTA in html, url
        assert "is-invalid" not in html, url


def test_regla_resalta_los_campos_invalidos(client, formularios):
    for url, datos, primero, otro in formularios:
        html = client.post(url, datos).content.decode()
        for id_campo in filter(None, (primero, otro)):
            etiqueta = _etiqueta(html, id_campo)
            assert "is-invalid" in etiqueta, (url, id_campo)
            assert 'aria-invalid="true"' in etiqueta, (url, id_campo)


def test_regla_no_resalta_los_campos_validos(client, formularios):
    url, datos, _, _ = formularios[-1]
    html = client.post(url, datos).content.decode()
    assert "is-invalid" not in _etiqueta(html, "id_correo")


def test_regla_el_foco_va_al_primer_campo_invalido(client, formularios):
    for url, datos, primero, otro in formularios:
        html = client.post(url, datos).content.decode()
        assert "autofocus" in _etiqueta(html, primero), url
        assert html.count(" autofocus") == 1, url
        if otro:
            assert "autofocus" not in _etiqueta(html, otro), url


def test_regla_credenciales_incorrectas_tambien_cumplen_la_regla(client, candidato):
    _con_correo(client, candidato.email)
    html = client.post(reverse("cuentas:ingresar_clave"), {"clave": "incorrecta"}).content.decode()
    assert f"<span>{MENSAJE}</span>" in html
    etiqueta = _etiqueta(html, "id_clave")
    assert "is-invalid" in etiqueta and "autofocus" in etiqueta


def test_regla_conserva_lo_ya_digitado(client, formularios):
    url, datos, _, _ = formularios[-1]
    html = client.post(url, dict(datos, telefono="3109876543")).content.decode()
    assert 'value="3109876543"' in html
    assert 'value="a@correo.com"' in html


def test_regla_los_formularios_usan_la_validacion_del_sistema(client, formularios):
    """El navegador no intercepta el envío y el script común aplica la misma regla."""
    for url, _, _, _ in formularios:
        html = client.get(url).content.decode()
        assert "novalidate data-validar" in html, url
        assert "js/validacion.js" in html, url
        assert " required" not in html, url
        assert 'data-obligatorio="1"' in html, url


def test_regla_la_interfaz_esta_en_espanol(client, formularios):
    for url, _, _, _ in formularios:
        html = client.get(url).content.decode()
        assert '<html lang="es-CO"' in html, url
    html = client.post(reverse("cuentas:registro"), {"rol": "candidato"}).content.decode()
    assert "Este campo es requerido." in html
    assert "This field is required" not in html
