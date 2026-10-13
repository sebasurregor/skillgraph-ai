from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from cuentas.models import Usuario
from cuentas.permisos import rol_requerido
from postulaciones import services
from postulaciones.models import Postulacion
from vacantes.models import Vacante

solo_candidato = rol_requerido(Usuario.Rol.CANDIDATO)
solo_reclutador = rol_requerido(Usuario.Rol.RECLUTADOR)


def _volver(request, defecto):
    destino = request.POST.get("siguiente", "")
    if url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
        return redirect(destino)
    return redirect(defecto)


# ---- Candidato (HU-RF-006) ----------------------------------------------------

@solo_candidato
@require_POST
def postular(request, vacante_id):
    """Un solo clic: crea la postulación y confirma el envío."""
    try:
        postulacion, creada = services.postular(request.user, vacante_id)
    except services.PostulacionRechazada as exc:
        messages.error(request, str(exc))
        return _volver(request, "recomendaciones:lista")
    vacante = postulacion.vacante
    if creada:
        messages.success(
            request, f"Postulación enviada a {vacante.empresa} para «{vacante.titulo}». "
                     "Puede seguir su estado en Mis postulaciones.")
    else:
        messages.info(request, f"Ya se había postulado a «{vacante.titulo}». "
                               "No se envió una segunda postulación.")
    return _volver(request, "recomendaciones:lista")


@solo_candidato
def mis_postulaciones(request):
    return render(request, "postulaciones/mis_postulaciones.html", {
        "postulaciones": services.postulaciones_de(request.user),
        "seccion": "postulaciones"})


# ---- Reclutador (HU-RF-013) ---------------------------------------------------

@solo_reclutador
def de_vacante(request, vacante_id):
    """Postulaciones de una vacante propia, priorizadas por match."""
    vacante = get_object_or_404(Vacante, pk=vacante_id, reclutador=request.user)
    solo_obligatorias = request.GET.get("filtro") == "obligatorias"
    return render(request, "postulaciones/de_vacante.html", {
        **services.priorizadas(vacante, solo_obligatorias=solo_obligatorias),
        "vacante": vacante, "solo_obligatorias": solo_obligatorias,
        "estados": Postulacion.Estado.choices, "seccion": "vacantes"})


def _postulacion_del_reclutador(request, pk):
    return get_object_or_404(Postulacion.objects.select_related("vacante", "candidato"),
                             pk=pk, vacante__reclutador=request.user)


@solo_reclutador
@require_POST
def cambiar_estado(request, pk):
    postulacion = _postulacion_del_reclutador(request, pk)
    try:
        services.cambiar_estado(postulacion, request.POST.get("estado"))
        messages.success(request, "Estado de la postulación actualizado.")
    except services.PostulacionRechazada as exc:
        messages.error(request, str(exc))
    return _volver(request, redirect("postulaciones:de_vacante",
                                     vacante_id=postulacion.vacante_id).url)


@solo_reclutador
def hoja_de_vida(request, pk):
    """Descarga de la hoja de vida original de quien se postuló."""
    hoja = services.hoja_de_vida_de(_postulacion_del_reclutador(request, pk))
    if hoja is None:
        raise Http404
    return FileResponse(hoja.archivo.open("rb"), as_attachment=True,
                        filename=hoja.nombre_original)
