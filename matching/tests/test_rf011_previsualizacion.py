"""HU-RF-011 · Previsualización de candidatos potenciales (SA-30)."""
import pytest
from django.urls import reverse

from cuentas.models import Usuario
from matching import services
from perfiles import services as perfiles

URL = "matching:candidatos_potenciales"


@pytest.fixture
def candidatos(crear_usuario, catalogo):
    """Tres candidatos con perfil confirmado y uno sin confirmar."""
    def crear(correo, habilidades, confirmar=True):
        perfil = perfiles.perfil_de(crear_usuario(correo=correo))
        perfiles.guardar_habilidades(perfil, habilidades)
        if confirmar:
            perfiles.confirmar_perfil(perfil)
        return perfil
    crear("bodega@correo.com", {"Picking y packing": 4, "Puntualidad": 5})
    crear("novato@correo.com", {"Picking y packing": 1, "Puntualidad": 3})
    crear("estilista@correo.com", {"Colorimetría": 5, "Corte de cabello": 4})
    crear("sin.confirmar@correo.com", {"Picking y packing": 5, "Puntualidad": 5}, confirmar=False)


def requisito(catalogo, nombre, nivel=2, obligatoria=True):
    return {"habilidad": catalogo[nombre], "nivel_minimo": nivel, "obligatoria": obligatoria}


def test_rf011_previsualizacion_consulta_el_grafo(grafo, catalogo):
    grafo.respuesta_lectura = [{"total": 7}]
    resultado = services.contar_candidatos_potenciales([requisito(catalogo, "Excel")])
    assert resultado == {"candidatos": 7, "total": 7, "fuente": "neo4j", "aviso": ""}
    assert "TIENE" in grafo.lecturas[0][0]


def test_rf011_respaldo_cuenta_quienes_cubren_todas_las_obligatorias(
        grafo_caido, catalogo, candidatos):
    resultado = services.contar_candidatos_potenciales([
        requisito(catalogo, "Picking y packing", nivel=2),
        requisito(catalogo, "Puntualidad", nivel=3),
        requisito(catalogo, "Excel", obligatoria=False),
    ])
    assert resultado["candidatos"] == 1      # el novato no alcanza el nivel 2 en picking
    assert resultado["total"] == 3           # el perfil sin confirmar no cuenta
    assert resultado["fuente"] == "sqlite"


def test_rf011_respaldo_exige_el_nivel_minimo(grafo_caido, catalogo, candidatos):
    def cuenta(nivel):
        return services.contar_candidatos_potenciales(
            [requisito(catalogo, "Picking y packing", nivel=nivel)])["candidatos"]
    assert (cuenta(1), cuenta(4), cuenta(5)) == (2, 1, 0)


def test_rf011_sin_obligatorias_basta_cubrir_una_habilidad(grafo_caido, catalogo, candidatos):
    resultado = services.contar_candidatos_potenciales([
        requisito(catalogo, "Colorimetría", nivel=3, obligatoria=False),
        requisito(catalogo, "Puntualidad", nivel=5, obligatoria=False),
    ])
    assert resultado["candidatos"] == 2      # la estilista y el auxiliar de bodega


def test_rf011_respaldo_avisa_y_lo_registra_en_el_log(grafo_caido, catalogo, caplog):
    with caplog.at_level("WARNING"):
        resultado = services.contar_candidatos_potenciales([requisito(catalogo, "Excel")])
    assert resultado["aviso"] == services.AVISO_RESPALDO
    assert "respaldo en SQLite" in caplog.text


def test_rf011_api_devuelve_la_previsualizacion_al_reclutador(
        client, reclutador, catalogo, candidatos, grafo_caido):
    client.force_login(reclutador)
    cuerpo = {"requisitos": [
        {"habilidad": catalogo["Colorimetría"].pk, "nivel_minimo": 3, "obligatoria": True}]}
    respuesta = client.post(reverse(URL), cuerpo, content_type="application/json")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"candidatos": 1, "total": 3, "fuente": "sqlite",
                                "aviso": services.AVISO_RESPALDO}


def test_rf011_api_rechaza_datos_invalidos(client, reclutador, catalogo):
    client.force_login(reclutador)
    cuerpo = {"requisitos": [{"habilidad": 999999, "nivel_minimo": 9}]}
    respuesta = client.post(reverse(URL), cuerpo, content_type="application/json")
    assert respuesta.status_code == 400


def test_rf011_api_solo_para_reclutadores(client, candidato, catalogo):
    cuerpo = {"requisitos": []}
    assert client.post(reverse(URL), cuerpo, content_type="application/json").status_code == 403
    client.force_login(candidato)
    assert client.post(reverse(URL), cuerpo, content_type="application/json").status_code == 403
    assert candidato.rol == Usuario.Rol.CANDIDATO
