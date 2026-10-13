"""Lógica de negocio de los perfiles de candidato."""
import logging

from django.db import transaction

from GraphCore import servicio_grafo
from perfiles.models import HabilidadCandidato, PerfilCandidato
from vacantes.models import Habilidad

logger = logging.getLogger(__name__)


def perfil_de(usuario):
    perfil, _ = PerfilCandidato.objects.get_or_create(usuario=usuario)
    return perfil


@transaction.atomic
def guardar_habilidades(perfil, niveles, por_aprender=()):
    """Reemplaza las habilidades del perfil.

    `niveles`: {nombre de habilidad: nivel de 1 a 5}. `por_aprender`: nombres de habilidades.
    Los nombres que no estén en el catálogo se ignoran.
    """
    catalogo = {h.nombre: h for h in Habilidad.objects.filter(
        nombre__in=list(niveles) + list(por_aprender))}
    perfil.habilidades.all().delete()
    HabilidadCandidato.objects.bulk_create([
        HabilidadCandidato(perfil=perfil, habilidad=catalogo[nombre],
                           nivel=max(1, min(5, int(nivel))))
        for nombre, nivel in niveles.items() if nombre in catalogo
    ])
    perfil.por_aprender.set([catalogo[n] for n in por_aprender if n in catalogo])
    return perfil


def confirmar_perfil(perfil):
    """Marca el perfil como confirmado y lo lleva al grafo."""
    perfil.confirmado = True
    perfil.save()
    logger.info("Perfil del usuario %s confirmado", perfil.usuario_id)
    return sincronizar_candidato_en_grafo(perfil)


def sincronizar_candidato_en_grafo(perfil):
    usuario = perfil.usuario
    return servicio_grafo.sincronizar_candidato(
        usuario.pk,
        {"titular": usuario.get_full_name(), "ciudad": usuario.ciudad},
        [{"nombre": h.habilidad.nombre, "nivel": h.nivel}
         for h in perfil.habilidades.select_related("habilidad")],
    )
