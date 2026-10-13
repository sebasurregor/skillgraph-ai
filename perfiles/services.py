"""Lógica de negocio de los perfiles de candidato."""
import logging
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.db.models import Max

from GraphCore import servicio_grafo
from perfiles.extraccion import extractor, lectores
from perfiles.models import (HabilidadCandidato, HojaDeVida, PerfilCandidato,
                             PreferenciaLaboral, VersionPerfil)
from vacantes.models import AreaOcupacional, Habilidad, Vacante

logger = logging.getLogger(__name__)

CAMPOS_PERFIL = ("nombre_completo", "correo", "telefono", "experiencia", "educacion")


def perfil_de(usuario):
    perfil, _ = PerfilCandidato.objects.get_or_create(usuario=usuario)
    return perfil


def tiene_perfil_confirmado(usuario):
    return PerfilCandidato.objects.filter(usuario=usuario, confirmado=True).exists()


def niveles_de(perfil):
    """{nombre de habilidad: nivel} del perfil."""
    return dict(perfil.habilidades.values_list("habilidad__nombre", "nivel"))


@transaction.atomic
def guardar_habilidades(perfil, niveles, por_aprender=None):
    """Reemplaza las habilidades del perfil.

    `niveles`: {nombre de habilidad: nivel de 1 a 5}. `por_aprender`: nombres de habilidades
    (None deja las actuales). Los nombres que no estén en el catálogo se ignoran.
    """
    catalogo = {h.nombre: h for h in Habilidad.objects.filter(
        nombre__in=list(niveles) + list(por_aprender or ()))}
    perfil.habilidades.all().delete()
    HabilidadCandidato.objects.bulk_create([
        HabilidadCandidato(perfil=perfil, habilidad=catalogo[nombre],
                           nivel=max(1, min(5, int(nivel))))
        for nombre, nivel in niveles.items() if nombre in catalogo
    ])
    if por_aprender is not None:
        perfil.por_aprender.set([catalogo[n] for n in por_aprender if n in catalogo])
    return perfil


# ---- Hoja de vida (HU-RF-003) -------------------------------------------------

class ArchivoRechazado(Exception):
    """El archivo no es una hoja de vida admisible. El mensaje es para el usuario."""


FIRMAS = {"pdf": b"%PDF", "docx": b"PK\x03\x04"}
MSG_FORMATO = ("Formato no admitido. Suba su hoja de vida en PDF o en Word (.docx). "
               "Otros formatos, como .doc, imágenes o .txt, no se aceptan.")


def validar_archivo_cv(archivo):
    """Devuelve el formato ("pdf" o "docx") o lanza `ArchivoRechazado`."""
    formato = Path(archivo.name).suffix.lower().lstrip(".")
    if formato not in FIRMAS:
        raise ArchivoRechazado(MSG_FORMATO)
    if archivo.size > settings.CV_TAMANO_MAXIMO:
        raise ArchivoRechazado(
            f"El archivo pesa {archivo.size / 1024 / 1024:.1f} MB y el máximo permitido "
            "es 5 MB. Reduzca su tamaño o súbalo en otro formato.")
    if archivo.size == 0:
        raise ArchivoRechazado("El archivo está vacío. Seleccione otro.")
    archivo.seek(0)
    cabecera = archivo.read(4)
    archivo.seek(0)
    if cabecera != FIRMAS[formato]:
        raise ArchivoRechazado(MSG_FORMATO)
    return formato


def procesar_hoja_de_vida(perfil, archivo):
    """Guarda el archivo, lo lee y extrae sus datos. No modifica el perfil todavía."""
    formato = validar_archivo_cv(archivo)
    catalogo = list(Habilidad.objects.values_list("nombre", flat=True))
    try:
        lectura = lectores.leer(archivo, formato)
        datos = extractor.extraer(lectura.texto, catalogo, lectura.titular_probable)
        texto = lectura.texto
    except lectores.ArchivoIlegible:
        logger.warning("Hoja de vida ilegible (usuario %s)", perfil.usuario_id)
        datos, texto = extractor.DatosExtraidos(), ""
    archivo.seek(0)
    hoja = HojaDeVida.objects.create(
        perfil=perfil, archivo=archivo, nombre_original=Path(archivo.name).name[:255],
        formato=formato, tamano=archivo.size, texto=texto,
        datos_extraidos=datos.como_dict(), suficiente=datos.suficiente)
    logger.info("Hoja de vida %s procesada: faltan %d campos", hoja.pk, len(datos.faltantes))
    return hoja


def datos_para_confirmar(perfil, hoja=None):
    """Valores con los que se precarga el formulario de confirmación.

    Con hoja de vida: lo extraído. Sin ella: el perfil actual o los datos de la cuenta.
    """
    if hoja is not None:
        extraido = hoja.datos_extraidos
        return {"nombre_completo": extraido.get("nombre", ""),
                "correo": extraido.get("correo", ""),
                "telefono": extraido.get("telefono", ""),
                "experiencia": extraido.get("experiencia", ""),
                "educacion": extraido.get("educacion", ""),
                "niveles": extraido.get("habilidades", {})}
    usuario = perfil.usuario
    return {"nombre_completo": perfil.nombre_completo or usuario.get_full_name(),
            "correo": perfil.correo or usuario.email,
            "telefono": perfil.telefono or usuario.telefono,
            "experiencia": perfil.experiencia, "educacion": perfil.educacion,
            "niveles": niveles_de(perfil)}


@transaction.atomic
def confirmar_perfil(perfil, datos=None, niveles=None, hoja=None):
    """Deja el perfil confirmado, guarda una versión válida y lo lleva al grafo.

    `datos`: {nombre_completo, correo, telefono, experiencia, educacion}; `niveles`:
    {habilidad: nivel}. Sin ellos se confirma el perfil tal como está.
    Devuelve True si quedó sincronizado en Neo4j.
    """
    for campo in CAMPOS_PERFIL:
        if datos and campo in datos:
            setattr(perfil, campo, datos[campo])
    perfil.confirmado = True
    perfil.save()
    if niveles is not None:
        guardar_habilidades(perfil, niveles)

    numero = (perfil.versiones.aggregate(n=Max("numero"))["n"] or 0) + 1
    VersionPerfil.objects.create(
        perfil=perfil, numero=numero, hoja_de_vida=hoja,
        origen=VersionPerfil.Origen.HOJA_DE_VIDA if hoja else VersionPerfil.Origen.MANUAL,
        datos={**{c: getattr(perfil, c) for c in CAMPOS_PERFIL},
               "habilidades": niveles_de(perfil)})
    logger.info("Perfil del usuario %s confirmado (versión %d)", perfil.usuario_id, numero)
    return sincronizar_candidato_en_grafo(perfil)


def version_vigente(perfil):
    return perfil.versiones.first()


def catalogo_agrupado():
    """Habilidades agrupadas para mostrarlas: transversales y luego por área."""
    grupos = [("Sirven en cualquier oficio", list(Habilidad.objects.filter(transversal=True)))]
    vistas = {h.pk for h in grupos[0][1]}
    for area in AreaOcupacional.objects.prefetch_related("habilidades"):
        propias = [h for h in area.habilidades.all() if h.pk not in vistas]
        vistas.update(h.pk for h in propias)
        if propias:
            grupos.append((area.nombre, propias))
    return grupos


def sincronizar_candidato_en_grafo(perfil):
    usuario = perfil.usuario
    return servicio_grafo.sincronizar_candidato(
        usuario.pk,
        {"titular": perfil.nombre_completo or usuario.get_full_name(), "ciudad": usuario.ciudad},
        [{"nombre": h.habilidad.nombre, "nivel": h.nivel}
         for h in perfil.habilidades.select_related("habilidad")],
    )


# ---- Preferencias laborales (HU-RF-004) ---------------------------------------

CIUDADES_BASE = ["Medellín", "Bogotá", "Cali", "Barranquilla", "Bucaramanga", "Pereira", "Remoto"]
CAMPOS_PREFERENCIAS = ("cargos", "ubicaciones", "tipos_contrato", "salario_min", "salario_max")


def preferencias_de(perfil):
    """Preferencias guardadas del perfil, o None si nunca las ha definido."""
    return PreferenciaLaboral.objects.filter(perfil=perfil).first()


def opciones_de_preferencias(preferencias=None):
    """Opciones que se ofrecen: salen de las vacantes publicadas, más lo ya elegido."""
    publicadas = Vacante.objects.filter(estado=Vacante.Estado.PUBLICADA)
    elegidos = preferencias or PreferenciaLaboral()

    def unir(base, propios):
        return sorted({v for v in list(base) + list(propios) if v})

    return {
        "cargos": unir(publicadas.values_list("cargo", flat=True), elegidos.cargos),
        "ubicaciones": unir(CIUDADES_BASE + list(publicadas.values_list("ciudad", flat=True)),
                            elegidos.ubicaciones),
        "tipos_contrato": [j for j, _ in Vacante.JORNADAS],
    }


@transaction.atomic
def guardar_preferencias(perfil, datos, por_aprender=None):
    """Crea o actualiza las preferencias. `por_aprender`: habilidades (modelos) o None."""
    preferencias, _ = PreferenciaLaboral.objects.get_or_create(perfil=perfil)
    for campo in CAMPOS_PREFERENCIAS:
        if campo in datos:
            setattr(preferencias, campo, datos[campo])
    preferencias.save()
    if por_aprender is not None:
        perfil.por_aprender.set(por_aprender)
    logger.info("Preferencias del usuario %s actualizadas", perfil.usuario_id)
    return preferencias
