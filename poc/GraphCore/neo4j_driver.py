# GraphCore/neo4j_driver.py
"""Envoltorio del driver oficial de Neo4j para SkillGraph AI."""
import logging
from django.conf import settings
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError

logger = logging.getLogger(__name__)


class Neo4jConnection:
    """Gestor único de la conexión Bolt hacia la base de datos de grafos."""

    _driver = None

    @classmethod
    def get_driver(cls):
        if cls._driver is None:
            cfg = settings.NEO4J_CONFIG
            cls._driver = GraphDatabase.driver(
                cfg["URI"],
                auth=(cfg["USER"], cfg["PASSWORD"]),
                max_connection_lifetime=3600,
                max_connection_pool_size=50,
                connection_acquisition_timeout=30,
            )
            logger.info("Driver de Neo4j inicializado en %s", cfg["URI"])
        return cls._driver

    @classmethod
    def close(cls):
        if cls._driver is not None:
            cls._driver.close()
            cls._driver = None
            logger.info("Driver de Neo4j cerrado")

    @classmethod
    def verify(cls):
        """Comprueba la disponibilidad del servidor. Devuelve (bool, mensaje)."""
        try:
            cls.get_driver().verify_connectivity()
            return True, "Conexión establecida con Neo4j"
        except AuthError:
            return False, "Credenciales de Neo4j inválidas"
        except ServiceUnavailable as exc:
            return False, f"Servidor de Neo4j no disponible: {exc}"

    @classmethod
    def read(cls, cypher, **params):
        """Ejecuta una consulta de solo lectura y devuelve una lista de diccionarios."""
        cfg = settings.NEO4J_CONFIG
        with cls.get_driver().session(
            database=cfg["DATABASE"], default_access_mode="READ"
        ) as session:
            result = session.run(cypher, **params)
            return [record.data() for record in result]

    @classmethod
    def write(cls, cypher, **params):
        """Ejecuta una consulta de escritura dentro de una transacción gestionada."""
        cfg = settings.NEO4J_CONFIG
        with cls.get_driver().session(database=cfg["DATABASE"]) as session:
            return session.execute_write(
                lambda tx: [r.data() for r in tx.run(cypher, **params)]
            )
