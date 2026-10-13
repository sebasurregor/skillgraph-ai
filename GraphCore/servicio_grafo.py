"""Servicio de grafo: único lugar, junto a GraphCore, donde vive Cypher.

Modelo:
    (:Candidato {usuario_id})-[:TIENE {nivel}]->(:Skill {nombre})
    (:Vacante {vacante_id})-[:REQUIERE {peso, nivel_min, obligatoria}]->(:Skill {nombre})

Recibe y devuelve datos planos (diccionarios), nunca modelos de Django.
Si Neo4j no responde, las escrituras devuelven False y las lecturas lanzan
`GrafoNoDisponible`, para que quien llama use su respaldo sobre SQLite.
"""
import logging
import time

from neo4j.exceptions import DriverError, Neo4jError

from GraphCore.neo4j_driver import Neo4jConnection

logger = logging.getLogger(__name__)

# Tras comprobar la conexión no se vuelve a comprobar durante este lapso, para
# no esperar al servidor en cada operación.
VIGENCIA_COMPROBACION = 30

_estado = {"disponible": None, "hasta": 0.0}


class GrafoNoDisponible(Exception):
    """Neo4j no respondió; hay que usar el respaldo."""


def reiniciar_estado():
    _estado.update(disponible=None, hasta=0.0)


def _marcar(disponible, motivo=""):
    if not disponible and _estado["disponible"] is not False:
        logger.warning("Neo4j no disponible; se usa el respaldo en SQLite. %s", motivo)
    _estado.update(disponible=disponible, hasta=time.monotonic() + VIGENCIA_COMPROBACION)


def disponible():
    """Indica si Neo4j responde. El resultado se recuerda unos segundos."""
    if _estado["disponible"] is not None and time.monotonic() < _estado["hasta"]:
        return _estado["disponible"]
    try:
        ok, mensaje = Neo4jConnection.verify()
    except (DriverError, Neo4jError, OSError, ValueError) as exc:
        ok, mensaje = False, str(exc)
    _marcar(ok, mensaje)
    return ok


def _ejecutar(operacion, cypher, **params):
    if not disponible():
        raise GrafoNoDisponible
    try:
        return operacion(cypher, **params)
    except (DriverError, Neo4jError, OSError) as exc:
        _marcar(False, str(exc))
        raise GrafoNoDisponible from exc


def _escribir(cypher, **params):
    """Escritura tolerante a fallos: devuelve True si quedó en el grafo."""
    try:
        _ejecutar(Neo4jConnection.write, cypher, **params)
        return True
    except GrafoNoDisponible:
        return False


# ---- Habilidades -----------------------------------------------------------

def sincronizar_habilidades(habilidades):
    """`habilidades`: lista de {nombre, categoria}."""
    return _escribir(
        """
        UNWIND $habilidades AS h
        MERGE (s:Skill {nombre: h.nombre})
          SET s.categoria = h.categoria
        """,
        habilidades=list(habilidades),
    )


# ---- Vacantes --------------------------------------------------------------

def sincronizar_vacante(vacante_id, datos, requisitos):
    """Deja la vacante publicada y sus aristas :REQUIERE tal como están en SQLite.

    `datos`: {titulo, empresa, ciudad, estado, centralidad}.
    `requisitos`: lista de {nombre, peso, nivel_min, obligatoria}.
    """
    return _escribir(
        """
        MERGE (v:Vacante {vacante_id: $vacante_id})
          SET v += $datos
        WITH v
        OPTIONAL MATCH (v)-[anterior:REQUIERE]->(:Skill)
        DELETE anterior
        WITH DISTINCT v
        UNWIND $requisitos AS q
        MERGE (s:Skill {nombre: q.nombre})
        MERGE (v)-[r:REQUIERE]->(s)
          SET r.peso = q.peso, r.nivel_min = q.nivel_min, r.obligatoria = q.obligatoria
        """,
        vacante_id=vacante_id, datos=dict(datos), requisitos=list(requisitos),
    )


def retirar_vacante(vacante_id):
    """Quita del grafo una vacante despublicada o eliminada."""
    return _escribir(
        "MATCH (v:Vacante {vacante_id: $vacante_id}) DETACH DELETE v",
        vacante_id=vacante_id,
    )


# ---- Candidatos ------------------------------------------------------------

def sincronizar_candidato(usuario_id, datos, habilidades):
    """Deja al candidato y sus aristas :TIENE tal como están en SQLite.

    `datos`: {titular, ciudad}. `habilidades`: lista de {nombre, nivel}.
    """
    return _escribir(
        """
        MERGE (c:Candidato {usuario_id: $usuario_id})
          SET c += $datos
        WITH c
        OPTIONAL MATCH (c)-[anterior:TIENE]->(:Skill)
        DELETE anterior
        WITH DISTINCT c
        UNWIND $habilidades AS h
        MERGE (s:Skill {nombre: h.nombre})
        MERGE (c)-[t:TIENE]->(s)
          SET t.nivel = h.nivel
        """,
        usuario_id=usuario_id, datos=dict(datos), habilidades=list(habilidades),
    )


def retirar_candidato(usuario_id):
    return _escribir(
        "MATCH (c:Candidato {usuario_id: $usuario_id}) DETACH DELETE c",
        usuario_id=usuario_id,
    )


def contar_candidatos():
    filas = _ejecutar(Neo4jConnection.read, "MATCH (c:Candidato) RETURN count(c) AS total")
    return filas[0]["total"] if filas else 0


def contar_candidatos_que_cubren(exigidas, minimo):
    """Candidatos que tienen al menos `minimo` de las habilidades exigidas con su nivel.

    `exigidas`: lista de {nombre, nivel_min}. Lanza `GrafoNoDisponible`.
    """
    filas = _ejecutar(
        Neo4jConnection.read,
        """
        UNWIND $exigidas AS q
        MATCH (c:Candidato)-[t:TIENE]->(:Skill {nombre: q.nombre})
        WHERE t.nivel >= q.nivel_min
        WITH c, count(DISTINCT q.nombre) AS cubiertas
        WHERE cubiertas >= $minimo
        RETURN count(c) AS total
        """,
        exigidas=list(exigidas), minimo=minimo,
    )
    return filas[0]["total"] if filas else 0


# ---- Matching --------------------------------------------------------------

def candidatos_presentes(usuario_ids):
    """Subconjunto de candidatos que ya existen como nodo. Lanza `GrafoNoDisponible`."""
    filas = _ejecutar(
        Neo4jConnection.read,
        "MATCH (c:Candidato) WHERE c.usuario_id IN $candidatos "
        "RETURN collect(c.usuario_id) AS presentes",
        candidatos=list(usuario_ids),
    )
    return set(filas[0]["presentes"]) if filas else set()


def recorrido_de_match(usuario_ids, vacante_ids):
    """Recorre Vacante → REQUIERE → Skill ← TIENE ← Candidato.

    Devuelve una fila por candidato y habilidad requerida:
    {usuario_id, vacante_id, centralidad, habilidad, peso, nivel_min, obligatoria, nivel};
    `nivel` es None cuando el candidato no tiene la habilidad. Lanza `GrafoNoDisponible`.
    """
    return _ejecutar(
        Neo4jConnection.read,
        """
        MATCH (v:Vacante)-[r:REQUIERE]->(s:Skill)
        WHERE v.vacante_id IN $vacantes
        UNWIND $candidatos AS usuario_id
        OPTIONAL MATCH (c:Candidato {usuario_id: usuario_id})-[t:TIENE]->(s)
        RETURN usuario_id, v.vacante_id AS vacante_id, v.centralidad AS centralidad,
               s.nombre AS habilidad, r.peso AS peso, r.nivel_min AS nivel_min,
               r.obligatoria AS obligatoria, t.nivel AS nivel
        """,
        candidatos=list(usuario_ids), vacantes=list(vacante_ids),
    )
