"""
Vistas del Modulo Reportes (Seccion 4.5, 5 y 6):
- Visibilidad diferenciada en servidor:
  * Coordinador: todos los filtros (disciplina, entrenador, estudiante, rango de fechas).
  * Entrenador: solo el alcance de sus disciplinas asignadas.
  * Estudiante: solo su propio resumen personal.
- Exportacion a CSV (protegido contra inyeccion de formulas) y PDF, registrando cada
  exportacion en RegistroAuditoria.
"""
from datetime import date
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views import View
from apps.auditoria.models import registrar_evento_auditoria
from apps.cuentas.mixins import RolRequeridoMixin
from apps.cuentas.models import Usuario
from apps.deportes.models import Disciplina, PerfilEntrenador, PerfilEstudiante
from .servicios import (
    construir_datos_reporte,
    generar_csv_reporte,
    generar_pdf_reporte,
)


def _parsear_fecha_segura(valor: str) -> date | None:
    if not valor:
        return None
    try:
        return date.fromisoformat(valor.strip())
    except ValueError:
        return None


def _extraer_parametros_reporte(request: HttpRequest) -> dict:
    disciplina_id = request.GET.get("disciplina", "").strip()
    entrenador_id = request.GET.get("entrenador", "").strip()
    estudiante_id = request.GET.get("estudiante", "").strip()
    fecha_desde_str = request.GET.get("fecha_desde", "").strip()
    fecha_hasta_str = request.GET.get("fecha_hasta", "").strip()
    return {
        "disciplina_id": disciplina_id,
        "entrenador_id": entrenador_id,
        "estudiante_id": estudiante_id,
        "fecha_desde": _parsear_fecha_segura(fecha_desde_str),
        "fecha_hasta": _parsear_fecha_segura(fecha_hasta_str),
        "fecha_desde_str": fecha_desde_str,
        "fecha_hasta_str": fecha_hasta_str,
    }


class VistaPanelReportes(RolRequeridoMixin, View):
    """Pantalla principal de reportes adaptada al alcance del rol autenticado."""

    roles_permitidos = (
        Usuario.ROL_COORDINADOR,
        Usuario.ROL_ENTRENADOR,
        Usuario.ROL_ESTUDIANTE,
    )
    plantilla = "reportes/panel_reportes.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        usuario: Usuario = request.user  # type: ignore[assignment]
        params = _extraer_parametros_reporte(request)

        datos_reporte = construir_datos_reporte(
            usuario_solicitante=usuario,
            disciplina_id=params["disciplina_id"],
            entrenador_id=params["entrenador_id"],
            estudiante_id=params["estudiante_id"],
            fecha_desde=params["fecha_desde"],
            fecha_hasta=params["fecha_hasta"],
        )

        # Listas de opciones de filtro segun el alcance del rol
        if usuario.es_coordinador:
            disciplinas_filtro = Disciplina.objects.order_by("nombre")
            entrenadores_filtro = PerfilEntrenador.objects.order_by(
                "apellidos", "nombres"
            )
            estudiantes_filtro = PerfilEstudiante.objects.order_by(
                "apellidos", "nombres"
            )
        elif usuario.es_entrenador:
            perfil_ent = getattr(usuario, "perfil_entrenador", None)
            disciplinas_filtro = Disciplina.objects.filter(
                asignaciones_entrenador__entrenador=perfil_ent
            ).distinct()
            entrenadores_filtro = PerfilEntrenador.objects.none()
            estudiantes_filtro = (
                PerfilEstudiante.objects.filter(
                    inscripciones__disciplina__in=disciplinas_filtro
                )
                .distinct()
                .order_by("apellidos", "nombres")
            )
        else:
            perfil_est = getattr(usuario, "perfil_estudiante", None)
            disciplinas_filtro = Disciplina.objects.filter(
                inscripciones__estudiante=perfil_est
            ).distinct()
            entrenadores_filtro = PerfilEntrenador.objects.none()
            estudiantes_filtro = PerfilEstudiante.objects.none()

        contexto = {
            "reporte": datos_reporte,
            "disciplinas_filtro": disciplinas_filtro,
            "entrenadores_filtro": entrenadores_filtro,
            "estudiantes_filtro": estudiantes_filtro,
            "filtros": params,
            "querystring_actual": request.GET.urlencode(),
        }
        return render(request, self.plantilla, contexto)


class VistaExportarReporteCSV(RolRequeridoMixin, View):
    """Exporta el reporte filtrado a CSV con proteccion contra inyeccion de formulas."""

    roles_permitidos = (
        Usuario.ROL_COORDINADOR,
        Usuario.ROL_ENTRENADOR,
        Usuario.ROL_ESTUDIANTE,
    )

    def get(self, request: HttpRequest) -> HttpResponse:
        usuario: Usuario = request.user  # type: ignore[assignment]
        params = _extraer_parametros_reporte(request)
        datos_reporte = construir_datos_reporte(
            usuario_solicitante=usuario,
            disciplina_id=params["disciplina_id"],
            entrenador_id=params["entrenador_id"],
            estudiante_id=params["estudiante_id"],
            fecha_desde=params["fecha_desde"],
            fecha_hasta=params["fecha_hasta"],
        )
        contenido_csv = generar_csv_reporte(datos_reporte)

        registrar_evento_auditoria(
            usuario=usuario,
            accion="exportacion_reporte_csv",
            entidad="Reporte",
            identificador=usuario.rol,
            request=request,
            detalle={
                "filas_exportadas": len(datos_reporte["filas_detalle"]),
                "disciplina_id": params["disciplina_id"],
                "estudiante_id": params["estudiante_id"],
            },
        )

        marca_fecha = timezone.localdate().strftime("%Y%m%d")
        respuesta = HttpResponse(
            contenido_csv, content_type="text/csv; charset=utf-8"
        )
        respuesta["Content-Disposition"] = (
            f'attachment; filename="reporte_palestra_{marca_fecha}.csv"'
        )
        return respuesta


class VistaExportarReportePDF(RolRequeridoMixin, View):
    """Exporta el reporte filtrado a PDF con formato institucional."""

    roles_permitidos = (
        Usuario.ROL_COORDINADOR,
        Usuario.ROL_ENTRENADOR,
        Usuario.ROL_ESTUDIANTE,
    )

    def get(self, request: HttpRequest) -> HttpResponse:
        usuario: Usuario = request.user  # type: ignore[assignment]
        params = _extraer_parametros_reporte(request)
        datos_reporte = construir_datos_reporte(
            usuario_solicitante=usuario,
            disciplina_id=params["disciplina_id"],
            entrenador_id=params["entrenador_id"],
            estudiante_id=params["estudiante_id"],
            fecha_desde=params["fecha_desde"],
            fecha_hasta=params["fecha_hasta"],
        )
        bytes_pdf = generar_pdf_reporte(datos_reporte, usuario)

        registrar_evento_auditoria(
            usuario=usuario,
            accion="exportacion_reporte_pdf",
            entidad="Reporte",
            identificador=usuario.rol,
            request=request,
            detalle={
                "filas_exportadas": len(datos_reporte["filas_detalle"]),
                "disciplina_id": params["disciplina_id"],
                "estudiante_id": params["estudiante_id"],
            },
        )

        marca_fecha = timezone.localdate().strftime("%Y%m%d")
        respuesta = HttpResponse(bytes_pdf, content_type="application/pdf")
        respuesta["Content-Disposition"] = (
            f'attachment; filename="reporte_palestra_{marca_fecha}.pdf"'
        )
        return respuesta
