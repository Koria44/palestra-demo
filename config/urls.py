"""Enrutador principal de URLs de PALESTRA y manejadores personalizados de errores."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("administracion/", admin.site.urls),
    path("", include("apps.cuentas.urls", namespace="cuentas")),
    path("deportes/", include("apps.deportes.urls", namespace="deportes")),
    path("seguimiento/", include("apps.seguimiento.urls", namespace="seguimiento")),
    path("reportes/", include("apps.reportes.urls", namespace="reportes")),
    path("auditoria/", include("apps.auditoria.urls", namespace="auditoria")),
    path("api/v1/", include("apps.api.urls", namespace="api")),
]

handler403 = "apps.cuentas.views.error_403"
handler404 = "apps.cuentas.views.error_404"
handler500 = "apps.cuentas.views.error_500"
