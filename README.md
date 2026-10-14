# SkillGraph AI — Matching explicable de vacantes y competencias

Proyecto final de Sistemas de Información · Periodo 2026-2

Plataforma de recomendación de empleo **para cualquier sector del mercado laboral**: calcula el
ajuste entre una persona y una vacante recorriendo un grafo de habilidades en Neo4j, y devuelve
la evidencia completa que sustenta el resultado —qué habilidades cubre, cuáles le faltan, cuánto
pesa cada una y cuánto subiría el ajuste al cerrar la brecha principal.

Cubre dieciséis áreas ocupacionales, desde un contrato de temporada en bodega hasta un cargo de
ingeniería de datos.

## Qué hay en el repositorio

| Carpeta / archivo | Descripción |
|---|---|
| `manage.py`, `skillgraph/` | Proyecto Django: configuración, rutas y regla común de formularios |
| `cuentas/` | Registro, inicio de sesión, roles y cifrado de contraseñas (HU-RNF-001) |
| `vacantes/` | Catálogo de habilidades y vacantes con habilidades ponderadas (HU-RF-011) |
| `perfiles/` | Hoja de vida, extracción, perfil y preferencias (HU-RF-003, HU-RF-004) |
| `matching/` | Servicio único de matching, recomendaciones y explicación (HU-RF-005) |
| `postulaciones/` | Postular y postulaciones priorizadas (HU-RF-006, HU-RF-013) |
| `GraphCore/` | Conexión con Neo4j y servicio de grafo: el único lugar con consultas Cypher |
| `templates/`, `static/` | Plantillas base, estilos del prototipo y JavaScript sin frameworks |
| `docs/` | Arquitectura, diagramas PlantUML, estado del sprint y hojas de vida de ejemplo |
| `prototipo/` | Prototipo navegable de la Entrega 1. No se modifica |

Documentación del Sprint 2: [`docs/estado_sprint2.md`](docs/estado_sprint2.md),
[`docs/arquitectura.md`](docs/arquitectura.md), [`docs/diagramas/`](docs/diagramas/),
[`docs/capturas_sugeridas.md`](docs/capturas_sugeridas.md) y
[`docs/arbol_directorios.txt`](docs/arbol_directorios.txt).

## Stack

Python 3.12 · Django 5.0 · SQLite3 · Neo4j 5.x (Bolt) · Django REST Framework 3.15 ·
HTML, CSS y JavaScript sin frameworks · pytest · flake8 · Gunicorn y WhiteNoise

## Instalación en Windows

Requisitos: Python 3.12, Git y Neo4j 5.x. Node.js solo hace falta para la prueba del prototipo.

```bat
cd "C:\ruta\al\repo"
py -3.12 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

> **Active el entorno virtual cada vez que abra una terminal** (`venv\Scripts\activate`). La línea
> de comandos debe empezar con `(venv)`. Sin eso, `python manage.py ...` falla con
> `No module named 'django'`.

### Archivo `.env`

```bat
copy .env.example .env
```

Edite `.env` si su Neo4j usa otras credenciales. Valores por defecto:

| Variable | Valor | Para qué |
|---|---|---|
| `DJANGO_DEBUG` | `True` | En `False` se exige HTTPS, cookies seguras y HSTS |
| `DJANGO_SECRET_KEY` | (cámbiela en producción) | Firma de sesiones |
| `NEO4J_URI` | `bolt://localhost:7687` | Conexión Bolt |
| `NEO4J_USER` / `NEO4J_PASSWORD` | `neo4j` / `skillgraph2026` | Credenciales del grafo |
| `NEO4J_DATABASE` | `neo4j` | Base de datos del grafo |
| `MATCHING_VERSION` | `1.0.0` | Versión del algoritmo que se muestra en la explicación |
| `W_COBERTURA`, `W_NIVEL`, `W_CENTRALIDAD`, `W_ADYACENCIA` | `0.60`, `0.25`, `0.10`, `0.05` | Pesos de la fórmula del match |

### Levantar Neo4j

**Neo4j Desktop.** Cree una instancia con la versión 5.x, usuario `neo4j` y contraseña
`skillgraph2026`, y pulse **Start**. Desktop muestra la URI `neo4j://127.0.0.1:7687`; el proyecto
usa `bolt://localhost:7687`, que apunta al mismo servidor. Tener Desktop abierto no basta: la
instancia debe estar iniciada.

**Docker** (alternativa; este comando no se probó en el equipo de desarrollo):

```bat
docker run -d --name skillgraph-neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/skillgraph2026 neo4j:5.26
```

Si Neo4j no está disponible la aplicación sigue funcionando: calcula el matching con los datos de
SQLite, muestra un aviso discreto y lo deja en `skillgraph.log`.

### Base de datos, grafo y datos de demostración

```bat
python manage.py migrate
python manage.py check_graph
python manage.py init_graph
python manage.py cargar_datos_demo
```

| Comando | Qué hace |
|---|---|
| `migrate` | Crea las tablas de SQLite |
| `check_graph` | Verifica la conexión con Neo4j (escribe, lee y borra un nodo de prueba) |
| `init_graph` | Crea las restricciones de unicidad y los índices del grafo |
| `cargar_datos_demo` | Carga el catálogo de 16 áreas (118 habilidades), 16 vacantes publicadas, un reclutador y dos candidatos, en SQLite y en Neo4j. Se puede ejecutar varias veces |
| `sincronizar_grafo` | Reconstruye Neo4j desde SQLite. Úselo si el grafo estuvo caído mientras se publicaban vacantes o se confirmaban perfiles |

### Ejecutar el servidor

```bat
python manage.py runserver
```

Abra http://127.0.0.1:8000/. Para detener el servidor use `Ctrl + C` (Django sugiere
`Ctrl + Break`, pero `Ctrl + C` funciona igual en Windows).

## Credenciales de demostración

Todas usan la contraseña `skillgraph2026`.

| Rol | Correo | Perfil |
|---|---|---|
| Candidata | `ana.rios@correo.com` | Ana María Ríos: perfil tecnológico. Su mejor vacante da 82 % |
| Candidato | `camilo.zapata@correo.com` | Camilo Zapata: perfil de temporada, sin experiencia. Su mejor vacante da 53 % |
| Reclutador | `reclutador@skillgraph.co` | Dueño de las 16 vacantes de demostración |

Para restablecer la contraseña de cualquier cuenta: `python manage.py changepassword correo@ejemplo.com`.

## Recorrido sugerido

1. Cree una cuenta nueva de candidato. Lo primero que se le ofrece es subir la hoja de vida.
2. Suba un archivo de `docs/cv_ejemplo/` (por ejemplo `cv_dos_columnas.pdf`), revise el formulario
   precargado y confirme.
3. Indique sus preferencias laborales.
4. En las vacantes recomendadas abra **Ver por qué** y pulse **Postularme**.
5. Entre con el reclutador, abra **Mis vacantes** → **Ver postulaciones** en esa vacante.
6. Cree, edite, despublique y elimine una vacante desde **Mis vacantes**.

## Pruebas y calidad

```bat
pytest
flake8
coverage run -m pytest
coverage report
```

Cada prueba lleva en su nombre la historia que valida (`test_rf003_rechaza_archivo_mayor_a_5mb`).
Usan un Neo4j simulado y no tocan su instancia.

Cuatro pruebas son de integración con el Neo4j real y vienen desactivadas. Para ejecutarlas:

```bat
set SKILLGRAPH_PRUEBAS_NEO4J=1
pytest matching/tests/test_integracion_neo4j.py
```

### Prototipo de la Entrega 1

Abra `prototipo/index.html` en cualquier navegador.

- Cuenta de prueba: `ana.rios@correo.com` · contraseña `skillgraph2026`
- Cualquier otro correo lleva a la pantalla de creación de cuenta
- `Alt + D` carga un perfil de tecnología · `Alt + N` carga un perfil de temporada navideña

```bat
npm install --no-save jsdom
node prototipo/test_flujo.js
```

Recorre el flujo completo y verifica 46 condiciones.

## Despliegue

En producción (`DJANGO_DEBUG=False`) la aplicación se sirve con Gunicorn y WhiteNoise detrás de un
proxy que termina TLS 1.2 o superior. Gunicorn no corre en Windows: para desarrollo local use
`runserver`. El proyecto no se ha desplegado todavía en un servidor; estos son los comandos
previstos:

```bash
python manage.py collectstatic --noinput
gunicorn skillgraph.wsgi:application
```

Detalle en [`docs/arquitectura.md`](docs/arquitectura.md) y
[`docs/diagramas/despliegue.puml`](docs/diagramas/despliegue.puml).
