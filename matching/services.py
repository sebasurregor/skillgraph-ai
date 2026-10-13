"""Servicio de matching. Consulta el grafo y, si Neo4j no responde, usa SQLite."""
import logging

from django.db.models import Count, Q

from GraphCore import servicio_grafo
from GraphCore.servicio_grafo import GrafoNoDisponible
from perfiles.models import PerfilCandidato

logger = logging.getLogger(__name__)

FUENTE_GRAFO = "neo4j"
FUENTE_RESPALDO = "sqlite"
AVISO_RESPALDO = "Cálculo hecho sin el grafo: Neo4j no está disponible en este momento."


def _criterio(requisitos):
    """Qué habilidades se exigen y cuántas de ellas debe cubrir un candidato.

    Si la vacante marca habilidades obligatorias, hay que cubrirlas todas.
    Si no marca ninguna, basta con cubrir al menos una de las requeridas.
    """
    obligatorias = [r for r in requisitos if r["obligatoria"]]
    exigidas = obligatorias or list(requisitos)
    minimo = len(obligatorias) if obligatorias else 1
    return exigidas, minimo


def contar_candidatos_potenciales(requisitos):
    """Previsualización de HU-RF-011: cuántos candidatos cumplirían los requisitos.

    `requisitos`: lista de {habilidad (modelo), nivel_minimo, obligatoria}.
    Devuelve {candidatos, total, fuente, aviso}.
    """
    exigidas, minimo = _criterio(requisitos)
    if not exigidas:
        return {"candidatos": 0, "total": _total_sqlite(), "fuente": FUENTE_RESPALDO, "aviso": ""}
    try:
        candidatos = servicio_grafo.contar_candidatos_que_cubren(
            [{"nombre": r["habilidad"].nombre, "nivel_min": r["nivel_minimo"]} for r in exigidas],
            minimo)
        total = servicio_grafo.contar_candidatos()
        return {"candidatos": candidatos, "total": total, "fuente": FUENTE_GRAFO, "aviso": ""}
    except GrafoNoDisponible:
        logger.warning("Previsualización de candidatos calculada con el respaldo en SQLite")
        return {"candidatos": _contar_sqlite(exigidas, minimo), "total": _total_sqlite(),
                "fuente": FUENTE_RESPALDO, "aviso": AVISO_RESPALDO}


def _perfiles_confirmados():
    return PerfilCandidato.objects.filter(confirmado=True)


def _total_sqlite():
    return _perfiles_confirmados().count()


def _contar_sqlite(exigidas, minimo):
    cubre = Q()
    for r in exigidas:
        cubre |= Q(habilidades__habilidad=r["habilidad"], habilidades__nivel__gte=r["nivel_minimo"])
    return (_perfiles_confirmados()
            .annotate(cubiertas=Count("habilidades__habilidad", filter=cubre, distinct=True))
            .filter(cubiertas__gte=minimo).count())
