"""Rutas del Modulo Coordinador Deportivo (disciplinas, entrenadores, estudiantes, inscripciones)."""
from django.urls import path
from . import views

app_name = "deportes"

urlpatterns = [
    # Disciplinas deportivas
    path("disciplinas/", views.VistaListaDisciplinas.as_view(), name="lista_disciplinas"),
    path("disciplinas/nueva/", views.VistaCrearDisciplina.as_view(), name="crear_disciplina"),
    path(
        "disciplinas/<uuid:pk>/editar/",
        views.VistaEditarDisciplina.as_view(),
        name="editar_disciplina",
    ),
    path(
        "disciplinas/<uuid:pk>/estado/",
        views.vista_cambiar_estado_disciplina,
        name="cambiar_estado_disciplina",
    ),
    # Entrenadores
    path("entrenadores/", views.VistaListaEntrenadores.as_view(), name="lista_entrenadores"),
    path("entrenadores/nuevo/", views.VistaCrearEntrenador.as_view(), name="crear_entrenador"),
    path(
        "entrenadores/<uuid:pk>/editar/",
        views.VistaEditarEntrenador.as_view(),
        name="editar_entrenador",
    ),
    path(
        "entrenadores/<uuid:pk>/estado/",
        views.vista_cambiar_estado_entrenador,
        name="cambiar_estado_entrenador",
    ),
    # Estudiantes
    path("estudiantes/", views.VistaListaEstudiantes.as_view(), name="lista_estudiantes"),
    path("estudiantes/nuevo/", views.VistaCrearEstudiante.as_view(), name="crear_estudiante"),
    path(
        "estudiantes/<uuid:pk>/editar/",
        views.VistaEditarEstudiante.as_view(),
        name="editar_estudiante",
    ),
    path(
        "estudiantes/<uuid:pk>/estado/",
        views.vista_cambiar_estado_estudiante,
        name="cambiar_estado_estudiante",
    ),
    # Inscripciones
    path("inscripciones/", views.VistaListaInscripciones.as_view(), name="lista_inscripciones"),
    path(
        "inscripciones/nueva/",
        views.VistaCrearInscripcion.as_view(),
        name="crear_inscripcion",
    ),
    path(
        "inscripciones/<uuid:pk>/baja/",
        views.vista_dar_baja_inscripcion,
        name="dar_baja_inscripcion",
    ),
]
