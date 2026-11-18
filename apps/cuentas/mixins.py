"""Mixins y decoradores de autorizacion por rol en el servidor (Seccion 5 y 6)."""
from functools import wraps
from typing import Any, Iterable
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from .models import Usuario


class RolRequeridoMixin(LoginRequiredMixin):
    """
    Verifica en el servidor que el usuario autenticado posea uno de los roles permitidos
    y que su cuenta se encuentre activa. Si no cumple, responde HTTP 403.
    """

    roles_permitidos: Iterable[str] = ()

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not getattr(request.user, "activo", True):
            raise PermissionDenied("Su cuenta se encuentra desactivada.")
        if self.roles_permitidos and request.user.rol not in self.roles_permitidos:
            raise PermissionDenied(
                "No cuenta con los permisos necesarios para acceder a esta seccion."
            )
        return super().dispatch(request, *args, **kwargs)


class SoloCoordinadorMixin(RolRequeridoMixin):
    roles_permitidos = (Usuario.ROL_COORDINADOR,)


class SoloEntrenadorMixin(RolRequeridoMixin):
    roles_permitidos = (Usuario.ROL_ENTRENADOR,)


class SoloEstudianteMixin(RolRequeridoMixin):
    roles_permitidos = (Usuario.ROL_ESTUDIANTE,)


def rol_requerido(*roles: str):
    """Decorador para vistas basadas en funciones que exige uno de los roles indicados."""

    def decorador(vista_func):
        @wraps(vista_func)
        def envoltura(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            if not request.user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login
                return redirect_to_login(request.get_full_path())
            if not getattr(request.user, "activo", True) or (
                roles and request.user.rol not in roles
            ):
                raise PermissionDenied(
                    "No cuenta con los permisos necesarios para realizar esta accion."
                )
            return vista_func(request, *args, **kwargs)

        return envoltura

    return decorador
