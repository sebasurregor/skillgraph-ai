from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from cuentas.models import Usuario
from cuentas.permisos import rol_requerido
from skillgraph.formularios import un_solo_foco
from vacantes import services
from vacantes.forms import RequisitoFormSet, VacanteForm
from vacantes.models import Vacante

solo_reclutador = rol_requerido(Usuario.Rol.RECLUTADOR)
PREFIJO = "req"
AVISO_GRAFO = ("El grafo de Neo4j no está disponible en este momento. Los datos quedaron "
               "guardados y se sincronizarán después.")


def _vacante_propia(request, pk):
    return get_object_or_404(Vacante, pk=pk, reclutador=request.user)


def _avisar_si_falta_grafo(request, en_grafo):
    if not en_grafo:
        messages.warning(request, AVISO_GRAFO)


@solo_reclutador
def lista(request):
    return render(request, "vacantes/lista.html", {
        "vacantes": services.vacantes_de(request.user), "seccion": "vacantes"})


@solo_reclutador
def editar(request, pk=None):
    """Crea (sin `pk`) o edita una vacante; guarda como borrador o publica."""
    vacante = _vacante_propia(request, pk) if pk else None
    errores_negocio = []

    if request.method == "POST":
        publicar = request.POST.get("accion") == "publicar"
        form = VacanteForm(request.POST, instance=vacante, publicar=publicar)
        formset = RequisitoFormSet(request.POST, prefix=PREFIJO, publicar=publicar)
        form_valido, formset_valido = form.is_valid(), formset.is_valid()
        if form_valido and formset_valido:
            try:
                _, en_grafo = services.guardar_vacante(
                    request.user, form.cleaned_data, formset.requisitos(),
                    publicar=publicar, vacante=vacante)
            except services.ErrorDeNegocio as exc:
                errores_negocio = exc.errores
            else:
                messages.success(request, "Vacante publicada." if publicar
                                 else "Vacante guardada como borrador.")
                _avisar_si_falta_grafo(request, en_grafo)
                return redirect("vacantes:lista")
        un_solo_foco(form, *formset.forms)
    else:
        inicial = {} if vacante else {"empresa": request.user.empresa}
        form = VacanteForm(instance=vacante, initial=inicial)
        formset = RequisitoFormSet(
            prefix=PREFIJO, initial=services.requisitos_de(vacante) if vacante else [])

    hay_errores = bool(form.errors or formset.total_error_count() or errores_negocio)
    return render(request, "vacantes/formulario.html", {
        "form": form, "formset": formset, "vacante": vacante, "seccion": "vacantes",
        "hay_errores": request.method == "POST" and hay_errores,
        "errores_requisitos": formset.mensajes + errores_negocio if request.method == "POST"
        else [],
    })


@solo_reclutador
@require_POST
def publicar(request, pk):
    vacante = _vacante_propia(request, pk)
    try:
        en_grafo = services.publicar_vacante(vacante)
    except services.ErrorDeNegocio as exc:
        messages.error(request, "No se pudo publicar: " + " ".join(exc.errores))
        return redirect("vacantes:editar", pk=vacante.pk)
    messages.success(request, "Vacante publicada.")
    _avisar_si_falta_grafo(request, en_grafo)
    return redirect("vacantes:lista")


@solo_reclutador
@require_POST
def despublicar(request, pk):
    en_grafo = services.despublicar_vacante(_vacante_propia(request, pk))
    messages.success(request, "Vacante despublicada. Quedó como borrador.")
    _avisar_si_falta_grafo(request, en_grafo)
    return redirect("vacantes:lista")


@solo_reclutador
def eliminar(request, pk):
    vacante = _vacante_propia(request, pk)
    if request.method == "POST":
        en_grafo = services.eliminar_vacante(vacante)
        messages.success(request, "Vacante eliminada.")
        _avisar_si_falta_grafo(request, en_grafo)
        return redirect("vacantes:lista")
    return render(request, "vacantes/confirmar_eliminar.html", {
        "vacante": vacante, "seccion": "vacantes"})
