"""
Vistas y ViewSets de la API RESTful v1 de PALESTRA (Seccion 5 y 9).
Aplica matriz de permisos en el servidor y aislamiento de querysets por rol:
- Coordinador: gestion de disciplinas e inscripciones; lectura global de sesiones, asistencias,
  evaluaciones y reportes; acceso exclusivo a OpenAPI. No registra asistencia ni evaluaciones.
- Entrenador: lectura de sus disciplinas e inscritos; registro y correccion de sesiones,
  asistencia y evaluaciones unicamente en sus disciplinas. No inscribe ni gestiona disciplinas.
- Estudiante: solo lectura de sus propias disciplinas, inscripciones, asistencias,
  evaluaciones y resumen de reporte. Nunca ve datos de otros estudiantes.
"""
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.auditoria.models import registrar_evento_auditoria
from apps.cuentas.models import Usuario
from apps.deportes.models import (
    Disciplina,
    Inscripcion,
    PerfilEntrenador,
    PerfilEstudiante,
)
from apps.reportes.servicios import construir_datos_reporte
from apps.seguimiento.models import Asistencia, Evaluacion, SesionEntrenamiento
from .permisos import EsCoordinadorPermiso, EsEntrenadorPermiso
from .serializadores import (
    AsistenciaSerializador,
    DisciplinaSerializador,
    EvaluacionSerializador,
    InscripcionSerializador,
    PerfilEntrenadorSerializador,
    PerfilEstudianteSerializador,
    SesionEntrenamientoSerializador,
)


class DisciplinaViewSet(viewsets.ModelViewSet):
    """Recurso API de disciplinas deportivas."""

    serializer_class = DisciplinaSerializador
    filterset_fields = ["activo", "dia"]
    search_fields = ["nombre", "lugar"]
    ordering_fields = ["nombre", "cupo_maximo"]

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return [EsCoordinadorPermiso()]

    def get_queryset(self):
        usuario: Usuario = self.request.user  # type: ignore[assignment]
        if usuario.es_coordinador:
            return Disciplina.objects.all()
        if usuario.es_entrenador:
            perfil = getattr(usuario, "perfil_entrenador", None)
            return Disciplina.objects.filter(
                asignaciones_entrenador__entrenador=perfil
            ).distinct()
        perfil_est = getattr(usuario, "perfil_estudiante", None)
        return Disciplina.objects.filter(
            inscripciones__estudiante=perfil_est
        ).distinct()


class PerfilEntrenadorViewSet(viewsets.ReadOnlyModelViewSet):
    """Recurso API de entrenadores (solo accesible para Coordinador)."""

    serializer_class = PerfilEntrenadorSerializador
    permission_classes = [EsCoordinadorPermiso]
    queryset = PerfilEntrenador.objects.select_related("usuario").all()
    filterset_fields = ["activo"]
    search_fields = ["nombres", "apellidos", "especialidad"]


class PerfilEstudianteViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Recurso API de estudiantes:
    - Coordinador: ve todos.
    - Entrenador: ve solo los inscritos activos en sus disciplinas.
    - Estudiante: denegado (403) para evitar listado o acceso a otros perfiles.
    """

    serializer_class = PerfilEstudianteSerializador
    filterset_fields = ["activo", "curso_o_carrera"]
    search_fields = ["nombres", "apellidos", "curso_o_carrera"]

    def get_queryset(self):
        usuario: Usuario = self.request.user  # type: ignore[assignment]
        if usuario.es_coordinador:
            return PerfilEstudiante.objects.select_related("usuario").all()
        if usuario.es_entrenador:
            perfil_ent = getattr(usuario, "perfil_entrenador", None)
            return (
                PerfilEstudiante.objects.select_related("usuario")
                .filter(
                    inscripciones__disciplina__asignaciones_entrenador__entrenador=perfil_ent,
                    inscripciones__estado=Inscripcion.ESTADO_ACTIVA,
                )
                .distinct()
            )
        raise DRFPermissionDenied(
            "Los estudiantes no tienen permiso para consultar el padrón de estudiantes."
        )


class InscripcionViewSet(viewsets.ModelViewSet):
    """
    Recurso API de inscripciones:
    - Coordinador: lectura, creacion (con validacion de cupo) y baja logica.
    - Entrenador: solo lectura de sus disciplinas.
    - Estudiante: solo lectura de sus propias inscripciones.
    """

    serializer_class = InscripcionSerializador
    filterset_fields = ["disciplina", "estudiante", "estado"]

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return [EsCoordinadorPermiso()]

    def get_queryset(self):
        usuario: Usuario = self.request.user  # type: ignore[assignment]
        qs = Inscripcion.objects.select_related("estudiante", "disciplina")
        if usuario.es_coordinador:
            return qs.all()
        if usuario.es_entrenador:
            perfil_ent = getattr(usuario, "perfil_entrenador", None)
            return qs.filter(
                disciplina__asignaciones_entrenador__entrenador=perfil_ent
            ).distinct()
        perfil_est = getattr(usuario, "perfil_estudiante", None)
        return qs.filter(estudiante=perfil_est)

    def perform_destroy(self, instance: Inscripcion) -> None:
        # Aplica baja logica en lugar de borrado fisico
        instance.dar_de_baja()


class SesionEntrenamientoViewSet(viewsets.ModelViewSet):
    """
    Recurso API de sesiones de entrenamiento:
    - Solo Entrenador puede crear/actualizar sesiones de sus propias disciplinas.
    - Coordinador ve todas (solo lectura).
    - Estudiante ve solo las de sus disciplinas inscritas (solo lectura).
    """

    serializer_class = SesionEntrenamientoSerializador
    filterset_fields = ["disciplina", "fecha"]

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return [EsEntrenadorPermiso()]

    def get_queryset(self):
        usuario: Usuario = self.request.user  # type: ignore[assignment]
        qs = SesionEntrenamiento.objects.select_related("disciplina", "entrenador")
        if usuario.es_coordinador:
            return qs.all()
        if usuario.es_entrenador:
            perfil_ent = getattr(usuario, "perfil_entrenador", None)
            return qs.filter(
                disciplina__asignaciones_entrenador__entrenador=perfil_ent
            ).distinct()
        perfil_est = getattr(usuario, "perfil_estudiante", None)
        return qs.filter(disciplina__inscripciones__estudiante=perfil_est).distinct()

    def perform_create(self, serializer) -> None:
        perfil_ent = getattr(self.request.user, "perfil_entrenador", None)
        disciplina: Disciplina = serializer.validated_data["disciplina"]
        if not disciplina.asignaciones_entrenador.filter(entrenador=perfil_ent).exists():
            raise DRFPermissionDenied(
                "No puede registrar sesiones en una disciplina que no tiene asignada."
            )
        serializer.save(entrenador=perfil_ent)


class AsistenciaViewSet(viewsets.ModelViewSet):
    """
    Recurso API de asistencia:
    - Solo Entrenador registra o corrige asistencia de sus propias disciplinas (dentro de 7 dias).
    - Coordinador: solo lectura global (segregacion de funciones).
    - Estudiante: solo lectura de su propia asistencia.
    """

    serializer_class = AsistenciaSerializador
    filterset_fields = ["sesion", "estudiante", "estado"]

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return [EsEntrenadorPermiso()]

    def get_queryset(self):
        usuario: Usuario = self.request.user  # type: ignore[assignment]
        qs = Asistencia.objects.select_related(
            "sesion", "sesion__disciplina", "estudiante"
        )
        if usuario.es_coordinador:
            return qs.all()
        if usuario.es_entrenador:
            perfil_ent = getattr(usuario, "perfil_entrenador", None)
            return qs.filter(
                sesion__disciplina__asignaciones_entrenador__entrenador=perfil_ent
            ).distinct()
        perfil_est = getattr(usuario, "perfil_estudiante", None)
        return qs.filter(estudiante=perfil_est)

    def perform_create(self, serializer) -> None:
        perfil_ent = getattr(self.request.user, "perfil_entrenador", None)
        sesion: SesionEntrenamiento = serializer.validated_data["sesion"]
        if not sesion.disciplina.asignaciones_entrenador.filter(
            entrenador=perfil_ent
        ).exists():
            raise DRFPermissionDenied(
                "No puede registrar asistencia en una disciplina no asignada."
            )
        if not sesion.esta_dentro_ventana_correccion():
            raise DRFPermissionDenied(
                "La sesión se encuentra fuera de la ventana de 7 días."
            )
        serializer.save(registrado_por=self.request.user)

    def perform_update(self, serializer) -> None:
        instancia: Asistencia = self.get_object()
        if not instancia.sesion.esta_dentro_ventana_correccion():
            raise DRFPermissionDenied(
                "Ha expirado el plazo de 7 días para corregir este registro de asistencia."
            )
        estado_anterior = instancia.estado
        actualizada = serializer.save(registrado_por=self.request.user)
        if estado_anterior != actualizada.estado:
            registrar_evento_auditoria(
                usuario=self.request.user,
                accion="correccion_asistencia_api",
                entidad="Asistencia",
                identificador=str(actualizada.id),
                request=self.request,
                detalle={
                    "estado_anterior": estado_anterior,
                    "estado_nuevo": actualizada.estado,
                },
            )


class EvaluacionViewSet(viewsets.ModelViewSet):
    """
    Recurso API de evaluaciones de rendimiento:
    - Solo Entrenador registra o corrige evaluaciones de sus propias disciplinas (dentro de 7 dias).
    - Coordinador: solo lectura global.
    - Estudiante: solo lectura de sus propias evaluaciones.
    """

    serializer_class = EvaluacionSerializador
    filterset_fields = ["sesion", "estudiante"]

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return [EsEntrenadorPermiso()]

    def get_queryset(self):
        usuario: Usuario = self.request.user  # type: ignore[assignment]
        qs = Evaluacion.objects.select_related(
            "sesion", "sesion__disciplina", "estudiante"
        )
        if usuario.es_coordinador:
            return qs.all()
        if usuario.es_entrenador:
            perfil_ent = getattr(usuario, "perfil_entrenador", None)
            return qs.filter(
                sesion__disciplina__asignaciones_entrenador__entrenador=perfil_ent
            ).distinct()
        perfil_est = getattr(usuario, "perfil_estudiante", None)
        return qs.filter(estudiante=perfil_est)

    def perform_create(self, serializer) -> None:
        perfil_ent = getattr(self.request.user, "perfil_entrenador", None)
        sesion: SesionEntrenamiento = serializer.validated_data["sesion"]
        if not sesion.disciplina.asignaciones_entrenador.filter(
            entrenador=perfil_ent
        ).exists():
            raise DRFPermissionDenied(
                "No puede registrar evaluaciones en una disciplina no asignada."
            )
        if not sesion.esta_dentro_ventana_correccion():
            raise DRFPermissionDenied(
                "La sesión se encuentra fuera de la ventana de 7 días."
            )
        serializer.save(registrado_por=self.request.user)

    def perform_update(self, serializer) -> None:
        instancia: Evaluacion = self.get_object()
        if not instancia.sesion.esta_dentro_ventana_correccion():
            raise DRFPermissionDenied(
                "Ha expirado el plazo de 7 días para corregir esta evaluación."
            )
        nota_anterior = str(instancia.puntaje)
        actualizada = serializer.save(registrado_por=self.request.user)
        if nota_anterior != str(actualizada.puntaje):
            registrar_evento_auditoria(
                usuario=self.request.user,
                accion="correccion_evaluacion_api",
                entidad="Evaluacion",
                identificador=str(actualizada.id),
                request=self.request,
                detalle={
                    "puntaje_anterior": nota_anterior,
                    "puntaje_nuevo": str(actualizada.puntaje),
                },
            )


class ReporteResumenAPIView(APIView):
    """Endpoint API de reportes con alcance filtrado automaticamente segun el rol."""

    permission_classes = [IsAuthenticated]

    def get(self, request) -> Response:
        usuario: Usuario = request.user
        datos = construir_datos_reporte(
            usuario_solicitante=usuario,
            disciplina_id=request.query_params.get("disciplina", ""),
            entrenador_id=request.query_params.get("entrenador", ""),
            estudiante_id=request.query_params.get("estudiante", ""),
        )
        return Response(
            {
                "rol_solicitante": usuario.rol,
                "total_asistencias": datos["total_asistencias"],
                "presentes": datos["presentes"],
                "justificados": datos["justificados"],
                "ausentes": datos["ausentes"],
                "porcentaje_asistencia": datos["porcentaje_asistencia"],
                "promedio_rendimiento": datos["promedio_rendimiento"],
                "minimo_rendimiento": datos["minimo_rendimiento"],
                "maximo_rendimiento": datos["maximo_rendimiento"],
                "tendencia_rendimiento": datos["tendencia_rendimiento"],
                "total_inscripciones_activas": datos["total_inscripciones_activas"],
                "cantidad_registros_detalle": len(datos["filas_detalle"]),
            },
            status=status.HTTP_200_OK,
        )
