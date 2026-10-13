"""HU-RF-003 · Extracción de información de la hoja de vida (SA-12)."""
import json
from pathlib import Path

import pytest
from django.conf import settings

from perfiles.extraccion import diccionario, extractor, lectores

CV = Path(settings.BASE_DIR) / "docs" / "cv_ejemplo"

# archivo → lo que debe extraerse
ESPERADO = {
    "cv_plano.pdf": {            # formato plano, campos rotulados · bodega y temporada
        "nombre": "Camilo Zapata Ospina", "correo": "camilo.zapata@correo.com",
        "telefono": "3109876543", "experiencia": "Auxiliar de cargue",
        "educacion": "Bachiller académico",
        "habilidades": {"Alistamiento de pedidos", "Atención al cliente", "Carga y descarga",
                        "Puntualidad", "Trabajo en equipo"}},
    "cv_harvard.docx": {         # tipo Harvard en Word · tecnología
        "nombre": "Ana María Ríos Bedoya", "correo": "ana.rios@correo.com",
        "telefono": "3001234567", "experiencia": "Desarrolladora backend",
        "educacion": "Universidad EAFIT",
        "habilidades": {"Python", "Django", "SQL", "Docker", "Git", "Scrum", "Linux"}},
    "cv_dos_columnas.pdf": {     # a dos columnas · belleza
        "nombre": "Valentina Restrepo Mejía", "correo": "valentina.restrepo@correo.com",
        "telefono": "3205557788", "experiencia": "Studio Bruna",
        "educacion": "Técnica en peluquería",
        "habilidades": {"Corte de cabello", "Colorimetría", "Manicure y pedicure",
                        "Maquillaje", "Atención al cliente"}},
    "cv_diseno.pdf": {           # con diseño y barra lateral · seguridad
        "nombre": "Jorge Iván Castaño Ruiz", "correo": "jorge.castano@correo.com",
        "telefono": "3014449080", "experiencia": "Vigilancia Antioquia",
        "educacion": "Bachiller académico",
        "habilidades": {"Curso de vigilancia", "Control de acceso", "Manejo de CCTV",
                        "Reporte de novedades", "Primeros auxilios", "Puntualidad"}},
    "cv_tabla.docx": {           # diseño en tabla de Word, rótulos en inglés · alimentos
        "nombre": "Luz Dary Mosquera Palacios", "correo": "luzdary.mosquera@correo.com",
        "telefono": "3142226677", "experiencia": "Restaurante La Provincia",
        "educacion": "Técnico en cocina",
        "habilidades": {"Manipulación de alimentos", "Cocina caliente",
                        "Panadería y repostería", "Trabajo en equipo"}},
}


def extraer_de(nombre, catalogo):
    lectura = lectores.leer(CV / nombre, nombre.rsplit(".", 1)[-1])
    return extractor.extraer(lectura.texto, list(catalogo), lectura.titular_probable)


def test_rf003_hay_al_menos_cuatro_hojas_de_vida_de_prueba():
    for nombre in ("cv_plano.pdf", "cv_harvard.docx", "cv_dos_columnas.pdf", "cv_diseno.pdf"):
        assert (CV / nombre).is_file(), nombre
    assert len(ESPERADO) >= 4
    assert {n.rsplit(".", 1)[-1] for n in ESPERADO} == {"pdf", "docx"}


@pytest.mark.parametrize("archivo", ESPERADO)
def test_rf003_extrae_nombre_correo_y_telefono(archivo, catalogo):
    datos = extraer_de(archivo, catalogo)
    esperado = ESPERADO[archivo]
    assert datos.nombre == esperado["nombre"]
    assert datos.correo == esperado["correo"]
    assert datos.telefono == esperado["telefono"]


@pytest.mark.parametrize("archivo", ESPERADO)
def test_rf003_extrae_experiencia_y_educacion(archivo, catalogo):
    datos = extraer_de(archivo, catalogo)
    esperado = ESPERADO[archivo]
    assert esperado["experiencia"] in datos.experiencia
    assert esperado["educacion"] in datos.educacion
    # Cada sección trae lo suyo: no se mezclan los bloques (ni siquiera a dos columnas).
    assert esperado["educacion"] not in datos.experiencia
    assert esperado["experiencia"] not in datos.educacion


@pytest.mark.parametrize("archivo", ESPERADO)
def test_rf003_extrae_las_habilidades(archivo, catalogo):
    datos = extraer_de(archivo, catalogo)
    assert ESPERADO[archivo]["habilidades"] <= set(datos.habilidades)
    assert datos.faltantes == []
    assert datos.suficiente


@pytest.mark.parametrize("archivo", ESPERADO)
def test_rf003_cada_habilidad_extraida_es_un_nodo_skill_del_catalogo(archivo, catalogo):
    datos = extraer_de(archivo, catalogo)
    assert set(datos.habilidades) <= set(catalogo)
    assert all(1 <= nivel <= 5 for nivel in datos.habilidades.values())


def test_rf003_lee_el_pdf_a_dos_columnas_columna_por_columna():
    lineas = lectores.leer(CV / "cv_dos_columnas.pdf", "pdf").texto.splitlines()
    assert lineas[0] == "VALENTINA RESTREPO MEJÍA"
    # La columna izquierda completa va antes que la derecha.
    assert lineas.index("APTITUDES") < lineas.index("IDIOMAS") < lineas.index("SOBRE MÍ")
    assert "Atención al cliente" in lineas          # y no «Atención al cliente FORMACIÓN…»


def test_rf003_toma_el_nivel_cuando_la_hoja_de_vida_lo_dice(catalogo):
    datos = extraer_de("cv_dos_columnas.pdf", catalogo)
    assert datos.habilidades["Corte de cabello"] == 5       # «(experto)»
    assert datos.habilidades["Colorimetría"] == 4           # «(avanzado)»
    assert datos.habilidades["Maquillaje"] == extractor.NIVEL_POR_DEFECTO


def test_rf003_hoja_de_vida_escaneada_no_trae_informacion_suficiente(catalogo):
    datos = extraer_de("cv_escaneado.pdf", catalogo)
    assert not datos.suficiente
    assert datos.faltantes == list(extractor.CAMPOS)


def test_rf003_archivo_danado_se_informa_como_ilegible(tmp_path):
    roto = tmp_path / "roto.pdf"
    roto.write_bytes(b"%PDF-1.4 esto no es un pdf de verdad")
    with pytest.raises(lectores.ArchivoIlegible):
        lectores.leer(roto, "pdf")


# ---- Diccionario de palabras clave y sinónimos --------------------------------

@pytest.mark.parametrize("rotulo", ["Nombre", "name", "NOMBRE COMPLETO", "Nombres y apellidos"])
def test_rf003_reconoce_el_nombre_por_sus_sinonimos(rotulo, catalogo):
    texto = f"Datos personales\n{rotulo}: Rosa Elvira Cuesta\nCel: 3001112233"
    assert extractor.extraer(texto, list(catalogo)).nombre == "Rosa Elvira Cuesta"


@pytest.mark.parametrize("titulo, campo", [
    ("Historia laboral", "experiencia"), ("WORK EXPERIENCE", "experiencia"),
    ("Trayectoria:", "experiencia"), ("Formación académica", "educacion"),
    ("Estudios realizados", "educacion"), ("Education", "educacion"),
])
def test_rf003_reconoce_las_secciones_por_sus_sinonimos(titulo, campo, catalogo):
    texto = f"Pedro Pérez Gómez\n{titulo}\nDato de prueba 2020\nReferencias\nOtra cosa"
    datos = extractor.extraer(texto, list(catalogo))
    assert getattr(datos, campo) == "Dato de prueba 2020"


@pytest.mark.parametrize("escrito, habilidad", [
    ("servicio al cliente", "Atención al cliente"),
    ("cargue y descargue", "Carga y descarga"),
    ("Monitoreo de cámaras", "Manejo de CCTV"),
    ("MANICURISTA", "Manicure y pedicure"),
    ("curso de alturas", "Trabajo en alturas"),
    ("cajera", "Manejo de caja"),
])
def test_rf003_reconoce_habilidades_por_sus_sinonimos(escrito, habilidad, catalogo):
    datos = extractor.extraer(f"Experiencia\nTrabajé en {escrito} dos años.", list(catalogo))
    assert habilidad in datos.habilidades


def test_rf003_no_confunde_palabras_parecidas(catalogo):
    texto = "Habilidades\nJavaScript, redes sociales, excelente actitud, GitHub"
    halladas = set(extractor.extraer(texto, list(catalogo)).habilidades)
    assert {"JavaScript", "Redes sociales", "Git"} <= halladas
    assert not {"Java", "Redes", "Excel"} & halladas


def test_rf003_el_diccionario_es_un_archivo_de_datos_editable():
    assert diccionario.RUTA.suffix == ".json"
    crudo = json.loads(diccionario.RUTA.read_text(encoding="utf-8"))
    assert {"nombre", "name", "nombre completo"} <= set(crudo["campos"]["nombre"])
    assert set(crudo) >= {"campos", "secciones", "niveles", "habilidades"}


def test_rf003_editar_el_diccionario_cambia_lo_que_se_reconoce(tmp_path, monkeypatch, catalogo):
    texto = "Experiencia\nFui bodeguero tres años."
    assert "Manejo de inventarios" not in extractor.extraer(texto, list(catalogo)).habilidades

    editado = json.loads(diccionario.RUTA.read_text(encoding="utf-8"))
    editado["habilidades"]["Manejo de inventarios"].append("bodeguero")
    copia = tmp_path / "diccionario_cv.json"
    copia.write_text(json.dumps(editado, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(diccionario, "RUTA", copia)

    assert "Manejo de inventarios" in extractor.extraer(texto, list(catalogo)).habilidades


def test_rf003_los_sinonimos_solo_apuntan_a_habilidades_del_catalogo(catalogo):
    crudo = json.loads(diccionario.RUTA.read_text(encoding="utf-8"))
    assert set(crudo["habilidades"]) <= set(catalogo)
    alias = diccionario.alias_de_habilidades(["Python"])
    assert set(alias.values()) == {"Python"}        # lo que no está en el catálogo se descarta
