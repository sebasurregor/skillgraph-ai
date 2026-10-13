from django.core.management.base import BaseCommand, CommandError

from matching.sincronizacion import sincronizar_todo


class Command(BaseCommand):
    help = "Lleva a Neo4j las habilidades, vacantes publicadas y perfiles confirmados de SQLite."

    def handle(self, *args, **options):
        resumen = sincronizar_todo()
        if resumen is None:
            raise CommandError("Neo4j no está disponible. Revise que el servidor esté iniciado "
                               "y las credenciales del archivo .env.")
        self.stdout.write(self.style.SUCCESS(
            f"Grafo sincronizado: {resumen['vacantes']} vacantes y "
            f"{resumen['candidatos']} candidatos."))
