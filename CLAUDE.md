# SkillGraph AI — reglas del proyecto

Proyecto de Ingeniería de Software (EAFIT) para el reto "matching explicable con Neo4j" de Magneto 365.
Estas reglas vienen del profesor, del cliente y del documento de arquitectura. No se negocian ni se
cambian sin preguntar al equipo.

## Intocable

- No modificar nada dentro de `prototipo/`. Es evidencia de la Entrega 1 y `node prototipo/test_flujo.js`
  debe seguir pasando (46 condiciones).
- `GraphCore` se movió desde `poc/` sin cambiar su comportamiento. No alterar `Neo4jConnection`,
  `init_graph` ni `check_graph` salvo que se pida.

## Stack obligatorio

- Python 3.12, Django 5.0, SQLite3 a través del ORM de Django.
- Neo4j 5.x con el driver oficial, siempre mediante `GraphCore.Neo4jConnection`.
- Django REST Framework 3.15 para los servicios JSON que necesite la interfaz.
- pytest, pytest-django, coverage y flake8 para calidad.
- Gunicorn y WhiteNoise para despliegue.
- Interfaz con plantillas de Django y HTML, CSS y JavaScript sin frameworks, reutilizando el diseño
  de `prototipo/index.html` (colores, tipografías, componentes, textos).
- Dependencias adicionales permitidas: `pdfplumber`, `python-docx` y la librería de hashing
  (`argon2-cffi` o `bcrypt`). Cualquier otra dependencia se pregunta primero.

## Arquitectura

- Cliente/servidor en tres niveles: presentación (plantillas), lógica (aplicaciones Django y servicios)
  y datos (SQLite y Neo4j).
- Capas dentro del servidor: vistas → servicios de negocio → acceso a datos.
  Nada de lógica de negocio en las vistas ni en las plantillas.
- Las consultas Cypher solo viven en `GraphCore` o en un servicio de grafo. Nunca en las vistas.
- Una aplicación de Django por dominio: `cuentas`, `perfiles`, `vacantes`, `matching`, `postulaciones`,
  además de `GraphCore`.
- Orientado a objetos: los conceptos del dominio son modelos de Django.
- Estructura: `manage.py` y la carpeta de configuración `skillgraph/` en la raíz; las aplicaciones en la raíz.
- `skillgraph/settings.py` lee `.env` con python-dotenv, construye `NEO4J_CONFIG` y lee los pesos del
  matching: `MATCHING_VERSION`, `W_COBERTURA`, `W_NIVEL`, `W_CENTRALIDAD`, `W_ADYACENCIA`.
- El cálculo del match vive en un único servicio de la aplicación `matching`, reutilizado por las
  recomendaciones (HU-RF-005) y por las postulaciones priorizadas (HU-RF-013).

### Modelo en el grafo

Se sincroniza cuando un candidato confirma su perfil o un reclutador publica una vacante:

```
(:Candidato)-[:TIENE {nivel}]->(:Skill)
(:Vacante)-[:REQUIERE {peso, nivel_min, obligatoria}]->(:Skill)
```

Respetar las restricciones que crea `init_graph` (`Skill.nombre`, `Candidato.usuario_id`,
`Vacante.vacante_id`, `Rol.nombre` únicos).

### Neo4j caído

Si Neo4j no está disponible el sistema no se puede caer. El servicio de matching tiene una implementación
de respaldo en Python sobre los datos de SQLite, muestra un aviso discreto en la interfaz y lo registra
en el log.

## Reglas de interfaz

- En todos los formularios, cuando hay campos obligatorios vacíos o inválidos:
  - se muestra exactamente este mensaje: `Favor ingresar información válida en los campos obligatorios`
  - se resaltan los campos inválidos;
  - el foco va al primer campo inválido.
- Toda la interfaz va en español.
- Inclusividad: el sistema sirve igual para oficios no técnicos (bodega, alimentos, belleza, seguridad,
  construcción, comercio) que para cargos técnicos. Usar el catálogo de 16 áreas del prototipo y nunca
  asumir que el usuario es del sector tecnológico.

## Forma de trabajar

- Una rama por historia (`feature/HU-RF-003`), commits pequeños con la clave de Jira (`SA-12: ...`).
  No hacer push: el equipo revisa y sube.
- Cambios incrementales. Nunca reemplazar un archivo completo cuando basta con editar una parte
  (ya hubo una regresión por reemplazar bloques enteros).
- Pruebas con pytest-django por cada criterio de aceptación, nombradas con la historia que validan
  (`test_rf003_rechaza_archivo_mayor_a_5mb`).
- Al cierre de cada fase deben pasar `pytest`, `flake8` y `node prototipo/test_flujo.js`.
- Si algo es ambiguo, preguntar antes de inventarlo.
