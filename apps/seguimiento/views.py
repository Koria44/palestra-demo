"""
Vistas de los Modulos Entrenador y Estudiante (Seccion 4.3, 4.4, 5 y 6):
- Modulo Entrenador:
  * Ver unicamente la lista de estudiantes inscritos activos en SUS disciplinas.
  * Crear sesion de entrenamiento por disciplina y fecha (impidiendo fechas futuras y duplicadas).
  * Registrar y corregir asistencia (presente, ausente, justificado) y evaluacion (1.0 a 7.0) en lote.
  * Ventana de correccion de 7 dias para registros propios con trazabilidad en RegistroAuditoria.
- Modulo Estudiante:
  * Consultar sus disciplinas asignadas (horario, lugar, entrenador).
  * Revisar su rendimiento acumulado (promedio y grafico de evolucion temporal) y su historial de asistencia.
  * Solo lectura; nunca ve datos de otros estudiantes (proteccion contra IDOR).
"""
from datetime import date
from decimal import Decimal, InvalidOperation
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from apps.auditoria.models import registrar_evento_auditoria
from apps.cuentas.mixins import SoloEntrenadorMixin, SoloEstudianteMixin
from apps.deportes.models import Disciplina, Inscripcion, PerfilEntrenador, PerfilEstudiante
from .models import Asistencia, Evaluacion, SesionEntrenamiento


def _obtener_perfil_entrenador_o_403(request: HttpRequest) -> PerfilEntrenador:
    perfil = getattr(request.user, "perfil_entrenador", None)
    if perfil is None or not perfil.activo:
        raise PermissionDenied("No cuenta con un perfil de entrenador activo.")
    return perfil


def _verificar_disciplina_de_entrenador(
    perfil_entrenador: PerfilEntrenador, disciplina_id: str
) -> Disciplina:
    """
    Verifica a nivel de objeto que la disciplina pertenezca al entrenador autenticado.
    Si pertenece a otro entrenador, lanza PermissionDenied (403) para prevenir IDOR.
    """
    disciplina = get_object_or_404(Disciplina, pk=disciplina_id)
    asignado = disciplina.asignaciones_entrenador.filter(
        entrenador=perfil_entrenador
    ).exists()
    if not asignado:
        raise PermissionDenied(
            "No tiene permiso para acceder o registrar datos en una disciplina no asignada a su perfil."
        )
    return disciplina


# ==============================================================================
# MODULO ENTRENADOR (PASOS 3.1 A 3.3)
# ==============================================================================


class VistaMisDisciplinasEntrenador(SoloEntrenadorMixin, View):
    """Lista las disciplinas asignadas al entrenador autenticado."""

    plantilla = "seguimiento/entrenador_mis_disciplinas.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        perfil = _obtener_perfil_entrenador_o_403(request)
        disciplinas = (
            Disciplina.objects.filter(
                asignaciones_entrenador__entrenador=perfil,
                activo=True,
            )
            .annotate(
                inscritos_activos=Count(
                    "inscripciones",
                    filter=Q(
                        inscripciones__estado=Inscripcion.ESTADO_ACTIVA,
                        inscripciones__estudiante__activo=True,
                    ),
                ),
                sesiones_count=Count("sesiones", distinct=True),
            )
            .order_by("nombre")
        )
        return render(request, self.plantilla, {"disciplinas": disciplinas})


class VistaNominaDisciplinaEntrenador(SoloEntrenadorMixin, View):
    """Muestra la nomina de estudiantes inscritos exclusivamente en una disciplina del entrenador."""

    plantilla = "seguimiento/entrenador_nomina_disciplina.html"

    def get(self, request: HttpRequest, disciplina_id: str) -> HttpResponse:
        perfil = _obtener_perfil_entrenador_o_403(request)
        disciplina = _verificar_disciplina_de_entrenador(perfil, disciplina_id)
        inscripciones = (
            Inscripcion.objects.filter(
                disciplina=disciplina,
                estado=Inscripcion.ESTADO_ACTIVA,
                estudiante__activo=True,
            )
            .select_related("estudiante", "estudiante__usuario")
            .order_by("estudiante__apellidos", "estudiante__nombres")
        )

        # Calcula resumen de asistencia y promedio en esta disciplina para cada estudiante
        nomina = []
        for insc in inscripciones:
            est = insc.estudiante
            asist_qs = Asistencia.objects.filter(
                estudiante=est, sesion__disciplina=disciplina
            )
            total_ses = asist_qs.count()
            presentes = asist_qs.filter(
                estado__in=[Asistencia.ESTADO_PRESENTE, Asistencia.ESTADO_JUSTIFICADO]
            ).count()
            pct = round((presentes / total_ses) * 100.0, 1) if total_ses > 0 else 0.0
            prom = Evaluacion.objects.filter(
                estudiante=est, sesion__disciplina=disciplina
            ).aggregate(p=Avg("puntaje"))["p"]
            nomina.append(
                {
                    "inscripcion": insc,
                    "estudiante": est,
                    "total_sesiones": total_ses,
                    "porcentaje_asistencia": pct,
                    "promedio_nota": round(float(prom), 1) if prom is not None else None,
                }
            )

        return render(
            request,
            self.plantilla,
            {"disciplina": disciplina, "nomina": nomina},
        )


class VistaHistorialSesionesEntrenador(SoloEntrenadorMixin, View):
    """Lista las sesiones registradas en las disciplinas del entrenador."""

    plantilla = "seguimiento/entrenador_lista_sesiones.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        perfil = _obtener_perfil_entrenador_o_403(request)
        disciplina_filtro = request.GET.get("disciplina", "").strip()

        disciplinas_propias = Disciplina.objects.filter(
            asignaciones_entrenador__entrenador=perfil
        )
        sesiones = (
            SesionEntrenamiento.objects.filter(disciplina__in=disciplinas_propias)
            .select_related("disciplina", "entrenador")
            .annotate(
                asistencias_count=Count("asistencias", distinct=True),
                evaluaciones_count=Count("evaluaciones", distinct=True),
            )
            .order_by("-fecha", "-creado_en")
        )
        if disciplina_filtro:
            sesiones = sesiones.filter(disciplina_id=disciplina_filtro)

        return render(
            request,
            self.plantilla,
            {
                "sesiones": sesiones,
                "disciplinas_propias": disciplinas_propias,
                "disciplina_seleccionada": disciplina_filtro,
            },
        )


class VistaCrearSesionEntrenamiento(SoloEntrenadorMixin, View):
    """
    Permite al entrenador seleccionar una de sus disciplinas y una fecha (no futura ni duplicada)
    para iniciar la toma de asistencia y evaluacion en lote.
    """

    plantilla = "seguimiento/entrenador_nueva_sesion.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        perfil = _obtener_perfil_entrenador_o_403(request)
        disciplinas = Disciplina.objects.filter(
            asignaciones_entrenador__entrenador=perfil,
            activo=True,
        ).order_by("nombre")
        disciplina_preseleccionada = request.GET.get("disciplina", "")
        hoy_str = timezone.localdate().strftime("%Y-%m-%d")
        return render(
            request,
            self.plantilla,
            {
                "disciplinas": disciplinas,
                "disciplina_preseleccionada": disciplina_preseleccionada,
                "fecha_hoy": hoy_str,
            },
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        perfil = _obtener_perfil_entrenador_o_403(request)
        disciplina_id = request.POST.get("disciplina", "").strip()
        fecha_str = request.POST.get("fecha", "").strip()
        tema = request.POST.get("tema", "").strip()[:160]

        disciplinas = Disciplina.objects.filter(
            asignaciones_entrenador__entrenador=perfil,
            activo=True,
        ).order_by("nombre")
        hoy = timezone.localdate()

        if not disciplina_id or not fecha_str:
            messages.error(request, "Debe seleccionar una disciplina y una fecha válida.")
            return render(
                request,
                self.plantilla,
                {
                    "disciplinas": disciplinas,
                    "disciplina_preseleccionada": disciplina_id,
                    "fecha_hoy": hoy.strftime("%Y-%m-%d"),
                },
            )

        disciplina = _verificar_disciplina_de_entrenador(perfil, disciplina_id)

        try:
            fecha_sesion = date.fromisoformat(fecha_str)
        except ValueError:
            messages.error(request, "El formato de la fecha ingresada no es válido.")
            return render(
                request,
                self.plantilla,
                {
                    "disciplinas": disciplinas,
                    "disciplina_preseleccionada": disciplina_id,
                    "fecha_hoy": hoy.strftime("%Y-%m-%d"),
                },
            )

        if fecha_sesion > hoy:
            messages.error(
                request,
                "No se permite registrar sesiones ni tomar asistencia con fechas futuras.",
            )
            return render(
                request,
                self.plantilla,
                {
                    "disciplinas": disciplinas,
                    "disciplina_preseleccionada": disciplina_id,
                    "fecha_hoy": hoy.strftime("%Y-%m-%d"),
                },
            )

        if SesionEntrenamiento.objects.filter(
            disciplina=disciplina, fecha=fecha_sesion
        ).exists():
            messages.error(
                request,
                f"Ya existe una sesión registrada para «{disciplina.nombre}» en la fecha {fecha_sesion:%d/%m/%Y}. Puede editarla desde el historial si está dentro de los 7 días.",
            )
            return render(
                request,
                self.plantilla,
                {
                    "disciplinas": disciplinas,
                    "disciplina_preseleccionada": disciplina_id,
                    "fecha_hoy": hoy.strftime("%Y-%m-%d"),
                },
            )

        with transaction.atomic():
            sesion = SesionEntrenamiento.objects.create(
                disciplina=disciplina,
                fecha=fecha_sesion,
                entrenador=perfil,
                tema=tema or "Sesión regular de entrenamiento",
            )
            registrar_evento_auditoria(
                usuario=request.user,
                accion="creacion_sesion_entrenamiento",
                entidad="SesionEntrenamiento",
                identificador=str(sesion.id),
                request=request,
                detalle={
                    "disciplina": disciplina.nombre,
                    "fecha": str(fecha_sesion),
                },
            )

        messages.success(
            request,
            f"Sesión del {fecha_sesion:%d/%m/%Y} creada. Registre a continuación la asistencia y evaluaciones en lote.",
        )
        return redirect("seguimiento:gestionar_sesion", sesion_id=sesion.id)


class VistaGestionarSesionAsistenciaEvaluacion(SoloEntrenadorMixin, View):
    """
    Permite registrar o corregir en lote la asistencia (presente, ausente, justificado)
    y la evaluacion (escala 1.0 a 7.0 + observacion) de todos los estudiantes inscritos
    en la disciplina de la sesion.
    Imprime en RegistroAuditoria toda alta o correccion realizada dentro de la ventana de 7 dias.
    """

    plantilla = "seguimiento/entrenador_gestionar_sesion.html"

    def _obtener_sesion_autorizada(
        self, request: HttpRequest, sesion_id: str
    ) -> tuple[PerfilEntrenador, SesionEntrenamiento]:
        perfil = _obtener_perfil_entrenador_o_403(request)
        sesion = get_object_or_404(
            SesionEntrenamiento.objects.select_related("disciplina", "entrenador"),
            pk=sesion_id,
        )
        _verificar_disciplina_de_entrenador(perfil, str(sesion.disciplina_id))
        return perfil, sesion

    def _construir_filas_estudiantes(self, sesion: SesionEntrenamiento) -> list[dict]:
        inscripciones = (
            Inscripcion.objects.filter(
                disciplina=sesion.disciplina,
                estado=Inscripcion.ESTADO_ACTIVA,
                estudiante__activo=True,
            )
            .select_related("estudiante")
            .order_by("estudiante__apellidos", "estudiante__nombres")
        )
        mapa_asistencias = {
            a.estudiante_id: a
            for a in Asistencia.objects.filter(sesion=sesion)
        }
        mapa_evaluaciones = {
            e.estudiante_id: e
            for e in Evaluacion.objects.filter(sesion=sesion)
        }

        filas = []
        for insc in inscripciones:
            est = insc.estudiante
            asist = mapa_asistencias.get(est.id)
            eval_obj = mapa_evaluaciones.get(est.id)
            filas.append(
                {
                    "estudiante": est,
                    "estado_asistencia": asist.estado if asist else Asistencia.ESTADO_PRESENTE,
                    "observacion_asistencia": asist.observacion if asist else "",
                    "puntaje_evaluacion": (
                        f"{eval_obj.puntaje:.1f}" if eval_obj else ""
                    ),
                    "observacion_evaluacion": eval_obj.observacion if eval_obj else "",
                }
            )
        return filas

    def get(self, request: HttpRequest, sesion_id: str) -> HttpResponse:
        _, sesion = self._obtener_sesion_autorizada(request, sesion_id)
        filas = self._construir_filas_estudiantes(sesion)
        contexto = {
            "sesion": sesion,
            "filas": filas,
            "editable": sesion.esta_dentro_ventana_correccion(),
            "nota_minima": getattr(settings, "ESCALA_NOTAS_MINIMA", 1.0),
            "nota_maxima": getattr(settings, "ESCALA_NOTAS_MAXIMA", 7.0),
            "dias_ventana": getattr(settings, "DIAS_VENTANA_CORRECCION", 7),
        }
        return render(request, self.plantilla, contexto)

    def post(self, request: HttpRequest, sesion_id: str) -> HttpResponse:
        perfil, sesion = self._obtener_sesion_autorizada(request, sesion_id)

        if not sesion.esta_dentro_ventana_correccion():
            raise PermissionDenied(
                "Ha expirado la ventana de 7 días permitida para corregir los registros de esta sesión."
            )

        inscripciones = (
            Inscripcion.objects.filter(
                disciplina=sesion.disciplina,
                estado=Inscripcion.ESTADO_ACTIVA,
                estudiante__activo=True,
            )
            .select_related("estudiante")
            .order_by("estudiante__apellidos", "estudiante__nombres")
        )

        nota_min = Decimal(str(getattr(settings, "ESCALA_NOTAS_MINIMA", "1.0")))
        nota_max = Decimal(str(getattr(settings, "ESCALA_NOTAS_MAXIMA", "7.0")))
        errores: list[str] = []
        operaciones_lote: list[dict] = []

        for insc in inscripciones:
            est = insc.estudiante
            prefijo = str(est.id)
            estado_asist = request.POST.get(
                f"estado_{prefijo}", Asistencia.ESTADO_PRESENTE
            ).strip()
            obs_asist = request.POST.get(f"obs_asist_{prefijo}", "").strip()[:250]
            puntaje_raw = (
                request.POST.get(f"puntaje_{prefijo}", "").strip().replace(",", ".")
            )
            obs_eval = request.POST.get(f"obs_eval_{prefijo}", "").strip()[:250]

            if estado_asist not in (
                Asistencia.ESTADO_PRESENTE,
                Asistencia.ESTADO_AUSENTE,
                Asistencia.ESTADO_JUSTIFICADO,
            ):
                errores.append(
                    f"Estado de asistencia inválido para {est.nombre_completo}."
                )
                continue

            puntaje_dec: Decimal | None = None
            if puntaje_raw != "":
                try:
                    puntaje_dec = Decimal(puntaje_raw).quantize(Decimal("0.1"))
                    if puntaje_dec < nota_min or puntaje_dec > nota_max:
                        errores.append(
                            f"El puntaje de {est.nombre_completo} debe estar entre 1,0 y 7,0."
                        )
                        continue
                except (InvalidOperation, ValueError):
                    errores.append(
                        f"El puntaje ingresado para {est.nombre_completo} no es un número válido."
                    )
                    continue

            operaciones_lote.append(
                {
                    "estudiante": est,
                    "estado_asistencia": estado_asist,
                    "obs_asistencia": obs_asist,
                    "puntaje": puntaje_dec,
                    "obs_evaluacion": obs_eval,
                }
            )

        if errores:
            for err in errores:
                messages.error(request, err)
            return redirect("seguimiento:gestionar_sesion", sesion_id=sesion.id)

        altas_asistencia = 0
        correcciones_asistencia = 0
        altas_evaluacion = 0
        correcciones_evaluacion = 0

        with transaction.atomic():
            nuevo_tema = request.POST.get("tema", "").strip()[:160]
            if nuevo_tema and nuevo_tema != sesion.tema:
                sesion.tema = nuevo_tema
                sesion.save(update_fields=["tema", "actualizado_en"])

            for item in operaciones_lote:
                est: PerfilEstudiante = item["estudiante"]
                asist_existente = Asistencia.objects.filter(
                    sesion=sesion, estudiante=est
                ).first()

                if asist_existente is None:
                    Asistencia.objects.create(
                        sesion=sesion,
                        estudiante=est,
                        estado=item["estado_asistencia"],
                        observacion=item["obs_asistencia"],
                        registrado_por=request.user,
                    )
                    altas_asistencia += 1
                else:
                    if (
                        asist_existente.estado != item["estado_asistencia"]
                        or asist_existente.observacion != item["obs_asistencia"]
                    ):
                        estado_anterior = asist_existente.estado
                        asist_existente.estado = item["estado_asistencia"]
                        asist_existente.observacion = item["obs_asistencia"]
                        asist_existente.registrado_por = request.user
                        asist_existente.save()
                        correcciones_asistencia += 1
                        registrar_evento_auditoria(
                            usuario=request.user,
                            accion="correccion_asistencia",
                            entidad="Asistencia",
                            identificador=str(asist_existente.id),
                            request=request,
                            detalle={
                                "estudiante": est.nombre_completo,
                                "disciplina": sesion.disciplina.nombre,
                                "fecha_sesion": str(sesion.fecha),
                                "estado_anterior": estado_anterior,
                                "estado_nuevo": item["estado_asistencia"],
                            },
                        )

                if item["puntaje"] is not None:
                    eval_existente = Evaluacion.objects.filter(
                        sesion=sesion, estudiante=est
                    ).first()
                    if eval_existente is None:
                        Evaluacion.objects.create(
                            sesion=sesion,
                            estudiante=est,
                            puntaje=item["puntaje"],
                            observacion=item["obs_evaluacion"],
                            registrado_por=request.user,
                        )
                        altas_evaluacion += 1
                    else:
                        if (
                            eval_existente.puntaje != item["puntaje"]
                            or eval_existente.observacion != item["obs_evaluacion"]
                        ):
                            puntaje_anterior = str(eval_existente.puntaje)
                            eval_existente.puntaje = item["puntaje"]
                            eval_existente.observacion = item["obs_evaluacion"]
                            eval_existente.registrado_por = request.user
                            eval_existente.save()
                            correcciones_evaluacion += 1
                            registrar_evento_auditoria(
                                usuario=request.user,
                                accion="correccion_evaluacion",
                                entidad="Evaluacion",
                                identificador=str(eval_existente.id),
                                request=request,
                                detalle={
                                    "estudiante": est.nombre_completo,
                                    "disciplina": sesion.disciplina.nombre,
                                    "fecha_sesion": str(sesion.fecha),
                                    "puntaje_anterior": puntaje_anterior,
                                    "puntaje_nuevo": str(item["puntaje"]),
                                },
                            )

            registrar_evento_auditoria(
                usuario=request.user,
                accion="guardado_lote_sesion",
                entidad="SesionEntrenamiento",
                identificador=str(sesion.id),
                request=request,
                detalle={
                    "disciplina": sesion.disciplina.nombre,
                    "fecha": str(sesion.fecha),
                    "altas_asistencia": altas_asistencia,
                    "correcciones_asistencia": correcciones_asistencia,
                    "altas_evaluacion": altas_evaluacion,
                    "correcciones_evaluacion": correcciones_evaluacion,
                },
            )

        messages.success(
            request,
            "Los registros de asistencia y evaluación fueron guardados correctamente en lote.",
        )
        return redirect("seguimiento:gestionar_sesion", sesion_id=sesion.id)


# ==============================================================================
# MODULO ESTUDIANTE (PASOS 4.1 Y 4.2)
# ==============================================================================


class VistaMisDisciplinasEstudiante(SoloEstudianteMixin, View):
    """Muestra al estudiante sus disciplinas asignadas con horario, lugar y entrenador."""

    plantilla = "seguimiento/estudiante_mis_disciplinas.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        perfil = getattr(request.user, "perfil_estudiante", None)
        if perfil is None:
            inscripciones = Inscripcion.objects.none()
        else:
            inscripciones = (
                Inscripcion.objects.filter(estudiante=perfil)
                .select_related("disciplina")
                .prefetch_related("disciplina__entrenadores")
                .order_by("estado", "disciplina__nombre")
            )
        return render(
            request,
            self.plantilla,
            {"inscripciones": inscripciones, "perfil": perfil},
        )


class VistaMiAsistenciaYRendimientoEstudiante(SoloEstudianteMixin, View):
    """
    Muestra al estudiante su rendimiento acumulado (promedio, grafico de evolucion en el tiempo)
    y su historial detallado de asistencia por fecha. Solo lectura y aislado a su propio perfil.
    """

    plantilla = "seguimiento/estudiante_mi_asistencia_rendimiento.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        perfil = getattr(request.user, "perfil_estudiante", None)
        disciplina_filtro = request.GET.get("disciplina", "").strip()

        if perfil is None:
            asistencias = Asistencia.objects.none()
            evaluaciones = Evaluacion.objects.none()
            disciplinas_inscritas = Disciplina.objects.none()
        else:
            disciplinas_inscritas = Disciplina.objects.filter(
                inscripciones__estudiante=perfil
            ).distinct()
            asistencias = (
                Asistencia.objects.filter(estudiante=perfil)
                .select_related("sesion", "sesion__disciplina")
                .order_by("-sesion__fecha")
            )
            evaluaciones = (
                Evaluacion.objects.filter(estudiante=perfil)
                .select_related("sesion", "sesion__disciplina")
                .order_by("sesion__fecha")
            )
            if disciplina_filtro:
                asistencias = asistencias.filter(
                    sesion__disciplina_id=disciplina_filtro
                )
                evaluaciones = evaluaciones.filter(
                    sesion__disciplina_id=disciplina_filtro
                )

        total_asist = asistencias.count()
        presentes = asistencias.filter(estado=Asistencia.ESTADO_PRESENTE).count()
        justificados = asistencias.filter(estado=Asistencia.ESTADO_JUSTIFICADO).count()
        ausentes = asistencias.filter(estado=Asistencia.ESTADO_AUSENTE).count()
        porcentaje_asistencia = (
            round(((presentes + justificados) / total_asist) * 100.0, 1)
            if total_asist > 0
            else 0.0
        )

        promedio_nota = evaluaciones.aggregate(p=Avg("puntaje"))["p"]
        puntos_grafico = ";".join(
            f"{ev.sesion.fecha:%d/%m}|{ev.puntaje:.1f}" for ev in evaluaciones
        )

        contexto = {
            "perfil": perfil,
            "disciplinas_inscritas": disciplinas_inscritas,
            "disciplina_seleccionada": disciplina_filtro,
            "asistencias": asistencias,
            "evaluaciones": list(reversed(list(evaluaciones))),
            "total_sesiones": total_asist,
            "presentes": presentes,
            "justificados": justificados,
            "ausentes": ausentes,
            "porcentaje_asistencia": porcentaje_asistencia,
            "promedio_nota": (
                round(float(promedio_nota), 1) if promedio_nota is not None else None
            ),
            "puntos_grafico": puntos_grafico,
        }
        return render(request, self.plantilla, contexto)
