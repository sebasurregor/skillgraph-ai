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
                candidato=perfil, vacante=vacante, ajuste_al_postular=match.pct,
                perfil_al_postular=fotografia_del_perfil(perfil))
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

    El reclutador ve el perfil con el que cada candidato se postuló: el match, el
    orden y el filtro salen de esa fotografía. Aparte se le muestra qué cambió en
    el perfil desde entonces y cuál sería el match hoy. Todo se calcula con el
    servicio único de `matching`.
    Devuelve {items: [{postulacion, perfil, match, match_actual, cambios, hoja_de_vida}],
    total, cumplen, aviso}; `perfil` es la fotografía (un diccionario).
    """
    postulaciones = list(vacante.postulaciones.select_related("candidato__usuario"))
    candidatos = [p.candidato for p in postulaciones]
    actuales, aviso = matching.calcular_lote(candidatos, [vacante])

    items = []
    for p in postulaciones:
        actual = fotografia_del_perfil(p.candidato)
        foto = p.perfil_al_postular or actual      # postulaciones anteriores a la fotografía
        match = matching.match_de_instantanea(
            foto["habilidades"], foto.get("por_aprender", []), vacante)
        match_actual = actuales[(p.candidato.pk, vacante.pk)]
        items.append({
            "postulacion": p, "perfil": foto, "match": match, "match_actual": match_actual,
            "cambios": cambios_del_perfil(foto, actual, match.pct, match_actual.pct),
            "hoja_de_vida": hoja_de_vida_de(p)})
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
    """Hoja de vida original con la que el candidato se postuló, si subió alguna."""
    perfil = postulacion.candidato
    foto = postulacion.perfil_al_postular
    if foto:
        return perfil.hojas_de_vida.filter(pk=foto.get("hoja_de_vida_id")).first()
    return _hoja_de_vida_vigente(perfil)


def _hoja_de_vida_vigente(perfil):
    vigente = perfiles.version_vigente(perfil)
    if vigente and vigente.hoja_de_vida_id:
        return vigente.hoja_de_vida
    return perfil.hojas_de_vida.first()


# ---- Fotografía del perfil y cambios desde la postulación ----------------------

DATOS_COMPARADOS = (("nombre_completo", "nombre"), ("correo", "correo"),
                    ("telefono", "teléfono"), ("experiencia", "experiencia"),
                    ("educacion", "educación"))


def fotografia_del_perfil(perfil):
    """El perfil tal como está ahora, como datos planos que se pueden guardar."""
    usuario = perfil.usuario
    vigente = perfiles.version_vigente(perfil)
    hoja = _hoja_de_vida_vigente(perfil)
    return {
        "nombre_completo": perfil.nombre_completo or usuario.get_full_name(),
        "correo": perfil.correo or usuario.email,
        "telefono": perfil.telefono or usuario.telefono,
        "ciudad": usuario.ciudad,
        "experiencia": perfil.experiencia, "educacion": perfil.educacion,
        "habilidades": perfiles.niveles_de(perfil),
        "por_aprender": sorted(perfil.por_aprender.values_list("nombre", flat=True)),
        "version": vigente.numero if vigente else None,
        "hoja_de_vida_id": hoja.pk if hoja else None,
    }


def cambios_del_perfil(antes, ahora, pct_antes, pct_ahora):
    """Qué cambió en el perfil desde que el candidato se postuló.

    Devuelve {hay, nuevas, retiradas, niveles, datos, pct_antes, pct_ahora, diferencia}.
    """
    h_antes, h_ahora = antes["habilidades"], ahora["habilidades"]
    cambios = {
        "nuevas": [{"nombre": n, "nivel": h_ahora[n]} for n in sorted(h_ahora.keys() - h_antes)],
        "retiradas": sorted(h_antes.keys() - h_ahora),
        "niveles": [{"nombre": n, "antes": h_antes[n], "ahora": h_ahora[n]}
                    for n in sorted(h_antes.keys() & h_ahora) if h_antes[n] != h_ahora[n]],
        "datos": [nombre for campo, nombre in DATOS_COMPARADOS
                  if antes.get(campo) != ahora.get(campo)],
        "pct_antes": pct_antes, "pct_ahora": pct_ahora, "diferencia": pct_ahora - pct_antes,
    }
    cambios["hay"] = bool(cambios["nuevas"] or cambios["retiradas"] or cambios["niveles"]
                          or cambios["datos"])
    return cambios
