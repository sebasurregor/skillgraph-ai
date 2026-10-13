"""Datos de demostración: catálogo, vacantes, reclutador y los dos candidatos del prototipo."""
import json
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from cuentas.models import Usuario
from perfiles import services as perfiles
from vacantes import services as vacantes
from vacantes.models import AreaOcupacional, Habilidad, Vacante

CLAVE_DEMO = "skillgraph2026"

RECLUTADOR = {
    "email": "reclutador@skillgraph.co", "first_name": "Laura", "last_name": "Gómez Restrepo",
    "telefono": "3015550101", "ciudad": "Medellín", "empresa": "Magneto Empleos",
}

CANDIDATOS = [
    {   # Perfil tecnológico: el caso trabajado en el documento (Alt + D en el prototipo).
        "email": "ana.rios@correo.com", "first_name": "Ana María", "last_name": "Ríos Bedoya",
        "telefono": "3001234567", "ciudad": "Medellín",
        "habilidades": {"Python": 5, "Django": 3, "SQL": 4, "Docker": 3, "Git": 5, "Scrum": 3,
                        "Linux": 4},
        "por_aprender": ["Neo4j / Cypher", "AWS"],
        "experiencia": "TechNova S.A.S. — Desarrolladora backend (2021 a la fecha)\n"
                       "Andes Analytics — Analista de datos (2019 a 2021)",
        "educacion": "Ingeniería de Sistemas, Universidad EAFIT, 2019",
    },
    {   # Perfil de temporada, sin experiencia previa (Alt + N en el prototipo).
        "email": "camilo.zapata@correo.com", "first_name": "Camilo",
        "last_name": "Zapata Ospina", "telefono": "3109876543", "ciudad": "Medellín",
        "habilidades": {"Trabajo en equipo": 4, "Puntualidad": 5, "Atención al cliente": 3,
                        "Carga y descarga": 3, "Alistamiento de pedidos": 2},
        "por_aprender": ["Manejo de inventarios", "Manejo de caja"],
        "experiencia": "Distribuidora El Paisa — Auxiliar de cargue (temporada 2024)",
        "educacion": "Bachiller académico, 2022",
    },
]


def _usuario(datos, rol):
    campos = {k: datos[k] for k in ("first_name", "last_name", "telefono", "ciudad")}
    campos.update(rol=rol, empresa=datos.get("empresa", ""), acepta_tratamiento_datos=True)
    usuario, creado = Usuario.objects.update_or_create(email=datos["email"], defaults=campos)
    if creado or not usuario.check_password(CLAVE_DEMO):
        usuario.set_password(CLAVE_DEMO)
        usuario.save()
    return usuario


def _descripcion(v):
    return (f"{v['empresa']} busca {v['cargo'].lower()} en {v['ciudad']}. "
            f"Modalidad {v['modalidad'].lower()}, contrato {v['jornada'].lower()}.")


@transaction.atomic
def cargar():
    """Deja SQLite listo para la demostración. Se puede ejecutar varias veces.

    Devuelve un resumen {habilidades, vacantes, candidatos, en_grafo}.
    """
    total_habilidades = vacantes.cargar_catalogo()
    en_grafo = vacantes.sincronizar_catalogo_en_grafo()

    reclutador = _usuario(RECLUTADOR, Usuario.Rol.RECLUTADOR)
    areas = {a.nombre: a for a in AreaOcupacional.objects.all()}
    habilidades = {h.nombre: h for h in Habilidad.objects.all()}
    ahora = timezone.now()

    demo = json.loads((vacantes.DATOS / "vacantes_demo.json").read_text(encoding="utf-8"))
    for v in demo:
        existente = Vacante.objects.filter(reclutador=reclutador, titulo=v["titulo"]).first()
        datos = {"titulo": v["titulo"], "empresa": v["empresa"], "cargo": v["cargo"],
                 "descripcion": _descripcion(v), "area": areas[v["area"]],
                 "ciudad": v["ciudad"], "modalidad": v["modalidad"], "jornada": v["jornada"],
                 "salario": v["salario"]}
        requisitos = [{"habilidad": habilidades[r["habilidad"]], "peso": str(r["peso"]),
                       "nivel_minimo": r["nivel_minimo"], "obligatoria": r["obligatoria"]}
                      for r in v["requisitos"]]
        vacante, ok = vacantes.guardar_vacante(
            reclutador, datos, requisitos, publicar=True, vacante=existente,
            centralidad=v["centralidad"])
        Vacante.objects.filter(pk=vacante.pk).update(
            publicada_en=ahora - timedelta(days=v["dias_publicada"]))
        en_grafo = en_grafo and ok

    for c in CANDIDATOS:
        perfil = perfiles.perfil_de(_usuario(c, Usuario.Rol.CANDIDATO))
        perfiles.guardar_habilidades(perfil, c["habilidades"], c["por_aprender"])
        datos = perfiles.datos_para_confirmar(perfil)
        datos.update(experiencia=c["experiencia"], educacion=c["educacion"])
        en_grafo = perfiles.confirmar_perfil(perfil, datos) and en_grafo

    return {"habilidades": total_habilidades, "vacantes": len(demo),
            "candidatos": len(CANDIDATOS), "en_grafo": en_grafo}
