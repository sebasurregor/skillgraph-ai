"""Reconstruye en Neo4j lo que ya está en SQLite (por ejemplo, tras una caída del grafo)."""
from perfiles import services as perfiles
from perfiles.models import PerfilCandidato
from vacantes import services as vacantes
from vacantes.models import Vacante


def sincronizar_todo():
    """Devuelve {habilidades, vacantes, candidatos} o None si Neo4j no está disponible."""
    if not vacantes.sincronizar_catalogo_en_grafo():
        return None
    publicadas = Vacante.objects.filter(estado=Vacante.Estado.PUBLICADA)
    confirmados = PerfilCandidato.objects.filter(confirmado=True).select_related("usuario")
    hechas = [vacantes.sincronizar_vacante_en_grafo(v) for v in publicadas]
    hechos = [perfiles.sincronizar_candidato_en_grafo(p) for p in confirmados]
    if not all(hechas + hechos):
        return None
    return {"vacantes": len(hechas), "candidatos": len(hechos)}
