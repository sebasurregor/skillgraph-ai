"""Servicio de matching. Consulta el grafo y, si Neo4j no responde, usa SQLite."""
import logging
import math
from dataclasses import asdict, dataclass, field

from django.conf import settings
from django.db.models import Count, Q

from GraphCore import servicio_grafo
from GraphCore.servicio_grafo import GrafoNoDisponible
from perfiles import services as perfiles
from perfiles.models import PerfilCandidato
from vacantes.models import Vacante

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


# ---- Preferencias laborales (HU-RF-004) ---------------------------------------

def filtrar_por_preferencias(vacantes, preferencias):
    """Deja solo las vacantes que encajan con lo que el candidato dijo buscar.

    Dentro de cada preferencia basta una coincidencia (un cargo u otro); entre
    preferencias deben cumplirse todas. Una preferencia sin opciones no filtra.
    Del rango salarial se usa el mínimo: una vacante que paga más del máximo
    esperado no se descarta.
    """
    if preferencias is None:
        return vacantes
    if preferencias.cargos:
        vacantes = vacantes.filter(cargo__in=preferencias.cargos)
    if preferencias.ubicaciones:
        en_ciudad = Q(ciudad__in=preferencias.ubicaciones)
        if "Remoto" in preferencias.ubicaciones:
            en_ciudad |= Q(modalidad="Remoto")
        vacantes = vacantes.filter(en_ciudad)
    if preferencias.tipos_contrato:
        vacantes = vacantes.filter(jornada__in=preferencias.tipos_contrato)
    if preferencias.salario_min:
        vacantes = vacantes.filter(salario__gte=preferencias.salario_min)
    return vacantes


# ---- Cálculo del match (único para HU-RF-005 y HU-RF-013) ---------------------
#
# puntaje = W_COBERTURA · cobertura + W_NIVEL · nivel
#         + W_CENTRALIDAD · centralidad + W_ADYACENCIA · adyacencia
#
#   cobertura   = peso de las habilidades requeridas que el candidato tiene / peso total
#   nivel       = promedio ponderado de min(1, nivel del candidato / nivel mínimo exigido)
#                 sobre las habilidades cubiertas
#   centralidad = qué tan demandadas son las habilidades de la vacante (dato de la vacante)
#   adyacencia  = 0.1 + 0.9 · (habilidades faltantes que el candidato quiere aprender
#                 / habilidades faltantes); 0.9 si no le falta ninguna
#
# Es la misma fórmula de `calcular()` en prototipo/index.html.

ORDEN_RELEVANCIA = "relevancia"
ORDEN_FECHA = "fecha"


def pesos():
    return {"cobertura": settings.W_COBERTURA, "nivel": settings.W_NIVEL,
            "centralidad": settings.W_CENTRALIDAD, "adyacencia": settings.W_ADYACENCIA}


def _porcentaje(valor):
    """Redondeo aritmético (0.5 hacia arriba), como Math.round del prototipo."""
    return int(math.floor(valor * 100 + 0.5))


@dataclass
class Match:
    """Resultado explicable del ajuste entre un candidato y una vacante."""

    pct: int = 0
    pct_potencial: int = 0
    cobertura: float = 0.0
    nivel: float = 0.0
    centralidad: float = 0.0
    adyacencia: float = 0.0
    cubiertas: list = field(default_factory=list)   # {nombre, peso, nivel, nivel_min, obligatoria}
    faltantes: list = field(default_factory=list)   # {nombre, peso, nivel_min, obligatoria}
    version: str = ""

    @property
    def obligatorias_faltantes(self):
        return [f for f in self.faltantes if f["obligatoria"]]

    @property
    def cumple_obligatorias(self):
        return not self.obligatorias_faltantes

    @property
    def componentes(self):
        """Desglose para la explicación: (nombre, valor, peso del componente, aporte)."""
        w = pesos()
        return [
            {"clave": clave, "nombre": nombre, "valor": getattr(self, clave), "peso": w[clave],
             "aporte": getattr(self, clave) * w[clave]}
            for clave, nombre in (
                ("cobertura", "Cobertura ponderada de habilidades"),
                ("nivel", "Nivel declarado vs. nivel exigido"),
                ("centralidad", "Centralidad del rol en el grafo"),
                ("adyacencia", "Afinidad con habilidades adyacentes"))
        ]

    @property
    def texto(self):
        total = len(self.cubiertas) + len(self.faltantes)
        partes = [f"Usted cubre {len(self.cubiertas)} de las {total} habilidades que exige "
                  "esta vacante"]
        if self.cubiertas:
            nombres = ", ".join(c["nombre"] for c in self.cubiertas)
            partes.append(f" ({nombres}), que concentran el {_porcentaje(self.cobertura)} % "
                          "del peso definido por el contratante.")
        else:
            partes.append(".")
        if self.faltantes:
            mayor = self.faltantes[0]
            partes.append(
                f" Le falta {mayor['nombre']} (peso {mayor['peso']:.2f}, nivel mínimo "
                f"{mayor['nivel_min']}). Cerrar esa brecha llevaría su ajuste de {self.pct} % "
                f"a {self.pct_potencial} %.")
        else:
            partes.append(" No tiene brechas: cubre el total de las habilidades requeridas.")
        return "".join(partes)

    def como_dict(self):
        return {**asdict(self), "componentes": self.componentes, "texto": self.texto,
                "cumple_obligatorias": self.cumple_obligatorias,
                "obligatorias_faltantes": [f["nombre"] for f in self.obligatorias_faltantes]}


def calcular_match(niveles, por_aprender, requisitos, centralidad):
    """Fórmula del match. Función pura: no consulta ninguna base de datos.

    `niveles`: {habilidad: nivel del candidato}; `por_aprender`: nombres de habilidades;
    `requisitos`: lista de {nombre, peso, nivel_min, obligatoria}.
    """
    w = pesos()
    total = cubierto = nivel_ponderado = 0.0
    cubiertas, faltantes = [], []
    for r in requisitos:
        peso = float(r["peso"])
        total += peso
        declarado = niveles.get(r["nombre"])
        base = {"nombre": r["nombre"], "peso": peso, "nivel_min": r["nivel_min"],
                "obligatoria": bool(r["obligatoria"])}
        if declarado is None:
            faltantes.append(base)
            continue
        cubierto += peso
        nivel_ponderado += peso * min(1.0, declarado / r["nivel_min"])
        cubiertas.append({**base, "nivel": declarado})

    cobertura = cubierto / total if total else 0.0
    nivel = nivel_ponderado / cubierto if cubierto else 0.0
    if faltantes:
        alcanzables = sum(1 for f in faltantes if f["nombre"] in por_aprender)
        adyacencia = alcanzables / len(faltantes) * 0.9 + 0.1
    else:
        adyacencia = 0.9
    fijo = w["centralidad"] * centralidad + w["adyacencia"] * adyacencia
    puntaje = w["cobertura"] * cobertura + w["nivel"] * nivel + fijo
    potencial = w["cobertura"] + w["nivel"] * max(nivel, 0.9) + fijo

    orden = {"key": lambda x: -x["peso"]}
    return Match(
        pct=_porcentaje(puntaje), pct_potencial=_porcentaje(min(potencial, 1.0)),
        cobertura=cobertura, nivel=nivel, centralidad=centralidad, adyacencia=adyacencia,
        cubiertas=sorted(cubiertas, **orden), faltantes=sorted(faltantes, **orden),
        version=settings.MATCHING_VERSION)


# ---- De dónde salen los datos: el grafo o, si no responde, SQLite -------------

def _datos_del_grafo(perfiles_, vacantes):
    """{(usuario_id, vacante_id): (niveles, requisitos, centralidad)} leído de Neo4j.

    Solo incluye los pares cuyo candidato y vacante existen en el grafo.
    """
    usuarios = [p.usuario_id for p in perfiles_]
    presentes = servicio_grafo.candidatos_presentes(usuarios)
    filas = servicio_grafo.recorrido_de_match(presentes, [v.pk for v in vacantes])
    datos = {}
    for f in filas:
        niveles, requisitos, _ = datos.setdefault(
            (f["usuario_id"], f["vacante_id"]), ({}, [], f["centralidad"]))
        requisitos.append({"nombre": f["habilidad"], "peso": f["peso"],
                           "nivel_min": f["nivel_min"], "obligatoria": f["obligatoria"]})
        if f["nivel"] is not None:
            niveles[f["habilidad"]] = f["nivel"]
    return datos


def _datos_de_sqlite(perfil, vacante):
    requisitos = [{"nombre": r.habilidad.nombre, "peso": float(r.peso),
                   "nivel_min": r.nivel_minimo, "obligatoria": r.obligatoria}
                  for r in vacante.requisitos.all()]
    return perfiles.niveles_de(perfil), requisitos, vacante.centralidad


def calcular_lote(perfiles_, vacantes):
    """Calcula el match de cada candidato con cada vacante.

    Devuelve ({(perfil.pk, vacante.pk): Match}, aviso). El aviso viene vacío cuando
    todo salió del grafo; si Neo4j no responde, o le falta algún nodo, esos pares
    se calculan con los datos de SQLite y se informa.
    """
    perfiles_, vacantes = list(perfiles_), list(vacantes)
    try:
        del_grafo = _datos_del_grafo(perfiles_, vacantes) if perfiles_ and vacantes else {}
    except GrafoNoDisponible:
        del_grafo = {}

    resultados, con_respaldo = {}, 0
    for perfil in perfiles_:
        por_aprender = set(perfil.por_aprender.values_list("nombre", flat=True))
        for vacante in vacantes:
            datos = del_grafo.get((perfil.usuario_id, vacante.pk))
            if datos is None:
                datos = _datos_de_sqlite(perfil, vacante)
                con_respaldo += 1
            resultados[(perfil.pk, vacante.pk)] = calcular_match(datos[0], por_aprender,
                                                                 datos[1], datos[2])
    if con_respaldo:
        logger.warning("Matching calculado con el respaldo en SQLite para %d de %d pares",
                       con_respaldo, len(resultados))
    return resultados, AVISO_RESPALDO if con_respaldo else ""


def match_de(perfil, vacante):
    """Match de un candidato con una vacante. Devuelve (Match, aviso)."""
    resultados, aviso = calcular_lote([perfil], [vacante])
    return resultados[(perfil.pk, vacante.pk)], aviso


# ---- Recomendaciones (HU-RF-005) ----------------------------------------------

def vacantes_publicadas():
    return (Vacante.objects.filter(estado=Vacante.Estado.PUBLICADA)
            .select_related("area").prefetch_related("requisitos__habilidad"))


def recomendar(perfil, orden=ORDEN_RELEVANCIA, todas=False):
    """Vacantes recomendadas para el candidato, cada una con su match explicable.

    Por defecto solo las que coinciden con el perfil (cubre al menos una habilidad
    requerida) y con sus preferencias laborales. Con `todas=True` no se filtra.
    Devuelve {items: [{vacante, match}], aviso, total, ocultas}.
    """
    publicadas = vacantes_publicadas()
    total = publicadas.count()
    candidatas = publicadas if todas else filtrar_por_preferencias(
        publicadas, perfiles.preferencias_de(perfil))
    resultados, aviso = calcular_lote([perfil], candidatas)

    items = [{"vacante": v, "match": resultados[(perfil.pk, v.pk)]} for v in candidatas]
    if not todas:
        items = [i for i in items if i["match"].cubiertas]
    if orden == ORDEN_FECHA:
        items.sort(key=lambda i: i["vacante"].publicada_en, reverse=True)
    else:
        items.sort(key=lambda i: (-i["match"].pct, i["vacante"].titulo))
    return {"items": items, "aviso": aviso, "total": total, "ocultas": total - len(items)}
