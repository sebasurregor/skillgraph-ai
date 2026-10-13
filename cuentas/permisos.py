"""Control de acceso por rol para las vistas."""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def rol_requerido(rol):
    """Exige sesión iniciada y que el usuario tenga el rol indicado."""
    def decorador(vista):
        @wraps(vista)
        @login_required
        def envoltura(request, *args, **kwargs):
            if request.user.rol != rol:
                raise PermissionDenied
            return vista(request, *args, **kwargs)
        return envoltura
    return decorador
