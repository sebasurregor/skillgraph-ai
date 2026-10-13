from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from cuentas import services
from cuentas.forms import ClaveForm, CorreoForm, RegistroForm

SESION_CORREO = "correo_ingreso"


def ingresar(request):
    """Paso 1: pide el correo y decide entre inicio de sesión y registro."""
    if request.user.is_authenticated:
        return redirect("cuentas:inicio")
    form = CorreoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        correo = form.cleaned_data["correo"]
        request.session[SESION_CORREO] = correo
        if services.existe_cuenta(correo):
            return redirect("cuentas:ingresar_clave")
        return redirect("cuentas:registro")
    return render(request, "cuentas/ingresar.html", {"form": form})


def ingresar_clave(request):
    """Paso 2: pide la contraseña de la cuenta existente."""
    if request.user.is_authenticated:
        return redirect("cuentas:inicio")
    correo = request.session.get(SESION_CORREO)
    if not correo:
        return redirect("cuentas:ingresar")
    form = ClaveForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if services.iniciar_sesion(request, correo, form.cleaned_data["clave"]):
            return redirect("raiz")
        form.add_error("clave", "Las credenciales no coinciden. Verifique su contraseña.")
        form.marcar_invalidos()
    return render(request, "cuentas/ingresar_clave.html", {"form": form, "correo": correo})


def registro(request):
    if request.user.is_authenticated:
        return redirect("cuentas:inicio")
    correo = request.session.get(SESION_CORREO, "")
    form = RegistroForm(request.POST or None, initial={"correo": correo})
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        usuario = services.registrar_usuario(
            correo=d["correo"], clave=d["clave"], nombres=d["nombres"],
            apellidos=d["apellidos"], telefono=d["telefono"], ciudad=d["ciudad"],
            rol=d["rol"], empresa=d["empresa"], acepta_datos=d["acepta_datos"],
        )
        request.session[SESION_CORREO] = usuario.email
        messages.success(request, "Su cuenta fue creada correctamente. Ingrese la contraseña "
                                  "que acaba de definir para continuar.")
        return redirect("cuentas:ingresar_clave")
    return render(request, "cuentas/registro.html", {"form": form, "correo": correo})


@require_POST
def salir(request):
    services.cerrar_sesion(request)
    messages.info(request, "Sesión cerrada.")
    return redirect("cuentas:ingresar")


@login_required
def inicio(request):
    return render(request, "cuentas/inicio.html")
