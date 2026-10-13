"""Control de acceso por rol para las vistas."""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission


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


class EsReclutador(BasePermission):
    """Permiso de DRF: sesión iniciada con rol de reclutador."""

    def has_permission(self, request, view):
        usuario = request.user
        return bool(usuario and usuario.is_authenticated and usuario.es_reclutador)
