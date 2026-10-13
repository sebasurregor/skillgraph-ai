from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from cuentas.models import Usuario
from cuentas.permisos import rol_requerido
from perfiles import services
from perfiles.forms import CargaCVForm, PerfilForm, PreferenciasForm
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
            # La primera vez, el siguiente paso es decir qué empleo busca.
            if services.preferencias_de(perfil) is None:
                return redirect("perfiles:preferencias")
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
        "preferencias": services.preferencias_de(perfil),
        "por_aprender": perfil.por_aprender.all(),
        "seccion": "perfil"})


@solo_candidato
def preferencias(request):
    """Preferencias laborales (HU-RF-004): se pueden editar en cualquier momento."""
    perfil = services.perfil_de(request.user)
    actuales = services.preferencias_de(perfil)
    opciones = services.opciones_de_preferencias(actuales)

    if request.method == "POST":
        form = PreferenciasForm(request.POST, opciones=opciones)
        if form.is_valid():
            datos = form.cleaned_data
            services.guardar_preferencias(perfil, datos, por_aprender=datos["por_aprender"])
            messages.success(request, "Preferencias guardadas. Las usaremos para filtrar "
                                      "sus recomendaciones.")
            return redirect("raiz")
    else:
        inicial = {"por_aprender": list(perfil.por_aprender.all())}
        if actuales:
            inicial.update({c: getattr(actuales, c) for c in services.CAMPOS_PREFERENCIAS})
        form = PreferenciasForm(initial=inicial, opciones=opciones)
    return render(request, "perfiles/preferencias.html", {
        "form": form, "primera_vez": actuales is None, "seccion": "preferencias"})
