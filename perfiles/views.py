from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from cuentas.models import Usuario
from cuentas.permisos import rol_requerido
from perfiles import services
from perfiles.forms import CargaCVForm, PerfilForm
from perfiles.models import HojaDeVida

solo_candidato = rol_requerido(Usuario.Rol.CANDIDATO)

AVISO_INSUFICIENTE = (
    "No logramos extraer información suficiente de su hoja de vida. Suele pasar cuando el "
    "documento es una imagen escaneada. Complete sus datos manualmente.")
AVISO_GRAFO = ("El grafo de Neo4j no está disponible en este momento. Su perfil quedó "
               "guardado y se sincronizará después.")


@solo_candidato
def cargar_cv(request):
    """Primer paso del candidato: subir la hoja de vida (flujo resume-first)."""
    perfil = services.perfil_de(request.user)
    enviado = request.method == "POST"
    form = CargaCVForm(request.POST, request.FILES) if enviado else CargaCVForm()
    if enviado and form.is_valid():
        hoja = services.procesar_hoja_de_vida(perfil, form.cleaned_data["archivo"])
        if hoja.suficiente:
            messages.success(request, "Leímos su hoja de vida. Revise los datos y confirme.")
        else:
            messages.warning(request, AVISO_INSUFICIENTE)
        return redirect("perfiles:confirmar_cv", pk=hoja.pk)
    return render(request, "perfiles/cargar_cv.html", {
        "form": form, "perfil": perfil, "seccion": "perfil"})


@solo_candidato
def confirmar(request, pk=None):
    """Formulario precargado (con `pk` de la hoja de vida) o manual (sin él)."""
    perfil = services.perfil_de(request.user)
    hoja = get_object_or_404(HojaDeVida, pk=pk, perfil=perfil) if pk else None
    faltantes = hoja.faltantes if hoja else []

    if request.method == "POST":
        form = PerfilForm(request.POST, faltantes=faltantes)
        if form.is_valid():
            datos = form.cleaned_data
            en_grafo = services.confirmar_perfil(perfil, datos, datos["niveles"], hoja=hoja)
            version = services.version_vigente(perfil)
            messages.success(
                request, f"Perfil confirmado. Guardamos la versión {version.numero} como "
                         "su perfil válido.")
            if not en_grafo:
                messages.warning(request, AVISO_GRAFO, extra_tags="grafo")
            return redirect("raiz")
    else:
        form = PerfilForm(initial=services.datos_para_confirmar(perfil, hoja),
                          faltantes=faltantes)
    return render(request, "perfiles/confirmar.html", {
        "form": form, "hoja": hoja, "perfil": perfil, "seccion": "perfil"})


@solo_candidato
def mi_perfil(request):
    perfil = services.perfil_de(request.user)
    return render(request, "perfiles/mi_perfil.html", {
        "perfil": perfil, "vigente": services.version_vigente(perfil),
        "versiones": perfil.versiones.select_related("hoja_de_vida"),
        "habilidades": perfil.habilidades.select_related("habilidad"),
        "seccion": "perfil"})
