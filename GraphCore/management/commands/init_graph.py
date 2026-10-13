# GraphCore/management/commands/init_graph.py
from django.core.management.base import BaseCommand
from GraphCore.neo4j_driver import Neo4jConnection

ESQUEMA = [
    "CREATE CONSTRAINT skill_nombre IF NOT EXISTS "
    "FOR (s:Skill) REQUIRE s.nombre IS UNIQUE",
    "CREATE CONSTRAINT candidato_id IF NOT EXISTS "
    "FOR (c:Candidato) REQUIRE c.usuario_id IS UNIQUE",
    "CREATE CONSTRAINT vacante_id IF NOT EXISTS "
    "FOR (v:Vacante) REQUIRE v.vacante_id IS UNIQUE",
    "CREATE CONSTRAINT rol_nombre IF NOT EXISTS "
    "FOR (r:Rol) REQUIRE r.nombre IS UNIQUE",
    "CREATE INDEX vacante_estado IF NOT EXISTS FOR (v:Vacante) ON (v.estado)",
    "CREATE INDEX skill_categoria IF NOT EXISTS FOR (s:Skill) ON (s.categoria)",
]


class Command(BaseCommand):
    help = "Crea restricciones de unicidad e índices en Neo4j."

    def handle(self, *args, **options):
        for sentencia in ESQUEMA:
            Neo4jConnection.write(sentencia)
            self.stdout.write(self.style.SUCCESS(f"OK · {sentencia[:58]}..."))
        self.stdout.write(self.style.SUCCESS(
            f"Esquema del grafo inicializado ({len(ESQUEMA)} sentencias)."
        ))
