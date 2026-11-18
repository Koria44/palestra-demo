"""Rutas del modulo auditoria."""
from django.urls import path
from . import views

app_name = "auditoria"

urlpatterns = [
    path("", views.VistaListaAuditoria.as_view(), name="lista_auditoria"),
]
