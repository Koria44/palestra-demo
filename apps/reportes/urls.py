"""Rutas del Modulo Reportes y Exportaciones."""
from django.urls import path
from . import views

app_name = "reportes"

urlpatterns = [
    path("", views.VistaPanelReportes.as_view(), name="panel_reportes"),
    path("exportar/csv/", views.VistaExportarReporteCSV.as_view(), name="exportar_csv"),
    path("exportar/pdf/", views.VistaExportarReportePDF.as_view(), name="exportar_pdf"),
]
