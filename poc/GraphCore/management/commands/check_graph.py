# GraphCore/management/commands/check_graph.py
"""Hello World de Neo4j: verifica conectividad, escritura y lectura."""
import time
from django.core.management.base import BaseCommand
from GraphCore.neo4j_driver import Neo4jConnection


class Command(BaseCommand):
    help = "Verifica la conexión con Neo4j ejecutando una consulta Cypher de prueba."

    def handle(self, *args, **options):
        self.stdout.write("=" * 62)
        self.stdout.write("  SkillGraph AI · Prueba de concepto: conexión con Neo4j")
        self.stdout.write("=" * 62)

        # --- Paso 1: conectividad ------------------------------------------
        ok, mensaje = Neo4jConnection.verify()
        if not ok:
            self.stdout.write(self.style.ERROR(f"[1/4] {mensaje}"))
            return
        self.stdout.write(self.style.SUCCESS(f"[1/4] {mensaje}"))

        # --- Paso 2: versión del servidor ----------------------------------
        info = Neo4jConnection.read(
            "CALL dbms.components() YIELD name, versions, edition "
            "RETURN name AS nombre, versions[0] AS version, edition AS edicion"
        )
        self.stdout.write(self.style.SUCCESS(
            f"[2/4] Servidor: {info[0]['nombre']} "
            f"{info[0]['version']} ({info[0]['edicion']})"
        ))

        # --- Paso 3: escritura idempotente ---------------------------------
        inicio = time.perf_counter()
        Neo4jConnection.write(
            """
            MERGE (c:Candidato {usuario_id: $usuario_id})
              ON CREATE SET c.titular = $titular, c.creado_en = datetime()
            MERGE (s:Skill {nombre: $skill})
              ON CREATE SET s.categoria = $categoria
            MERGE (c)-[r:HAS_SKILL]->(s)
              SET r.nivel = $nivel, r.anios_experiencia = $anios
            RETURN c.usuario_id AS candidato, s.nombre AS skill, r.nivel AS nivel
            """,
            usuario_id=0, titular="Candidato de prueba", skill="Cypher",
            categoria="Lenguaje de consulta", nivel=3, anios=1,
        )
        self.stdout.write(self.style.SUCCESS(
            "[3/4] Escritura idempotente ejecutada (MERGE de :Candidato y :Skill)"
        ))

        # --- Paso 4: lectura y recorrido del grafo -------------------------
        filas = Neo4jConnection.read(
            """
            MATCH (c:Candidato {usuario_id: $usuario_id})-[r:HAS_SKILL]->(s:Skill)
            RETURN c.titular AS candidato,
                   s.nombre  AS habilidad,
                   s.categoria AS categoria,
                   r.nivel   AS nivel
            """,
            usuario_id=0,
        )
        transcurrido = (time.perf_counter() - inicio) * 1000
        for fila in filas:
            self.stdout.write(self.style.SUCCESS(
                f"[4/4] {fila['candidato']} --[:HAS_SKILL nivel={fila['nivel']}]--> "
                f"{fila['habilidad']} ({fila['categoria']})"
            ))

        # --- Limpieza del nodo de prueba -----------------------------------
        Neo4jConnection.write(
            "MATCH (c:Candidato {usuario_id: $usuario_id}) DETACH DELETE c",
            usuario_id=0,
        )
        self.stdout.write("-" * 62)
        self.stdout.write(self.style.SUCCESS(
            f"Prueba de concepto superada en {transcurrido:.1f} ms. "
            "Nodo de prueba eliminado."
        ))
