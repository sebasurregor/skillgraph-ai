from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from perfiles import services as perfiles


@login_required
def portada(request):
    """Lleva a cada usuario a su punto de partida.

    Flujo resume-first: al candidato sin perfil confirmado lo primero que se le
    ofrece es subir su hoja de vida.
    """
    usuario = request.user
    if usuario.es_reclutador:
        return redirect("vacantes:lista")
    if not perfiles.tiene_perfil_confirmado(usuario):
        return redirect("perfiles:cargar_cv")
    return redirect("recomendaciones:lista")
