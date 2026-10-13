"""Lógica de negocio de las cuentas. Las vistas solo llaman a estas funciones."""
import logging

from django.contrib.auth import authenticate, login, logout

from cuentas.models import Usuario

logger = logging.getLogger(__name__)


def normalizar_correo(correo):
    return (correo or "").strip().lower()


def existe_cuenta(correo):
    return Usuario.objects.filter(email=normalizar_correo(correo)).exists()


def registrar_usuario(*, correo, clave, nombres, apellidos, telefono, ciudad,
                      rol=Usuario.Rol.CANDIDATO, empresa="", acepta_datos=True):
    """Crea la cuenta. La contraseña se guarda cifrada (ver cuentas/hashers.py)."""
    usuario = Usuario.objects.create_user(
        email=correo,
        password=clave,
        first_name=nombres.strip(),
        last_name=apellidos.strip(),
        telefono=telefono.strip(),
        ciudad=ciudad,
        rol=rol,
        empresa=empresa.strip() if rol == Usuario.Rol.RECLUTADOR else "",
        acepta_tratamiento_datos=acepta_datos,
    )
    logger.info("Cuenta creada: usuario %s con rol %s", usuario.pk, usuario.rol)
    return usuario


def iniciar_sesion(request, correo, clave):
    """Devuelve el usuario si las credenciales son válidas; si no, None."""
    usuario = authenticate(request, username=normalizar_correo(correo), password=clave)
    if usuario is None:
        logger.warning("Intento de inicio de sesión fallido")
        return None
    login(request, usuario)
    return usuario


def cerrar_sesion(request):
    logout(request)
