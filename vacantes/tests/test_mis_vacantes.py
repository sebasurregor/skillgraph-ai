"""Acceso a datos para la sustentación: lista con acciones y formulario que inserta,
actualiza y borra vacantes."""
import pytest
from django.urls import reverse

from cuentas.models import Usuario
from vacantes.models import Vacante
from vacantes.tests.test_rf011_publicar_vacante import datos_post


@pytest.fixture
def sesion(client, reclutador):
    client.force_login(reclutador)
    return client


@pytest.fixture
def publicada(sesion, catalogo):
    sesion.post(reverse("vacantes:nueva"), datos_post(catalogo))
    return Vacante.objects.get()


def test_lista_vacia_invita_a_crear_la_primera(sesion):
    html = sesion.get(reverse("vacantes:lista")).content.decode()
    assert "Todavía no tiene vacantes" in html
    assert reverse("vacantes:nueva") in html


def test_lista_muestra_los_registros_con_una_accion_por_registro(sesion, publicada, catalogo):
    sesion.post(reverse("vacantes:nueva"),
                datos_post(catalogo, accion="borrador", titulo="Mesero"))
    html = sesion.get(reverse("vacantes:lista")).content.decode()

    assert html.count("<tr data-vacante=") == 2
    assert "Auxiliar de bodega" in html and "Mesero" in html
    assert ">Publicada</span>" in html and ">Borrador</span>" in html
    borrador = Vacante.objects.get(titulo="Mesero")
    for nombre, pk in (("editar", publicada.pk), ("despublicar", publicada.pk),
                       ("eliminar", publicada.pk), ("publicar", borrador.pk)):
        assert reverse(f"vacantes:{nombre}", args=[pk]) in html


def test_formulario_inserta_una_vacante(sesion, catalogo, reclutador):
    assert Vacante.objects.count() == 0
    sesion.post(reverse("vacantes:nueva"), datos_post(catalogo))
    vacante = Vacante.objects.get()
    assert vacante.reclutador == reclutador
    assert vacante.salario == 1600000


def test_formulario_de_edicion_viene_precargado(sesion, publicada):
    html = sesion.get(reverse("vacantes:editar", args=[publicada.pk])).content.decode()
    assert 'value="Auxiliar de bodega"' in html
    assert 'name="req-2-peso"' in html
    assert 'value="0.40"' in html


def test_formulario_actualiza_una_vacante(sesion, publicada, catalogo):
    nuevos = [("Carga y descarga", "0.50", 2, True), ("Trabajo en equipo", "0.50", 3, False)]
    sesion.post(reverse("vacantes:editar", args=[publicada.pk]),
                datos_post(catalogo, nuevos, titulo="Auxiliar de cargue", salario="1750000"))

    publicada.refresh_from_db()
    assert Vacante.objects.count() == 1
    assert publicada.titulo == "Auxiliar de cargue"
    assert publicada.salario == 1750000
    assert set(publicada.requisitos.values_list("habilidad__nombre", flat=True)) == {
        "Carga y descarga", "Trabajo en equipo"}


def test_eliminar_pide_confirmacion_y_luego_borra(sesion, publicada, grafo):
    url = reverse("vacantes:eliminar", args=[publicada.pk])
    assert "¿Eliminar «Auxiliar de bodega»?" in sesion.get(url).content.decode()
    assert Vacante.objects.count() == 1

    respuesta = sesion.post(url, follow=True)
    assert Vacante.objects.count() == 0
    assert "Vacante eliminada." in respuesta.content.decode()
    assert grafo.escrituras_con("DETACH DELETE v")


def test_despublicar_desde_la_lista(sesion, publicada):
    respuesta = sesion.post(reverse("vacantes:despublicar", args=[publicada.pk]), follow=True)
    publicada.refresh_from_db()
    assert publicada.estado == Vacante.Estado.BORRADOR
    assert "Vacante despublicada" in respuesta.content.decode()


def test_un_reclutador_no_ve_ni_toca_vacantes_ajenas(client, publicada, crear_usuario):
    otro = crear_usuario(correo="otro@correo.com", rol=Usuario.Rol.RECLUTADOR)
    client.force_login(otro)
    assert "Auxiliar de bodega" not in client.get(reverse("vacantes:lista")).content.decode()
    for nombre in ("editar", "eliminar"):
        assert client.get(reverse(f"vacantes:{nombre}", args=[publicada.pk])).status_code == 404
    assert client.post(reverse("vacantes:eliminar", args=[publicada.pk])).status_code == 404
    assert Vacante.objects.count() == 1


def test_un_candidato_no_puede_gestionar_vacantes(client, candidato):
    client.force_login(candidato)
    assert client.get(reverse("vacantes:lista")).status_code == 403
    assert client.get(reverse("vacantes:nueva")).status_code == 403


@pytest.mark.django_db
def test_sin_sesion_redirige_a_ingresar(client):
    respuesta = client.get(reverse("vacantes:lista"))
    assert respuesta.status_code == 302
    assert respuesta["Location"].startswith(reverse("cuentas:ingresar"))


def test_el_reclutador_llega_a_mis_vacantes_desde_el_inicio(sesion):
    html = sesion.get(reverse("cuentas:inicio")).content.decode()
    assert html.count(reverse("vacantes:lista")) >= 2    # barra lateral y botón
