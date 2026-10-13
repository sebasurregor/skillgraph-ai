"""Diccionario de palabras clave y sinónimos, leído de `perfiles/datos/diccionario_cv.json`."""
import json
import unicodedata
from pathlib import Path

RUTA = Path(__file__).resolve().parent.parent / "datos" / "diccionario_cv.json"

_cache = {"mtime": None, "datos": None}


def normalizar(texto):
    """Minúsculas y sin tildes, conservando la longitud (ñ → n, Á → a)."""
    return "".join(unicodedata.normalize("NFD", c)[0] for c in texto).lower()


def cargar(ruta=None):
    """Devuelve el diccionario normalizado. Se recarga solo si el archivo cambió."""
    ruta = ruta or RUTA
    mtime = ruta.stat().st_mtime
    if _cache["mtime"] != (ruta, mtime):
        crudo = json.loads(ruta.read_text(encoding="utf-8"))
        _cache["datos"] = {
            "campos": {k: [normalizar(s) for s in v] for k, v in crudo["campos"].items()},
            "secciones": {normalizar(s): k for k, v in crudo["secciones"].items() for s in v},
            "niveles": {normalizar(k): v for k, v in crudo["niveles"].items()},
            "habilidades": {k: [normalizar(s) for s in v]
                            for k, v in crudo["habilidades"].items()},
        }
        _cache["mtime"] = (ruta, mtime)
    return _cache["datos"]


def alias_de_habilidades(nombres_catalogo, ruta=None):
    """{alias normalizado: nombre del catálogo}. Incluye el propio nombre de cada habilidad.

    Los sinónimos de habilidades que no estén en el catálogo se descartan: toda
    habilidad reconocida debe corresponder a un nodo :Skill.
    """
    sinonimos = cargar(ruta)["habilidades"]
    alias = {}
    for nombre in nombres_catalogo:
        for termino in [normalizar(nombre)] + sinonimos.get(nombre, []):
            alias.setdefault(termino, nombre)
    return alias
