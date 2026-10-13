"""Lógica de negocio de las vacantes (HU-RF-011). Las vistas solo llaman a estas funciones."""
import json
import logging
from decimal import Decimal
from pathlib import Path

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from GraphCore import servicio_grafo
from vacantes.models import AreaOcupacional, Habilidad, RequisitoVacante, Vacante

logger = logging.getLogger(__name__)

DATOS = Path(__file__).resolve().parent / "datos"
SUMA_EXIGIDA = Decimal("1.00")
CAMPOS_PARA_PUBLICAR = ("titulo", "empresa", "descripcion", "area", "ciudad", "modalidad",
                        "jornada", "salario")
CAMPOS_EDITABLES = CAMPOS_PARA_PUBLICAR + ("cargo",)


class ErrorDeNegocio(Exception):
    """Regla de negocio incumplida. `errores` es una lista de mensajes para el usuario."""

    def __init__(self, errores):
        self.errores = [errores] if isinstance(errores, str) else list(errores)
        super().__init__(" ".join(self.errores))


# ---- Catálogo de habilidades ------------------------------------------------

def cargar_catalogo():
    """Carga en SQLite las 16 áreas y sus habilidades desde `datos/catalogo.json`."""
    catalogo = json.loads((DATOS / "catalogo.json").read_text(encoding="utf-8"))
    for nombre in catalogo["transversales"]:
        Habilidad.objects.update_or_create(nombre=nombre, defaults={"transversal": True})
    for orden, datos in enumerate(catalogo["areas"], start=1):
        area, _ = AreaOcupacional.objects.update_or_create(
            nombre=datos["nombre"], defaults={"orden": orden})
        for nombre in datos["habilidades"]:
            habilidad, _ = Habilidad.objects.get_or_create(nombre=nombre)
            habilidad.areas.add(area)
    return Habilidad.objects.count()


def sincronizar_catalogo_en_grafo():
    habilidades = Habilidad.objects.prefetch_related("areas")
    return servicio_grafo.sincronizar_habilidades(
        {"nombre": h.nombre, "categoria": h.categoria} for h in habilidades)


# ---- Reglas de publicación --------------------------------------------------

def suma_de_pesos(requisitos):
    return sum((Decimal(str(r["peso"])) for r in requisitos), Decimal("0"))


def errores_de_requisitos(requisitos):
    """Reglas sobre las habilidades ponderadas de una vacante que se va a publicar."""
    if not requisitos:
        return ["Agregue al menos una habilidad con su peso antes de publicar."]
    suma = suma_de_pesos(requisitos)
    if suma != SUMA_EXIGIDA:
        return [f"La suma de los pesos debe ser igual a 1.00. Actualmente suma {suma:.2f}."]
    return []


def errores_de_publicacion(datos, requisitos):
    errores = []
    faltantes = [c for c in CAMPOS_PARA_PUBLICAR if datos.get(c) in (None, "")]
    if faltantes:
        errores.append("Complete todos los datos de la vacante antes de publicarla.")
    return errores + errores_de_requisitos(requisitos)


# ---- Consultas --------------------------------------------------------------

def vacantes_de(reclutador):
    return (Vacante.objects.filter(reclutador=reclutador)
            .select_related("area")
            .annotate(num_requisitos=Count("requisitos"))
            .order_by("-actualizada_en"))


def requisitos_de(vacante):
    """Requisitos como datos planos, en el formato que usan los servicios."""
    return [{"habilidad": r.habilidad, "peso": r.peso, "nivel_minimo": r.nivel_minimo,
             "obligatoria": r.obligatoria}
            for r in vacante.requisitos.select_related("habilidad")]


def calcular_centralidad(habilidades, excluir=None):
    """Qué tan demandadas son las habilidades de la vacante entre las ya publicadas (0 a 1)."""
    publicadas = Q(requisitos__vacante__estado=Vacante.Estado.PUBLICADA)
    if excluir is not None:
        publicadas &= ~Q(requisitos__vacante=excluir)
    demanda = dict(Habilidad.objects.annotate(n=Count("requisitos", filter=publicadas))
                   .filter(n__gt=0).values_list("pk", "n"))
    if not demanda or not habilidades:
        return 0.5
    maximo = max(demanda.values())
    promedio = sum(demanda.get(h.pk, 0) for h in habilidades) / (maximo * len(habilidades))
    return round(0.5 + 0.5 * promedio, 2)


# ---- Escrituras -------------------------------------------------------------

@transaction.atomic
def guardar_vacante(reclutador, datos, requisitos, *, publicar, vacante=None, centralidad=None):
    """Crea o actualiza una vacante con sus habilidades ponderadas.

    Con `publicar=False` queda como borrador y no se le exigen las reglas de publicación.
    Devuelve (vacante, en_grafo): `en_grafo` es False si Neo4j no pudo sincronizarse.
    """
    if publicar:
        errores = errores_de_publicacion(datos, requisitos)
        if errores:
            raise ErrorDeNegocio(errores)

    vacante = vacante or Vacante(reclutador=reclutador)
    for campo in CAMPOS_EDITABLES:
        if campo in datos:
            setattr(vacante, campo, datos[campo])
    if not vacante.empresa:
        vacante.empresa = reclutador.empresa
    vacante.save()

    vacante.requisitos.all().delete()
    RequisitoVacante.objects.bulk_create([
        RequisitoVacante(vacante=vacante, habilidad=r["habilidad"], peso=r["peso"],
                         nivel_minimo=r["nivel_minimo"], obligatoria=r["obligatoria"])
        for r in requisitos
    ])

    if publicar:
        return vacante, _publicar(vacante, centralidad)
    return vacante, _despublicar(vacante)


@transaction.atomic
def publicar_vacante(vacante):
    """Publica un borrador ya guardado, si cumple las reglas."""
    datos = {c: getattr(vacante, c) for c in CAMPOS_PARA_PUBLICAR}
    errores = errores_de_publicacion(datos, requisitos_de(vacante))
    if errores:
        raise ErrorDeNegocio(errores)
    return _publicar(vacante)


def despublicar_vacante(vacante):
    return _despublicar(vacante)


def eliminar_vacante(vacante):
    vacante_id = vacante.pk
    vacante.delete()
    logger.info("Vacante %s eliminada", vacante_id)
    return servicio_grafo.retirar_vacante(vacante_id)


def _publicar(vacante, centralidad=None):
    if centralidad is None:
        habilidades = [r.habilidad for r in vacante.requisitos.select_related("habilidad")]
        centralidad = calcular_centralidad(habilidades, excluir=vacante)
    vacante.centralidad = centralidad
    vacante.estado = Vacante.Estado.PUBLICADA
    vacante.publicada_en = vacante.publicada_en or timezone.now()
    vacante.save()
    logger.info("Vacante %s publicada", vacante.pk)
    return sincronizar_vacante_en_grafo(vacante)


def _despublicar(vacante):
    estaba_publicada = vacante.publicada
    vacante.estado = Vacante.Estado.BORRADOR
    vacante.publicada_en = None
    vacante.save()
    if not estaba_publicada:
        return True
    logger.info("Vacante %s despublicada", vacante.pk)
    return servicio_grafo.retirar_vacante(vacante.pk)


def sincronizar_vacante_en_grafo(vacante):
    return servicio_grafo.sincronizar_vacante(
        vacante.pk,
        {"titulo": vacante.titulo, "empresa": vacante.empresa, "ciudad": vacante.ciudad,
         "estado": vacante.estado, "centralidad": vacante.centralidad},
        [{"nombre": r.habilidad.nombre, "peso": float(r.peso), "nivel_min": r.nivel_minimo,
          "obligatoria": r.obligatoria}
         for r in vacante.requisitos.select_related("habilidad")],
    )
