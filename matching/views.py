from django.shortcuts import render

from cuentas.models import Usuario
from cuentas.permisos import rol_requerido
from matching import services
from perfiles import services as perfiles

solo_candidato = rol_requerido(Usuario.Rol.CANDIDATO)

ORDENES = [(services.ORDEN_RELEVANCIA, "Mayor ajuste"), (services.ORDEN_FECHA, "Más recientes")]


@solo_candidato
def recomendaciones(request):
    """HU-RF-005: vacantes recomendadas con su porcentaje y la explicación del match."""
    perfil = perfiles.perfil_de(request.user)
    orden = request.GET.get("orden")
    if orden not in dict(ORDENES):
        orden = services.ORDEN_RELEVANCIA
    todas = request.GET.get("ver") == "todas"
    resultado = services.recomendar(perfil, orden=orden, todas=todas)
    return render(request, "matching/recomendaciones.html", {
        **resultado, "perfil": perfil, "orden": orden, "ordenes": ORDENES, "todas": todas,
        "preferencias": perfiles.preferencias_de(perfil), "pesos": services.pesos(),
        "seccion": "recomendaciones"})
