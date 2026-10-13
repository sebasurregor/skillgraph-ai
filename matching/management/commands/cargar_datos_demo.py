from django.core.management import call_command
from django.core.management.base import BaseCommand

from GraphCore import servicio_grafo
from matching import demo


class Command(BaseCommand):
    help = ("Carga el catálogo de 16 áreas, las vacantes de demostración, un reclutador y los "
            "candidatos Ana María Ríos y Camilo Zapata, en SQLite y en Neo4j.")

    def handle(self, *args, **options):
        if servicio_grafo.disponible():
            call_command("init_graph", stdout=self.stdout)
        resumen = demo.cargar()

        self.stdout.write(self.style.SUCCESS(
            f"SQLite: {resumen['habilidades']} habilidades, {resumen['vacantes']} vacantes "
            f"publicadas y {resumen['candidatos']} candidatos."))
        if resumen["en_grafo"]:
            self.stdout.write(self.style.SUCCESS("Neo4j: grafo sincronizado."))
        else:
            self.stdout.write(self.style.WARNING(
                "Neo4j no está disponible: los datos quedaron solo en SQLite. Cuando el grafo "
                "esté arriba ejecute: python manage.py init_graph && "
                "python manage.py sincronizar_grafo"))

        self.stdout.write("")
        self.stdout.write(f"Contraseña de todas las cuentas de demostración: {demo.CLAVE_DEMO}")
        self.stdout.write(f"  Reclutador : {demo.RECLUTADOR['email']}")
        for candidato in demo.CANDIDATOS:
            self.stdout.write(f"  Candidato  : {candidato['email']}")
