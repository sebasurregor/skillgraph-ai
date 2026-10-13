"""Convierte un PDF o un Word en texto plano, respetando el orden de lectura.

Los PDF a dos columnas o con barra lateral se leen columna por columna; si se
leyeran renglón por renglón, las secciones de ambas columnas quedarían mezcladas.
"""
from dataclasses import dataclass
from statistics import median

import pdfplumber
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

TOLERANCIA_RENGLON = 3      # puntos: palabras a esta distancia vertical son un mismo renglón
ANCHO_MIN_CANAL = 12        # puntos: separación mínima entre dos columnas
MAX_CRUCES = 2              # renglones a todo el ancho que se toleran sobre el canal
MIN_PALABRAS_POR_LADO = 0.12


class ArchivoIlegible(Exception):
    """El archivo no se pudo abrir como PDF o Word."""


@dataclass
class Lectura:
    texto: str
    titular_probable: str = ""   # renglón con la letra más grande: suele ser el nombre


def leer(archivo, formato):
    """`formato`: "pdf" o "docx". Lanza `ArchivoIlegible` si el archivo está dañado."""
    try:
        return _leer_pdf(archivo) if formato == "pdf" else _leer_docx(archivo)
    except ArchivoIlegible:
        raise
    except Exception as exc:    # las librerías lanzan errores muy variados ante archivos rotos
        raise ArchivoIlegible(str(exc)) from exc


# ---- PDF ----------------------------------------------------------------------

def _leer_pdf(archivo):
    renglones = []      # (texto, tamaño de letra)
    with pdfplumber.open(archivo) as pdf:
        for pagina in pdf.pages:
            renglones.extend(_renglones_de_pagina(pagina))
    texto = "\n".join(t for t, _ in renglones)
    return Lectura(texto=texto, titular_probable=_titular(renglones))


def _renglones_de_pagina(pagina):
    palabras = pagina.extract_words(extra_attrs=["size"], x_tolerance=2, y_tolerance=3)
    if not palabras:
        return []
    lineas = _agrupar_en_lineas(palabras)
    canal = _buscar_canal(palabras, pagina.width)
    if canal is None:
        return [_renglon(linea) for linea in lineas]

    salida, izquierda, derecha = [], [], []
    for linea in lineas:
        parte_izq = [p for p in linea if p["x1"] <= canal]
        parte_der = [p for p in linea if p["x0"] >= canal]
        if len(parte_izq) + len(parte_der) < len(linea) or _pegadas(parte_izq, parte_der):
            # Renglón a todo el ancho (un título, por ejemplo): cierra el bloque anterior.
            salida += izquierda + derecha + [_renglon(linea)]
            izquierda, derecha = [], []
            continue
        if parte_izq:
            izquierda.append(_renglon(parte_izq))
        if parte_der:
            derecha.append(_renglon(parte_der))
    return salida + izquierda + derecha


def _agrupar_en_lineas(palabras):
    lineas = []
    for palabra in sorted(palabras, key=lambda p: (p["top"], p["x0"])):
        if lineas and abs(palabra["top"] - lineas[-1][0]["top"]) <= TOLERANCIA_RENGLON:
            lineas[-1].append(palabra)
        else:
            lineas.append([palabra])
    return [sorted(linea, key=lambda p: p["x0"]) for linea in lineas]


def _buscar_canal(palabras, ancho):
    """Devuelve la x del espacio en blanco vertical que separa dos columnas, o None."""
    mejor, inicio = None, None
    for x in range(int(ancho * 0.2), int(ancho * 0.8) + 2, 2):
        cruces = sum(1 for p in palabras if p["x0"] < x < p["x1"])
        if cruces <= MAX_CRUCES:
            inicio = x if inicio is None else inicio
            continue
        mejor = _mas_ancho(mejor, inicio, x)
        inicio = None
    mejor = _mas_ancho(mejor, inicio, int(ancho * 0.8))
    if mejor is None or mejor[1] - mejor[0] < ANCHO_MIN_CANAL:
        return None
    canal = (mejor[0] + mejor[1]) / 2
    minimo = len(palabras) * MIN_PALABRAS_POR_LADO
    a_la_izquierda = sum(1 for p in palabras if p["x1"] <= canal)
    a_la_derecha = sum(1 for p in palabras if p["x0"] >= canal)
    return canal if a_la_izquierda >= minimo and a_la_derecha >= minimo else None


def _mas_ancho(mejor, inicio, fin):
    if inicio is None:
        return mejor
    if mejor is None or fin - inicio > mejor[1] - mejor[0]:
        return (inicio, fin)
    return mejor


def _pegadas(parte_izq, parte_der):
    """Las dos partes son en realidad un mismo renglón corrido que pasa sobre el canal."""
    if not parte_izq or not parte_der:
        return False
    separacion = parte_der[0]["x0"] - parte_izq[-1]["x1"]
    return separacion < 0.8 * parte_izq[-1]["size"]


def _renglon(palabras):
    return " ".join(p["text"] for p in palabras), max(p["size"] for p in palabras)


def _titular(renglones):
    if not renglones:
        return ""
    texto, tamano = max(renglones, key=lambda r: r[1])
    normal = median(t for _, t in renglones)
    return texto if tamano >= normal * 1.25 else ""


# ---- Word ---------------------------------------------------------------------

def _leer_docx(archivo):
    documento = Document(archivo)
    renglones = []
    for parrafo in _parrafos(documento):
        texto = parrafo.text.strip()
        if texto:
            tamanos = [r.font.size.pt for r in parrafo.runs if r.font.size]
            renglones.append((texto, max(tamanos, default=0)))
    texto = "\n".join(t for t, _ in renglones)
    con_tamano = [r for r in renglones if r[1]]
    titular = max(con_tamano, key=lambda r: r[1])[0] if con_tamano else ""
    return Lectura(texto=texto, titular_probable=titular)


def _parrafos(contenedor):
    """Párrafos en orden de lectura, entrando a las tablas (celda por celda)."""
    cuerpo = contenedor.element.body if hasattr(contenedor, "element") else contenedor._tc
    vistas = set()
    for hijo in cuerpo.iterchildren():
        if hijo.tag.endswith("}p"):
            yield Paragraph(hijo, contenedor)
        elif hijo.tag.endswith("}tbl"):
            for fila in Table(hijo, contenedor).rows:
                for celda in fila.cells:
                    if id(celda._tc) not in vistas:      # las celdas combinadas se repiten
                        vistas.add(id(celda._tc))
                        yield from _parrafos(celda)
