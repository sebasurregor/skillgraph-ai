"""Extrae nombre, correo, teléfono, experiencia, educación y habilidades del texto de un CV."""
import re
from dataclasses import asdict, dataclass, field

from perfiles.extraccion import diccionario
from perfiles.extraccion.diccionario import normalizar

CAMPOS = ("nombre", "correo", "telefono", "experiencia", "educacion", "habilidades")
MIN_CAMPOS_SUFICIENTES = 2
NIVEL_POR_DEFECTO = 3

RE_CORREO = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
RE_CELULAR = re.compile(r"(?<!\d)(?:\+?57[\s.-]?)?(3\d{2})[\s.-]?(\d{3})[\s.-]?(\d{4})(?!\d)")
RE_FIJO = re.compile(r"(?<!\d)(60\d)[\s.-]?(\d{3})[\s.-]?(\d{4})(?!\d)")
RE_NOMBRE = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ'’.]+(?: [A-Za-zÁÉÍÓÚÜÑáéíóúüñ'’.]+){1,5}$")
PARTICULAS = {"de", "del", "la", "las", "los", "y", "da", "dos"}
SEPARADOR_ROTULO = r"\s*[:\-–—]\s*"


@dataclass
class DatosExtraidos:
    nombre: str = ""
    correo: str = ""
    telefono: str = ""
    experiencia: str = ""
    educacion: str = ""
    habilidades: dict = field(default_factory=dict)     # {nombre del catálogo: nivel}

    @property
    def faltantes(self):
        """Campos que no se pudieron extraer."""
        return [c for c in CAMPOS if not getattr(self, c)]

    @property
    def suficiente(self):
        return len(CAMPOS) - len(self.faltantes) >= MIN_CAMPOS_SUFICIENTES

    def como_dict(self):
        return {**asdict(self), "faltantes": self.faltantes, "suficiente": self.suficiente}


def extraer(texto, nombres_catalogo, titular_probable=""):
    """`nombres_catalogo`: nombres de las habilidades que existen como nodos :Skill."""
    dic = diccionario.cargar()
    lineas = [linea.strip() for linea in texto.splitlines() if linea.strip()]
    secciones = _secciones(lineas, dic)
    return DatosExtraidos(
        nombre=_nombre(lineas, titular_probable, dic),
        correo=_correo(texto),
        telefono=_telefono(texto),
        experiencia="\n".join(secciones.get("experiencia", [])),
        educacion="\n".join(secciones.get("educacion", [])),
        habilidades=_habilidades(texto, nombres_catalogo, dic),
    )


# ---- Campos simples -----------------------------------------------------------

def _correo(texto):
    encontrado = RE_CORREO.search(texto)
    return encontrado.group(0).lower().rstrip(".") if encontrado else ""


def _telefono(texto):
    encontrado = RE_CELULAR.search(texto) or RE_FIJO.search(texto)
    return "".join(encontrado.groups()) if encontrado else ""


def _rotulado(lineas, sinonimos):
    """Valor de un renglón «Rótulo: valor», o del renglón que sigue a un rótulo solo."""
    patron = re.compile(
        r"^(?:%s)(?:%s(?P<valor>.+))?$" % (
            "|".join(sorted(map(re.escape, sinonimos), key=len, reverse=True)),
            SEPARADOR_ROTULO))
    for i, linea in enumerate(lineas):
        hallado = patron.match(normalizar(linea))
        if not hallado:
            continue
        if hallado.group("valor"):
            return linea[hallado.start("valor"):].strip()
        if i + 1 < len(lineas):
            return lineas[i + 1]
    return ""


def _parece_nombre(linea, dic):
    if not RE_NOMBRE.match(linea) or len(linea) > 60:
        return False
    if _titulo_de_seccion(linea, dic)[0]:
        return False
    palabras = [p for p in linea.split() if p.lower() not in PARTICULAS]
    return len(palabras) >= 2 and all(p[0].isupper() for p in palabras)


def _nombre(lineas, titular_probable, dic):
    candidatos = [_rotulado(lineas, dic["campos"]["nombre"]), titular_probable] + lineas[:8]
    for candidato in candidatos:
        if candidato and _parece_nombre(candidato, dic):
            return candidato.title() if candidato.isupper() else candidato
    return ""


# ---- Secciones ----------------------------------------------------------------

def _titulo_de_seccion(linea, dic):
    """Devuelve (sección, resto del renglón) si el renglón abre una sección."""
    limpio = normalizar(linea).strip(" :.-–—•")
    if limpio in dic["secciones"]:
        return dic["secciones"][limpio], ""
    rotulo, separador, resto = linea.partition(":")
    if separador and resto.strip():
        seccion = dic["secciones"].get(normalizar(rotulo).strip())
        if seccion:
            return seccion, resto.strip()
    return None, ""


def _secciones(lineas, dic):
    secciones, actual = {}, None
    for linea in lineas:
        seccion, resto = _titulo_de_seccion(linea, dic)
        if seccion:
            actual = secciones.setdefault(seccion, [])
            if resto:
                actual.append(resto)
        elif actual is not None:
            actual.append(linea.lstrip("•-–* ").strip())
    return secciones


# ---- Habilidades --------------------------------------------------------------

def _habilidades(texto, nombres_catalogo, dic):
    """Busca cada habilidad del catálogo (o un sinónimo) como palabra completa."""
    plano = normalizar(texto)
    alias = diccionario.alias_de_habilidades(nombres_catalogo)
    niveles = "|".join(sorted(map(re.escape, dic["niveles"]), key=len, reverse=True))
    re_nivel = re.compile(r"[\s:(\-–]{0,4}(?:nivel\s+)?(%s)\b" % niveles)

    ocupado = [False] * len(plano)
    halladas = {}
    # Primero los términos largos: «redes sociales» no debe contarse además como «redes».
    for termino in sorted(alias, key=len, reverse=True):
        patron = re.compile(r"(?<![a-z0-9])%s(?![a-z0-9])" % re.escape(termino))
        for hallado in patron.finditer(plano):
            inicio, fin = hallado.span()
            if any(ocupado[inicio:fin]):
                continue
            ocupado[inicio:fin] = [True] * (fin - inicio)
            nivel = re_nivel.match(plano, fin)
            valor = dic["niveles"][nivel.group(1)] if nivel else None
            nombre = alias[termino]
            if nombre not in halladas or (valor and not halladas[nombre]):
                halladas[nombre] = valor
    return {nombre: nivel or NIVEL_POR_DEFECTO for nombre, nivel in sorted(halladas.items())}
