"""Base técnica: configuración del proyecto y GraphCore integrado."""
from unittest import mock

from django.core.management import get_commands
from neo4j.exceptions import ServiceUnavailable

from GraphCore.neo4j_driver import Neo4jConnection


def test_base_settings_construye_neo4j_config(settings):
    assert set(settings.NEO4J_CONFIG) == {"URI", "USER", "PASSWORD", "DATABASE"}
    assert settings.NEO4J_CONFIG["URI"].startswith(("bolt://", "neo4j://", "neo4j+s://"))


def test_base_settings_lee_los_pesos_del_matching(settings):
    pesos = [settings.W_COBERTURA, settings.W_NIVEL, settings.W_CENTRALIDAD, settings.W_ADYACENCIA]
    assert all(isinstance(p, float) for p in pesos)
    assert round(sum(pesos), 6) == 1.0
    assert settings.MATCHING_VERSION


def test_base_graphcore_registra_sus_comandos():
    comandos = get_commands()
    assert comandos["init_graph"] == "GraphCore"
    assert comandos["check_graph"] == "GraphCore"


def test_base_graphcore_informa_si_neo4j_no_esta_disponible():
    driver = mock.Mock()
    driver.verify_connectivity.side_effect = ServiceUnavailable("sin conexión")
    with mock.patch.object(Neo4jConnection, "get_driver", return_value=driver):
        disponible, mensaje = Neo4jConnection.verify()
    assert disponible is False
    assert "no disponible" in mensaje


def test_base_aplicaciones_instaladas(settings):
    for app in ("rest_framework", "GraphCore", "cuentas"):
        assert app in settings.INSTALLED_APPS
