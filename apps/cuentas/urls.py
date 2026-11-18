"""Rutas de la aplicacion cuentas (autenticacion, paneles, activacion y privacidad)."""
from django.urls import path
from . import views

app_name = "cuentas"

urlpatterns = [
    path("", views.vista_panel_inicio, name="panel_inicio"),
    path("iniciar-sesion/", views.VistaIniciarSesion.as_view(), name="iniciar_sesion"),
    path("cerrar-sesion/", views.vista_cerrar_sesion, name="cerrar_sesion"),
    path("panel/coordinador/", views.VistaPanelCoordinador.as_view(), name="panel_coordinador"),
    path("panel/entrenador/", views.VistaPanelEntrenador.as_view(), name="panel_entrenador"),
    path("panel/estudiante/", views.VistaPanelEstudiante.as_view(), name="panel_estudiante"),
    path("cambiar-contrasena/", views.VistaCambiarContrasena.as_view(), name="cambiar_contrasena"),
    path("activar-cuenta/<str:token>/", views.VistaActivarCuenta.as_view(), name="activar_cuenta"),
    path(
        "recuperar-contrasena/",
        views.VistaRecuperarContrasena.as_view(),
        name="recuperar_contrasena",
    ),
    path(
        "recuperar-contrasena/enviado/",
        views.VistaRecuperarContrasenaEnviado.as_view(),
        name="recuperar_contrasena_enviado",
    ),
    path(
        "recuperar-contrasena/<uidb64>/<token>/",
        views.VistaRecuperarContrasenaConfirmar.as_view(),
        name="recuperar_contrasena_confirmar",
    ),
    path(
        "recuperar-contrasena/completado/",
        views.VistaRecuperarContrasenaCompletado.as_view(),
        name="recuperar_contrasena_completado",
    ),
    path("aviso-privacidad/", views.vista_aviso_privacidad, name="aviso_privacidad"),
]
