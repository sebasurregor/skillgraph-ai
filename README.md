# SkillGraph AI — Matching explicable de vacantes y competencias

Proyecto final de Sistemas de Información · Periodo 2026-2

Plataforma de recomendación de empleo **para cualquier sector del mercado laboral**: calcula el
ajuste entre una persona y una vacante recorriendo un grafo de habilidades en Neo4j, y devuelve
la evidencia completa que sustenta el resultado —qué habilidades cubre, cuáles le faltan, cuánto
pesa cada una y qué ruta mínima cerraría la brecha.

Cubre dieciséis áreas ocupacionales, desde un contrato de temporada en bodega hasta un cargo de
ingeniería de datos, y el cuestionario se adapta al área que la persona elige.

## Contenido del repositorio

| Carpeta / archivo | Descripción |
|---|---|
| `SkillGraph_AI_Entrega1.md` | Documento completo de la primera entrega |
| `prototipo/index.html` | Prototipo navegable. Se abre con doble clic, sin instalar nada |
| `poc/` | Prueba de concepto: conexión Django ↔ Neo4j, esquema del grafo y dependencias |
| `media/` | Diagramas y wireframes del documento |
| `backlog_historias.csv` | Las 30 historias de usuario para importar a GitHub Projects |
| `GUIA_GIT.md` | Flujo de trabajo del equipo con Git |

## Probar el prototipo

Abra `prototipo/index.html` en cualquier navegador.

- Cuenta de prueba: `ana.rios@correo.com` · contraseña `skillgraph2026`
- Cualquier otro correo lleva a la pantalla de creación de cuenta
- `Alt + D` carga un perfil de tecnología · `Alt + N` carga un perfil de temporada navideña

## Ejecutar la prueba de concepto de Neo4j

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r poc/requirements.txt
cp poc/.env.example .env           # edite las credenciales de Neo4j
python manage.py check_graph
```

## Stack

Django 5.0 · Python 3.12 · SQLite3 · Neo4j 5.x (Bolt) · HTML/CSS/JS
