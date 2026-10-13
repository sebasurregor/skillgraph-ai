"""HU-RNF-001 · Cifrar contraseñas y datos sensibles (SA-20)."""
from datetime import timedelta

import pytest
from django.contrib.auth.hashers import get_hasher, identify_hasher
from django.contrib.sessions.models import Session
from django.urls import reverse
from django.utils import timezone

from conftest import CLAVE
from cuentas import services
from skillgraph.seguridad import seguridad_transporte

QUINCE_MINUTOS = 15 * 60


# ---- Criterio 1: contraseñas con bcrypt, factor de costo mínimo 12 ----------

def test_rnf001_contrasena_no_se_guarda_en_texto_plano(candidato):
    assert CLAVE not in candidato.password


def test_rnf001_contrasena_se_guarda_con_bcrypt_costo_12(candidato):
    algoritmo, _, variante, costo, _ = candidato.password.split("$")
    assert algoritmo == "bcrypt_sha256"
    assert variante == "2b"
    assert int(costo) >= 12


def test_rnf001_hasher_por_defecto_es_bcrypt_con_costo_minimo_12(candidato, settings):
    assert settings.PASSWORD_HASHERS == ["cuentas.hashers.BCryptCosto12PasswordHasher"]
    assert get_hasher().rounds >= 12
    assert identify_hasher(candidato.password).safe_summary(candidato.password)["work factor"] \
        == 12


def test_rnf001_cada_contrasena_usa_una_sal_distinta(crear_usuario):
    uno = crear_usuario(correo="uno@correo.com")
    dos = crear_usuario(correo="dos@correo.com")
    assert uno.password != dos.password


def test_rnf001_contrasena_cifrada_permite_autenticar(candidato):
    assert candidato.check_password(CLAVE)
    assert not candidato.check_password("otra-clave")


# ---- Criterio 2: HTTPS obligatorio en producción, HTTP en local -------------

def test_rnf001_produccion_exige_https_cookies_seguras_y_hsts():
    ajustes = seguridad_transporte(debug=False)
    assert ajustes["SECURE_SSL_REDIRECT"] is True
    assert ajustes["SESSION_COOKIE_SECURE"] is True
    assert ajustes["CSRF_COOKIE_SECURE"] is True
    assert ajustes["SECURE_HSTS_SECONDS"] >= 31536000
    assert ajustes["SECURE_HSTS_INCLUDE_SUBDOMAINS"] is True


def test_rnf001_local_trabaja_con_http():
    ajustes = seguridad_transporte(debug=True)
    assert ajustes["SECURE_SSL_REDIRECT"] is False
    assert ajustes["SESSION_COOKIE_SECURE"] is False
    assert ajustes["CSRF_COOKIE_SECURE"] is False
    assert ajustes["SECURE_HSTS_SECONDS"] == 0


def test_rnf001_settings_toma_los_ajustes_de_transporte(settings):
    import skillgraph.settings as modulo
    for nombre, valor in seguridad_transporte(modulo.DEBUG).items():
        assert getattr(modulo, nombre) == valor


@pytest.mark.django_db
def test_rnf001_en_produccion_http_redirige_a_https(client, settings):
    settings.SECURE_SSL_REDIRECT = True
    respuesta = client.get(reverse("cuentas:ingresar"))
    assert respuesta.status_code == 301
    assert respuesta["Location"].startswith("https://")


@pytest.mark.django_db
def test_rnf001_en_produccion_responde_con_cabecera_hsts(client, settings):
    settings.SECURE_HSTS_SECONDS = seguridad_transporte(False)["SECURE_HSTS_SECONDS"]
    respuesta = client.get(reverse("cuentas:ingresar"), secure=True)
    assert "max-age=31536000" in respuesta["Strict-Transport-Security"]


# ---- Criterio 3: cierre de sesión tras 15 minutos de inactividad ------------

def _ingresar(client, usuario):
    sesion = client.session
    sesion["correo_ingreso"] = usuario.email
    sesion.save()
    return client.post(reverse("cuentas:ingresar_clave"), {"clave": CLAVE})


def test_rnf001_sesion_configurada_a_15_minutos(settings):
    assert settings.SESSION_COOKIE_AGE == QUINCE_MINUTOS
    assert settings.SESSION_SAVE_EVERY_REQUEST is True


def test_rnf001_cookie_de_sesion_vence_a_los_15_minutos(client, candidato):
    _ingresar(client, candidato)
    assert client.cookies["sessionid"]["max-age"] == QUINCE_MINUTOS


def test_rnf001_sesion_se_cierra_tras_15_minutos_de_inactividad(client, candidato):
    _ingresar(client, candidato)
    assert client.get(reverse("cuentas:inicio")).status_code == 200

    # Simula 15 minutos sin actividad: la sesión guardada ya venció.
    Session.objects.update(expire_date=timezone.now() - timedelta(seconds=1))

    respuesta = client.get(reverse("cuentas:inicio"))
    assert respuesta.status_code == 302
    assert respuesta["Location"].startswith(reverse("cuentas:ingresar"))


def test_rnf001_la_actividad_reinicia_el_contador_de_inactividad(client, candidato):
    _ingresar(client, candidato)
    # Quedaba un minuto para el cierre automático...
    Session.objects.update(expire_date=timezone.now() + timedelta(minutes=1))

    assert client.get(reverse("cuentas:inicio")).status_code == 200

    # ...y la petición devolvió el plazo a 15 minutos.
    restante = Session.objects.get().expire_date - timezone.now()
    assert restante > timedelta(minutes=14)


def test_rnf001_cerrar_sesion_invalida_la_sesion(client, candidato):
    _ingresar(client, candidato)
    client.post(reverse("cuentas:salir"))
    assert client.get(reverse("cuentas:inicio")).status_code == 302


def test_rnf001_el_log_no_registra_correos_ni_contrasenas(client, candidato, caplog):
    sesion = client.session
    sesion["correo_ingreso"] = candidato.email
    sesion.save()
    with caplog.at_level("INFO"):
        client.post(reverse("cuentas:ingresar_clave"), {"clave": "clave-equivocada"})
        services.registrar_usuario(correo="nueva@correo.com", clave="secreto-123", nombres="A",
                                   apellidos="B", telefono="3000000000", ciudad="Cali")
    assert "clave-equivocada" not in caplog.text
    assert "secreto-123" not in caplog.text
    assert candidato.email not in caplog.text
