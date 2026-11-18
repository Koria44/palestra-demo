"""
Rutas versionadas (/api/v1/) de la API RESTful de PALESTRA y documentacion OpenAPI
restringida exclusivamente al Coordinador Deportivo (Seccion 9).
"""
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter
from . import views
from .permisos import EsCoordinadorPermiso

app_name = "api"

enrutador = DefaultRouter()
enrutador.register(r"disciplinas", views.DisciplinaViewSet, basename="disciplinas")
enrutador.register(
    r"entrenadores", views.PerfilEntrenadorViewSet, basename="entrenadores"
)
enrutador.register(
    r"estudiantes", views.PerfilEstudianteViewSet, basename="estudiantes"
)
enrutador.register(
    r"inscripciones", views.InscripcionViewSet, basename="inscripciones"
)
enrutador.register(
    r"sesiones", views.SesionEntrenamientoViewSet, basename="sesiones"
)
enrutador.register(r"asistencias", views.AsistenciaViewSet, basename="asistencias")
enrutador.register(
    r"evaluaciones", views.EvaluacionViewSet, basename="evaluaciones"
)

urlpatterns = [
    path("", include(enrutador.urls)),
    path("reportes/", views.ReporteResumenAPIView.as_view(), name="reportes_resumen"),
    path(
        "esquema/",
        SpectacularAPIView.as_view(permission_classes=[EsCoordinadorPermiso]),
        name="esquema_openapi",
    ),
    path(
        "documentacion/",
        SpectacularSwaggerView.as_view(
            url_name="api:esquema_openapi",
            permission_classes=[EsCoordinadorPermiso],
        ),
        name="documentacion_openapi",
    ),
]
