"""HU-RF-006 · Postular a vacantes (SA-15)."""
import re

import pytest
from django.db import IntegrityError, transaction
from django.urls import reverse

from cuentas.models import Usuario
from postulaciones import services
from postulaciones.models import Postulacion
from vacantes import services as vacantes
from vacantes.models import Vacante

RECOMENDACIONES = "recomendaciones:lista"


@pytest.fixture
def ana(demo):
    return Usuario.objects.get(email="ana.rios@correo.com")


@pytest.fixture
def backend(demo):
    return Vacante.objects.get(titulo="Desarrollador Backend Senior")


@pytest.fixture
def sesion(client, ana):
    client.force_login(ana)
    return client


def postular(client, vacante, **kwargs):
    return client.post(reverse("postulaciones:postular", args=[vacante.pk]), **kwargs)


# ---- Criterio 1: postular con un solo clic --------------------------------------

def test_rf006_cada_vacante_recomendada_tiene_el_boton_postularme(sesion, backend):
    html = sesion.get(reverse(RECOMENDACIONES)).content.decode()
    accion = reverse("postulaciones:postular", args=[backend.pk])
    formulario = html.split(f'action="{accion}"')[1].split("</form>")[0]
    # Un solo clic: el formulario no pide ningún dato, solo el botón.
    assert f'<button class="btn btn-accent" type="submit" data-postular="{backend.pk}">' \
           in formulario
    assert re.findall(r'<input type="(\w+)"', formulario) == ["hidden", "hidden"]
    assert html.count("data-postular=") == html.count('<article class="job"')


def test_rf006_el_boton_esta_a_la_vista_sin_abrir_la_explicacion(sesion, backend):
    html = sesion.get(reverse(RECOMENDACIONES)).content.decode()
    tarjeta = html.split(f'data-vacante="{backend.pk}"')[1].split("</article>")[0]
    assert tarjeta.index("data-postular=") < tarjeta.index('<details class="porque">')


def test_rf006_un_clic_crea_la_postulacion(sesion, ana, backend):
    respuesta = postular(sesion, backend)
    assert respuesta.status_code == 302

    postulacion = Postulacion.objects.get()
    assert (postulacion.candidato, postulacion.vacante) == (ana.perfil, backend)
    assert postulacion.estado == Postulacion.Estado.ENVIADA
    assert postulacion.ajuste_al_postular == 82


def test_rf006_solo_se_postula_por_post(sesion, backend):
    assert sesion.get(reverse("postulaciones:postular", args=[backend.pk])).status_code == 405
    assert not Postulacion.objects.exists()


# ---- Criterio 2: confirma el envío ----------------------------------------------

def test_rf006_confirma_el_envio_de_la_postulacion(sesion, backend):
    html = postular(sesion, backend, follow=True).content.decode()
    assert ("Postulación enviada a TechNova S.A.S. para «Desarrollador Backend Senior»."
            in html)
    assert 'class="alert alert-ok"' in html


def test_rf006_tras_postular_vuelve_a_la_lista_donde_estaba(sesion, backend):
    origen = reverse(RECOMENDACIONES) + "?ver=todas&orden=fecha"
    respuesta = postular(sesion, backend, data={"siguiente": origen})
    assert respuesta.url == origen


def test_rf006_no_redirige_a_sitios_externos(sesion, backend):
    respuesta = postular(sesion, backend, data={"siguiente": "https://malicioso.example/"})
    assert respuesta.url == reverse(RECOMENDACIONES)


def test_rf006_la_tarjeta_muestra_que_ya_se_postulo(sesion, backend):
    postular(sesion, backend)
    html = sesion.get(reverse(RECOMENDACIONES)).content.decode()
    assert f'disabled data-postulada="{backend.pk}">Postulación enviada ✓</button>' in html
    assert f'data-postular="{backend.pk}"' not in html
    assert html.count("data-postular=") == html.count('<article class="job"') - 1


# ---- Criterio 3: impide postular más de una vez ---------------------------------

def test_rf006_impide_postular_mas_de_una_vez_a_la_misma_vacante(sesion, backend):
    postular(sesion, backend)
    html = postular(sesion, backend, follow=True).content.decode()
    assert Postulacion.objects.count() == 1
    assert "Ya se había postulado a «Desarrollador Backend Senior»." in html
    assert "No se envió una segunda postulación." in html


def test_rf006_el_servicio_devuelve_la_postulacion_existente(ana, backend):
    primera, creada = services.postular(ana, backend.pk)
    segunda, creada_otra_vez = services.postular(ana, backend.pk)
    assert (creada, creada_otra_vez) == (True, False)
    assert primera == segunda


def test_rf006_la_base_de_datos_tambien_impide_el_duplicado(ana, backend):
    Postulacion.objects.create(candidato=ana.perfil, vacante=backend, ajuste_al_postular=82)
    with pytest.raises(IntegrityError), transaction.atomic():
        Postulacion.objects.create(candidato=ana.perfil, vacante=backend, ajuste_al_postular=82)


def test_rf006_si_puede_postularse_a_vacantes_distintas(sesion, backend):
    datos = Vacante.objects.get(titulo="Ingeniera de datos")
    postular(sesion, backend)
    postular(sesion, datos)
    assert Postulacion.objects.count() == 2


def test_rf006_dos_candidatos_pueden_postularse_a_la_misma_vacante(client, demo):
    bodega = Vacante.objects.get(titulo="Auxiliar de bodega — temporada navideña")
    for correo in ("ana.rios@correo.com", "camilo.zapata@correo.com"):
        client.force_login(Usuario.objects.get(email=correo))
        postular(client, bodega)
    assert Postulacion.objects.filter(vacante=bodega).count() == 2


# ---- Criterio 4: ver el estado de las postulaciones -----------------------------

def test_rf006_permite_ver_el_estado_de_las_postulaciones(sesion, backend):
    datos = Vacante.objects.get(titulo="Ingeniera de datos")
    postular(sesion, backend)
    postular(sesion, datos)
    services.cambiar_estado(Postulacion.objects.get(vacante=datos), "preseleccionada")

    html = sesion.get(reverse("postulaciones:mias")).content.decode()
    assert html.count("<tr data-postulacion=") == 2
    assert "Desarrollador Backend Senior" in html and "Ingeniera de datos" in html
    assert 'data-estado="enviada">Enviada</span>' in html
    assert 'data-estado="preseleccionada">Preseleccionada</span>' in html
    assert "82 %" in html


def test_rf006_el_candidato_ve_el_cambio_de_estado_que_hace_el_reclutador(
        client, sesion, backend):
    postular(sesion, backend)
    postulacion = Postulacion.objects.get()
    reclutador = backend.reclutador
    client.force_login(reclutador)
    client.post(reverse("postulaciones:cambiar_estado", args=[postulacion.pk]),
                {"estado": "en_revision"})

    client.force_login(postulacion.candidato.usuario)
    html = client.get(reverse("postulaciones:mias")).content.decode()
    assert 'data-estado="en_revision">En revisión</span>' in html


def test_rf006_cada_candidato_ve_solo_sus_postulaciones(client, sesion, backend):
    postular(sesion, backend)
    client.force_login(Usuario.objects.get(email="camilo.zapata@correo.com"))
    html = client.get(reverse("postulaciones:mias")).content.decode()
    assert "Todavía no se ha postulado a ninguna vacante" in html


def test_rf006_se_llega_a_mis_postulaciones_desde_la_barra(sesion):
    html = sesion.get(reverse(RECOMENDACIONES)).content.decode()
    assert f'href="{reverse("postulaciones:mias")}" aria-label="Mis postulaciones"' in html


# ---- Reglas de negocio y acceso -------------------------------------------------

def test_rf006_no_se_puede_postular_a_una_vacante_despublicada(sesion, backend):
    vacantes.despublicar_vacante(backend)
    html = postular(sesion, backend, follow=True).content.decode()
    assert not Postulacion.objects.exists()
    assert "Esta vacante ya no está disponible." in html


def test_rf006_exige_perfil_confirmado(client, crear_usuario, backend):
    client.force_login(crear_usuario(correo="sin.perfil@correo.com"))
    html = postular(client, backend, follow=True).content.decode()
    assert not Postulacion.objects.exists()
    assert "Confirme su perfil antes de postularse." in html


def test_rf006_el_reclutador_no_se_postula(client, backend):
    client.force_login(backend.reclutador)
    assert postular(client, backend).status_code == 403


def test_rf006_funciona_con_neo4j_caido(sesion, backend, grafo):
    grafo.caido = True
    services.matching.servicio_grafo.reiniciar_estado()
    postular(sesion, backend)
    assert Postulacion.objects.get().ajuste_al_postular == 82
