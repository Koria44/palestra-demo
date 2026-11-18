"""Middleware para obligar al cambio de contrasena temporal en el primer ingreso."""
from typing import Callable
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse


class CambioContrasenaObligatorioMiddleware:
    """
    Si el usuario autenticado tiene debe_cambiar_contrasena=True, redirige a la
    vista de cambio obligatorio de contrasena antes de permitir navegar por el sistema.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        usuario = getattr(request, "user", None)
        if usuario and usuario.is_authenticated and getattr(usuario, "debe_cambiar_contrasena", False):
            rutas_exentas = {
                reverse("cuentas:cambiar_contrasena"),
                reverse("cuentas:cerrar_sesion"),
                reverse("cuentas:aviso_privacidad"),
            }
            if (
                request.path not in rutas_exentas
                and not request.path.startswith("/static/")
            ):
                return redirect("cuentas:cambiar_contrasena")
        return self.get_response(request)
