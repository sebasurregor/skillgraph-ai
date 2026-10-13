"""Base técnica: registro e inicio de sesión reales con roles de candidato y reclutador."""
import pytest
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory
from django.urls import reverse

from conftest import CLAVE
from cuentas.models import Usuario
from cuentas.permisos import rol_requerido

DATOS_REGISTRO = {
    "rol": "candidato", "nombres": "Camilo", "apellidos": "Zapata Ospina",
    "correo": "Nuevo.Usuario@correo.com", "telefono": "3109876543", "ciudad": "Medellín",
    "empresa": "", "clave": CLAVE, "clave2": CLAVE, "acepta_datos": "on",
}


def _con_correo(client, correo):
    sesion = client.session
    sesion["correo_ingreso"] = correo
    sesion.save()


@pytest.mark.django_db
def test_base_raiz_sin_sesion_lleva_a_ingresar(client):
    respuesta = client.get("/", follow=True)
    assert respuesta.redirect_chain[-1][0].startswith(reverse("cuentas:ingresar"))


@pytest.mark.django_db
def test_base_correo_inexistente_lleva_al_registro_con_el_correo_precargado(client):
    respuesta = client.post(reverse("cuentas:ingresar"), {"correo": "nuevo@correo.com"},
                            follow=True)
    assert respuesta.redirect_chain[-1][0] == reverse("cuentas:registro")
    assert 'value="nuevo@correo.com"' in respuesta.content.decode()


def test_base_correo_existente_lleva_a_pedir_la_contrasena(client, candidato):
    respuesta = client.post(reverse("cuentas:ingresar"), {"correo": candidato.email.upper()},
                            follow=True)
    assert respuesta.redirect_chain[-1][0] == reverse("cuentas:ingresar_clave")
    assert candidato.email in respuesta.content.decode()


@pytest.mark.django_db
def test_base_registro_crea_candidato_y_lleva_a_iniciar_sesion(client):
    respuesta = client.post(reverse("cuentas:registro"), DATOS_REGISTRO, follow=True)

    usuario = Usuario.objects.get(email="nuevo.usuario@correo.com")
    assert usuario.es_candidato and not usuario.es_reclutador
    assert usuario.acepta_tratamiento_datos
    assert respuesta.redirect_chain[-1][0] == reverse("cuentas:ingresar_clave")
    assert "Su cuenta fue creada correctamente" in respuesta.content.decode()
    # Crear la cuenta no inicia la sesión: se confirma la contraseña recién definida.
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_base_registro_crea_reclutador_con_empresa(client):
    datos = dict(DATOS_REGISTRO, rol="reclutador", empresa="Moda Andina")
    client.post(reverse("cuentas:registro"), datos)
    usuario = Usuario.objects.get()
    assert usuario.es_reclutador
    assert usuario.empresa == "Moda Andina"


@pytest.mark.django_db
def test_base_registro_de_reclutador_exige_empresa(client):
    datos = dict(DATOS_REGISTRO, rol="reclutador", empresa="")
    respuesta = client.post(reverse("cuentas:registro"), datos)
    assert not Usuario.objects.exists()
    assert "Indique la empresa" in respuesta.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize("cambio, detalle", [
    ({"clave2": "distinta123"}, "Las contraseñas no coinciden."),
    ({"clave": "corta", "clave2": "corta"}, "8 caracteres"),
    ({"telefono": "310-987"}, "entre 7 y 10 dígitos"),
])
def test_base_registro_rechaza_datos_invalidos(client, cambio, detalle):
    respuesta = client.post(reverse("cuentas:registro"), dict(DATOS_REGISTRO, **cambio))
    assert not Usuario.objects.exists()
    assert detalle in respuesta.content.decode()


def test_base_registro_rechaza_correo_ya_registrado(client, candidato):
    respuesta = client.post(reverse("cuentas:registro"),
                            dict(DATOS_REGISTRO, correo=candidato.email))
    assert Usuario.objects.count() == 1
    assert "Ya existe una cuenta con ese correo" in respuesta.content.decode()


def test_base_inicio_de_sesion_con_credenciales_validas(client, candidato):
    _con_correo(client, candidato.email)
    respuesta = client.post(reverse("cuentas:ingresar_clave"), {"clave": CLAVE}, follow=True)
    # Flujo resume-first: al candidato sin perfil se le ofrece primero subir su hoja de vida.
    assert respuesta.redirect_chain[-1][0] == reverse("perfiles:cargar_cv")
    assert "_auth_user_id" in client.session


def test_base_inicio_de_sesion_rechaza_contrasena_incorrecta(client, candidato):
    _con_correo(client, candidato.email)
    respuesta = client.post(reverse("cuentas:ingresar_clave"), {"clave": "incorrecta"})
    assert respuesta.status_code == 200
    assert "Las credenciales no coinciden" in respuesta.content.decode()
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_base_pedir_contrasena_sin_correo_vuelve_al_paso_1(client):
    respuesta = client.get(reverse("cuentas:ingresar_clave"))
    assert respuesta["Location"] == reverse("cuentas:ingresar")


@pytest.mark.django_db
def test_base_inicio_exige_sesion(client):
    respuesta = client.get(reverse("cuentas:inicio"))
    assert respuesta.status_code == 302
    assert respuesta["Location"].startswith(reverse("cuentas:ingresar"))


def test_base_inicio_muestra_el_rol_de_cada_usuario(client, candidato, reclutador):
    client.force_login(candidato)
    assert "cargará su hoja de vida" in client.get(reverse("cuentas:inicio")).content.decode()
    client.force_login(reclutador)
    assert "publicará vacantes" in client.get(reverse("cuentas:inicio")).content.decode()


def test_base_cerrar_sesion_solo_por_post(client, candidato):
    client.force_login(candidato)
    assert client.get(reverse("cuentas:salir")).status_code == 405
    assert "_auth_user_id" in client.session


def test_base_rol_requerido_bloquea_al_rol_equivocado(candidato, reclutador):
    @rol_requerido(Usuario.Rol.RECLUTADOR)
    def vista(request):
        return "ok"

    peticion = RequestFactory().get("/")
    peticion.user = reclutador
    assert vista(peticion) == "ok"
    peticion.user = candidato
    with pytest.raises(PermissionDenied):
        vista(peticion)
