"""Vistas de consulta de la bitacora de auditoria (solo Coordinador)."""
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views import View
from apps.cuentas.mixins import SoloCoordinadorMixin
from .models import RegistroAuditoria


class VistaListaAuditoria(SoloCoordinadorMixin, View):
    """Permite al Coordinador Deportivo revisar la bitacora de auditoria inmutable."""

    plantilla = "auditoria/lista_auditoria.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        busqueda = request.GET.get("q", "").strip()
        accion_filtro = request.GET.get("accion", "").strip()
        entidad_filtro = request.GET.get("entidad", "").strip()

        registros = RegistroAuditoria.objects.select_related("usuario").all()
        if busqueda:
            registros = registros.filter(
                Q(accion__icontains=busqueda)
                | Q(entidad__icontains=busqueda)
                | Q(identificador__icontains=busqueda)
                | Q(usuario__email__icontains=busqueda)
            )
        if accion_filtro:
            registros = registros.filter(accion=accion_filtro)
        if entidad_filtro:
            registros = registros.filter(entidad=entidad_filtro)

        acciones_disponibles = (
            RegistroAuditoria.objects.values_list("accion", flat=True)
            .distinct()
            .order_by("accion")
        )
        entidades_disponibles = (
            RegistroAuditoria.objects.values_list("entidad", flat=True)
            .distinct()
            .order_by("entidad")
        )

        paginador = Paginator(registros, 20)
        pagina_obj = paginador.get_page(request.GET.get("pagina"))

        contexto = {
            "pagina_obj": pagina_obj,
            "busqueda": busqueda,
            "accion_filtro": accion_filtro,
            "entidad_filtro": entidad_filtro,
            "acciones_disponibles": acciones_disponibles,
            "entidades_disponibles": entidades_disponibles,
        }
        return render(request, self.plantilla, contexto)
