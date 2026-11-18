"""Rutas de los Modulos Entrenador y Estudiante (seguimiento)."""
from django.urls import path
from . import views

app_name = "seguimiento"

urlpatterns = [
    # Modulo Entrenador
    path(
        "mis-disciplinas/",
        views.VistaMisDisciplinasEntrenador.as_view(),
        name="entrenador_mis_disciplinas",
    ),
    path(
        "mis-disciplinas/<uuid:disciplina_id>/",
        views.VistaNominaDisciplinaEntrenador.as_view(),
        name="entrenador_nomina_disciplina",
    ),
    path(
        "sesiones/",
        views.VistaHistorialSesionesEntrenador.as_view(),
        name="lista_sesiones",
    ),
    path(
        "sesiones/nueva/",
        views.VistaCrearSesionEntrenamiento.as_view(),
        name="crear_sesion",
    ),
    path(
        "sesiones/<uuid:sesion_id>/",
        views.VistaGestionarSesionAsistenciaEvaluacion.as_view(),
        name="gestionar_sesion",
    ),
    # Modulo Estudiante
    path(
        "estudiante/mis-disciplinas/",
        views.VistaMisDisciplinasEstudiante.as_view(),
        name="estudiante_mis_disciplinas",
    ),
    path(
        "estudiante/mi-asistencia/",
        views.VistaMiAsistenciaYRendimientoEstudiante.as_view(),
        name="estudiante_mi_asistencia",
    ),
]
