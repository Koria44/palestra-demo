"""
Vistas de autenticacion, paneles diferenciados por rol, activacion de cuenta por
enlace de un solo uso, cambio obligatorio de contrasena, recuperacion y aviso de privacidad.
"""
from typing import Any
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.contrib.sessions.models import Session
from django.db.models import Avg, Count, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_POST
from apps.auditoria.models import registrar_evento_auditoria
from apps.deportes.models import (
    Disciplina,
    Inscripcion,
    PerfilEntrenador,
    PerfilEstudiante,
)
from apps.seguimiento.models import Asistencia, Evaluacion, SesionEntrenamiento
from .formularios import (
    FormularioCambioContrasena,
    FormularioDefinirContrasena,
    FormularioInicioSesion,
    FormularioRecuperarContrasena,
)
from .mixins import SoloCoordinadorMixin, SoloEntrenadorMixin, SoloEstudianteMixin
from .models import Usuario


def invalidar_otras_sesiones_usuario(usuario: Usuario, sesion_actual_key: str | None) -> int:
    """
    Invalida todas las sesiones activas del usuario excepto la sesion actual
    al cambiar o restablecer la contrasena (Seccion 6.1.A).
    """
    ahora = timezone.now()
    sesiones_vigentes = Session.objects.filter(expire_date__gt=ahora)
    eliminadas = 0
    uid_str = str(usuario.pk)
    for sesion in sesiones_vigentes:
        if sesion_actual_key and sesion.session_key == sesion_actual_key:
            continue
        datos = sesion.get_decoded()
        if str(datos.get("_auth_user_id")) == uid_str:
            sesion.delete()
            eliminadas += 1
    return eliminadas


@method_decorator(
    [
        sensitive_post_parameters("contrasena", "password"),
        csrf_protect,
        never_cache,
    ],
    name="dispatch",
)
class VistaIniciarSesion(View):
    """Pantalla de inicio de sesion institucional para Coordinador, Entrenador y Estudiante."""

    plantilla = "cuentas/iniciar_sesion.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_authenticated:
            return redirect("cuentas:panel_inicio")
        formulario = FormularioInicioSesion(request=request)
        return render(request, self.plantilla, {"formulario": formulario})

    def post(self, request: HttpRequest) -> HttpResponse:
        formulario = FormularioInicioSesion(request=request, data=request.POST)
        if formulario.is_valid():
            usuario = formulario.obtener_usuario()
            if usuario is not None:
                auth_login(request, usuario)
                # Rotacion de clave de sesion explicita tras autenticar
                request.session.cycle_key()
                if usuario.debe_cambiar_contrasena:
                    messages.warning(
                        request,
                        "Por seguridad, debe actualizar su contraseña temporal antes de continuar.",
                    )
                    return redirect("cuentas:cambiar_contrasena")
                return redirect("cuentas:panel_inicio")
        return render(
            request,
            self.plantilla,
            {"formulario": formulario},
            status=200,
        )


@require_POST
@csrf_protect
def vista_cerrar_sesion(request: HttpRequest) -> HttpResponse:
    """Cierra la sesion activa unicamente mediante peticion POST protegida por CSRF."""
    auth_logout(request)
    messages.info(request, "Ha cerrado su sesión de forma segura.")
    return redirect("cuentas:iniciar_sesion")


@login_required
def vista_panel_inicio(request: HttpRequest) -> HttpResponse:
    """Redirige automaticamente al panel diferenciado segun el rol del usuario."""
    usuario: Usuario = request.user  # type: ignore[assignment]
    if usuario.es_coordinador:
        return redirect("cuentas:panel_coordinador")
    if usuario.es_entrenador:
        return redirect("cuentas:panel_entrenador")
    return redirect("cuentas:panel_estudiante")


class VistaPanelCoordinador(SoloCoordinadorMixin, View):
    """Panel de inicio para el Coordinador Deportivo con metricas globales e indicadores."""

    plantilla = "cuentas/panel_coordinador.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        total_estudiantes = PerfilEstudiante.objects.filter(activo=True).count()
        total_disciplinas = Disciplina.objects.filter(activo=True).count()
        total_entrenadores = PerfilEntrenador.objects.filter(activo=True).count()
        total_inscripciones = Inscripcion.objects.filter(
            estado=Inscripcion.ESTADO_ACTIVA,
            estudiante__activo=True,
            disciplina__activo=True,
        ).count()

        disciplinas = (
            Disciplina.objects.filter(activo=True)
            .annotate(
                inscritos_activos=Count(
                    "inscripciones",
                    filter=Q(
                        inscripciones__estado=Inscripcion.ESTADO_ACTIVA,
                        inscripciones__estudiante__activo=True,
                    ),
                )
            )
            .order_by("nombre")
        )

        total_asistencias = Asistencia.objects.count()
        presentes_o_justificados = Asistencia.objects.filter(
            estado__in=[Asistencia.ESTADO_PRESENTE, Asistencia.ESTADO_JUSTIFICADO]
        ).count()
        asistencia_promedio_global = (
            round((presentes_o_justificados / total_asistencias) * 100.0, 1)
            if total_asistencias > 0
            else 0.0
        )

        promedio_rendimiento_global = Evaluacion.objects.aggregate(
            promedio=Avg("puntaje")
        )["promedio"]

        contexto = {
            "total_estudiantes": total_estudiantes,
            "total_disciplinas": total_disciplinas,
            "total_entrenadores": total_entrenadores,
            "total_inscripciones": total_inscripciones,
            "disciplinas_ocupacion": disciplinas,
            "asistencia_promedio_global": asistencia_promedio_global,
            "promedio_rendimiento_global": (
                round(float(promedio_rendimiento_global), 1)
                if promedio_rendimiento_global is not None
                else None
            ),
        }
        return render(request, self.plantilla, contexto)


class VistaPanelEntrenador(SoloEntrenadorMixin, View):
    """Panel de inicio para el Entrenador con sus disciplinas y sesiones."""

    plantilla = "cuentas/panel_entrenador.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        perfil = getattr(request.user, "perfil_entrenador", None)
        if perfil is None:
            disciplinas = Disciplina.objects.none()
            ultimas_sesiones = SesionEntrenamiento.objects.none()
            sesiones_sin_asistencia = SesionEntrenamiento.objects.none()
        else:
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
                    )
                )
                .distinct()
            )
            ultimas_sesiones = (
                SesionEntrenamiento.objects.filter(disciplina__in=disciplinas)
                .select_related("disciplina")
                .annotate(total_asistencias=Count("asistencias"))
                .order_by("-fecha")[:8]
            )
            sesiones_sin_asistencia = (
                SesionEntrenamiento.objects.filter(disciplina__in=disciplinas)
                .annotate(total_asistencias=Count("asistencias"))
                .filter(total_asistencias=0)
            )

        contexto = {
            "perfil_entrenador": perfil,
            "disciplinas_asignadas": disciplinas,
            "ultimas_sesiones": ultimas_sesiones,
            "sesiones_pendientes_count": sesiones_sin_asistencia.count(),
        }
        return render(request, self.plantilla, contexto)


class VistaPanelEstudiante(SoloEstudianteMixin, View):
    """Panel de inicio para el Estudiante con su resumen personal de asistencia y notas."""

    plantilla = "cuentas/panel_estudiante.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        perfil = getattr(request.user, "perfil_estudiante", None)
        if perfil is None:
            inscripciones = Inscripcion.objects.none()
            asistencias = Asistencia.objects.none()
            evaluaciones = Evaluacion.objects.none()
        else:
            inscripciones = (
                Inscripcion.objects.filter(
                    estudiante=perfil,
                    estado=Inscripcion.ESTADO_ACTIVA,
                    disciplina__activo=True,
                )
                .select_related("disciplina")
                .prefetch_related("disciplina__entrenadores")
            )
            asistencias = Asistencia.objects.filter(estudiante=perfil).select_related(
                "sesion", "sesion__disciplina"
            )
            evaluaciones = (
                Evaluacion.objects.filter(estudiante=perfil)
                .select_related("sesion", "sesion__disciplina")
                .order_by("-sesion__fecha")
            )

        total_asist = asistencias.count()
        cumplidas = asistencias.filter(
            estado__in=[Asistencia.ESTADO_PRESENTE, Asistencia.ESTADO_JUSTIFICADO]
        ).count()
        porcentaje_asistencia = (
            round((cumplidas / total_asist) * 100.0, 1) if total_asist > 0 else 0.0
        )
        promedio_notas = evaluaciones.aggregate(prom=Avg("puntaje"))["prom"]

        contexto = {
            "perfil_estudiante": perfil,
            "inscripciones_activas": inscripciones,
            "porcentaje_asistencia": porcentaje_asistencia,
            "total_sesiones_registradas": total_asist,
            "promedio_rendimiento": (
                round(float(promedio_notas), 1) if promedio_notas is not None else None
            ),
            "ultimas_evaluaciones": evaluaciones[:6],
        }
        return render(request, self.plantilla, contexto)


@method_decorator(
    [
        sensitive_post_parameters("old_password", "new_password1", "new_password2"),
        csrf_protect,
        never_cache,
        login_required,
    ],
    name="dispatch",
)
class VistaCambiarContrasena(View):
    """Permite al usuario cambiar su contrasena e invalida todas sus otras sesiones."""

    plantilla = "cuentas/cambiar_contrasena.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        formulario = FormularioCambioContrasena(user=request.user)
        return render(request, self.plantilla, {"formulario": formulario})

    def post(self, request: HttpRequest) -> HttpResponse:
        formulario = FormularioCambioContrasena(user=request.user, data=request.POST)
        if formulario.is_valid():
            usuario: Usuario = formulario.save(commit=False)
            usuario.debe_cambiar_contrasena = False
            usuario.hash_token_activacion = ""
            usuario.save()
            update_session_auth_hash(request, usuario)
            sesiones_cerradas = invalidar_otras_sesiones_usuario(
                usuario, request.session.session_key
            )
            registrar_evento_auditoria(
                usuario=usuario,
                accion="cambio_contrasena",
                entidad="Usuario",
                identificador=str(usuario.id),
                request=request,
                detalle={"sesiones_remotas_invalidadas": sesiones_cerradas},
            )
            messages.success(
                request,
                "Su contraseña ha sido actualizada correctamente con hash Argon2id.",
            )
            return redirect("cuentas:panel_inicio")
        return render(request, self.plantilla, {"formulario": formulario})


@method_decorator(
    [
        sensitive_post_parameters("new_password1", "new_password2"),
        csrf_protect,
        never_cache,
    ],
    name="dispatch",
)
class VistaActivarCuenta(View):
    """
    Permite a un usuario nuevo activar su cuenta y crear su propia contrasena
    mediante un enlace firmado de un solo uso y con expiracion (Seccion 6.1.B).
    """

    plantilla = "cuentas/activar_cuenta.html"

    def get(self, request: HttpRequest, token: str) -> HttpResponse:
        usuario = Usuario.validar_token_activacion(token)
        if usuario is None:
            return render(
                request,
                self.plantilla,
                {"enlace_invalido": True},
                status=400,
            )
        formulario = FormularioDefinirContrasena(user=usuario)
        return render(
            request,
            self.plantilla,
            {
                "formulario": formulario,
                "usuario_objetivo": usuario,
                "enlace_invalido": False,
            },
        )

    def post(self, request: HttpRequest, token: str) -> HttpResponse:
        usuario = Usuario.validar_token_activacion(token)
        if usuario is None:
            return render(
                request,
                self.plantilla,
                {"enlace_invalido": True},
                status=400,
            )
        formulario = FormularioDefinirContrasena(user=usuario, data=request.POST)
        if formulario.is_valid():
            formulario.save()
            usuario.consumir_token_activacion()
            invalidar_otras_sesiones_usuario(usuario, None)
            registrar_evento_auditoria(
                usuario=usuario,
                accion="activacion_cuenta_exitosa",
                entidad="Usuario",
                identificador=str(usuario.id),
                request=request,
                detalle={"correo": usuario.email},
            )
            messages.success(
                request,
                "Su cuenta ha sido activada exitosamente. Ahora puede iniciar sesión.",
            )
            return redirect("cuentas:iniciar_sesion")
        return render(
            request,
            self.plantilla,
            {
                "formulario": formulario,
                "usuario_objetivo": usuario,
                "enlace_invalido": False,
            },
        )


class VistaRecuperarContrasena(PasswordResetView):
    """Solicita enlace de recuperacion de un solo uso sin revelar si el correo existe."""

    template_name = "cuentas/recuperar_contrasena.html"
    email_template_name = "cuentas/correo_recuperar_contrasena.txt"
    subject_template_name = "cuentas/asunto_recuperar_contrasena.txt"
    form_class = FormularioRecuperarContrasena
    success_url = reverse_lazy("cuentas:recuperar_contrasena_enviado")


class VistaRecuperarContrasenaEnviado(PasswordResetDoneView):
    template_name = "cuentas/recuperar_contrasena_enviado.html"


@method_decorator(
    [sensitive_post_parameters("new_password1", "new_password2"), never_cache],
    name="dispatch",
)
class VistaRecuperarContrasenaConfirmar(PasswordResetConfirmView):
    template_name = "cuentas/recuperar_contrasena_confirmar.html"
    form_class = FormularioDefinirContrasena
    success_url = reverse_lazy("cuentas:recuperar_contrasena_completado")

    def form_valid(self, form: Any) -> HttpResponse:
        respuesta = super().form_valid(form)
        usuario: Usuario = self.user  # type: ignore[assignment]
        usuario.debe_cambiar_contrasena = False
        usuario.hash_token_activacion = ""
        usuario.save(
            update_fields=[
                "debe_cambiar_contrasena",
                "hash_token_activacion",
                "actualizado_en",
            ]
        )
        invalidar_otras_sesiones_usuario(usuario, None)
        registrar_evento_auditoria(
            usuario=usuario,
            accion="restablecimiento_contrasena",
            entidad="Usuario",
            identificador=str(usuario.id),
            request=self.request,
            detalle={"correo": usuario.email},
        )
        return respuesta


class VistaRecuperarContrasenaCompletado(PasswordResetCompleteView):
    template_name = "cuentas/recuperar_contrasena_completado.html"


def vista_aviso_privacidad(request: HttpRequest) -> HttpResponse:
    """Pagina institucional de aviso de privacidad y proteccion de datos personales."""
    return render(request, "cuentas/aviso_privacidad.html")


def error_403(request: HttpRequest, exception: Exception | None = None) -> HttpResponse:
    return render(request, "errores/403.html", status=403)


def error_404(request: HttpRequest, exception: Exception | None = None) -> HttpResponse:
    return render(request, "errores/404.html", status=404)


def error_500(request: HttpRequest) -> HttpResponse:
    return render(request, "errores/500.html", status=500)
