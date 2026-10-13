"""Lógica de negocio de las postulaciones (HU-RF-006 y HU-RF-013)."""
import logging

from django.db import IntegrityError, transaction

from matching import services as matching
from perfiles import services as perfiles
from postulaciones.models import Postulacion
from vacantes.models import Vacante

logger = logging.getLogger(__name__)


class PostulacionRechazada(Exception):
    """No se puede postular. El mensaje es para el usuario."""


# ---- Candidato (HU-RF-006) ----------------------------------------------------

def postular(usuario, vacante_id):
    """Postula al candidato a la vacante con un solo paso.

    Devuelve (postulación, creada). Si ya se había postulado devuelve la existente
    con `creada=False`: nunca hay dos postulaciones a la misma vacante.
    """
    vacante = Vacante.objects.filter(pk=vacante_id, estado=Vacante.Estado.PUBLICADA).first()
    if vacante is None:
        raise PostulacionRechazada("Esta vacante ya no está disponible.")
    if not perfiles.tiene_perfil_confirmado(usuario):
        raise PostulacionRechazada("Confirme su perfil antes de postularse.")
    perfil = perfiles.perfil_de(usuario)

    existente = Postulacion.objects.filter(candidato=perfil, vacante=vacante).first()
    if existente:
        return existente, False
    match, _ = matching.match_de(perfil, vacante)
    try:
        with transaction.atomic():
            postulacion = Postulacion.objects.create(
                candidato=perfil, vacante=vacante, ajuste_al_postular=match.pct)
    except IntegrityError:      # dos envíos simultáneos: la base de datos garantiza la unicidad
        return Postulacion.objects.get(candidato=perfil, vacante=vacante), False
    logger.info("Postulación %s creada (vacante %s)", postulacion.pk, vacante.pk)
    return postulacion, True


def postulaciones_de(usuario):
    """Postulaciones del candidato, con el estado de cada una."""
    return (Postulacion.objects.filter(candidato__usuario=usuario)
            .select_related("vacante").order_by("-creada_en"))


def vacantes_postuladas(usuario):
    """Ids de las vacantes a las que el candidato ya se postuló."""
    return set(Postulacion.objects.filter(candidato__usuario=usuario)
               .values_list("vacante_id", flat=True))


# ---- Reclutador (HU-RF-013) ---------------------------------------------------

def priorizadas(vacante, solo_obligatorias=False):
    """Postulaciones de la vacante ordenadas de mayor a menor match.

    El match se calcula con el servicio único de `matching`, sobre el perfil actual.
    Devuelve {items: [{postulacion, perfil, match}], total, cumplen, aviso}.
    """
    postulaciones = list(vacante.postulaciones.select_related("candidato__usuario"))
    candidatos = [p.candidato for p in postulaciones]
    resultados, aviso = matching.calcular_lote(candidatos, [vacante])

    items = [{"postulacion": p, "perfil": p.candidato,
              "match": resultados[(p.candidato.pk, vacante.pk)],
              "hoja_de_vida": hoja_de_vida_de(p)}
             for p in postulaciones]
    items.sort(key=lambda i: (-i["match"].pct, i["postulacion"].creada_en))
    cumplen = [i for i in items if i["match"].cumple_obligatorias]
    return {"items": cumplen if solo_obligatorias else items, "total": len(items),
            "cumplen": len(cumplen), "aviso": aviso}


def cambiar_estado(postulacion, estado):
    if estado not in Postulacion.Estado.values:
        raise PostulacionRechazada("Ese estado no existe.")
    postulacion.estado = estado
    postulacion.save()
    logger.info("Postulación %s pasó a %s", postulacion.pk, estado)
    return postulacion


def hoja_de_vida_de(postulacion):
    """Hoja de vida original del candidato: la de su versión válida o la última que subió."""
    perfil = postulacion.candidato
    vigente = perfiles.version_vigente(perfil)
    if vigente and vigente.hoja_de_vida_id:
        return vigente.hoja_de_vida
    return perfil.hojas_de_vida.first()
