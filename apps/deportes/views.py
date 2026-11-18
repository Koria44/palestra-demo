"""
Vistas del Modulo Coordinador Deportivo (Seccion 4.2, 5, 6.1.B y 7):
- CRUD de Disciplina con baja logica
- CRUD de PerfilEntrenador con asignacion multiple a disciplinas y creacion segura de cuenta
- CRUD de PerfilEstudiante con RUT/telefono cifrados y creacion segura de cuenta
- Gestion de Inscripcion en transaccion atomica (select_for_update) y baja logica
"""
import secrets
import string
from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from apps.auditoria.models import registrar_evento_auditoria
from apps.cuentas.campos import calcular_indice_ciego_rut, normalizar_rut
from apps.cuentas.mixins import SoloCoordinadorMixin, rol_requerido
from apps.cuentas.models import Usuario
from .formularios import (
    FormularioDisciplina,
    FormularioEntrenador,
    FormularioEstudiante,
    FormularioInscripcion,
)
from .models import (
    Disciplina,
    EntrenadorDisciplina,
    Inscripcion,
    PerfilEntrenador,
    PerfilEstudiante,
)


def _generar_contrasena_temporal_segura() -> str:
    """
    Genera una contrasena temporal criptograficamente aleatoria de 16 caracteres
    con el modulo secrets (Seccion 6.1.B), garantizando mayusculas, minusculas,
    digitos y simbolos.
    """
    alfabeto = string.ascii_letters + string.digits + "!@#$%&*"
    while True:
        candidata = "".join(secrets.choice(alfabeto) for _ in range(16))
        if (
            any(c.isupper() for c in candidata)
            and any(c.islower() for c in candidata)
            and any(c.isdigit() for c in candidata)
            and any(c in "!@#$%&*" for c in candidata)
        ):
            return candidata


def _configurar_acceso_nueva_cuenta(
    request: HttpRequest,
    usuario: Usuario,
    modo: str,
) -> tuple[str | None, str | None]:
    """
    Configura el acceso de una nueva cuenta creada por el Coordinador (Seccion 6.1.B):
    - Si modo == 'contrasena_temporal': genera clave aleatoria de 16 caracteres con secrets,
      guarda solo su hash Argon2id, marca debe_cambiar_contrasena=True y la retorna para
      mostrarla una unica vez en pantalla (jamas en logs ni en auditoria).
    - Por defecto ('enlace_activacion'): deja la contrasena inutilizable, genera un token
      firmado de un solo uso y envia el enlace de activacion por correo.
    """
    if modo == FormularioEntrenador.MODE_TEMPORAL:
        clave_temporal = _generar_contrasena_temporal_segura()
        usuario.set_password(clave_temporal)
        usuario.debe_cambiar_contrasena = True
        usuario.hash_token_activacion = ""
        usuario.save()
        return clave_temporal, None

    usuario.set_unusable_password()
    usuario.debe_cambiar_contrasena = False
    usuario.save()
    token = usuario.generar_token_activacion()
    ruta_activacion = reverse("cuentas:activar_cuenta", kwargs={"token": token})
    enlace_absoluto = request.build_absolute_uri(ruta_activacion)
    send_mail(
        subject="PALESTRA — Active su cuenta institucional",
        message=(
            f"Estimado(a) {usuario.nombre_completo},\n\n"
            f"La Coordinación Deportiva ha habilitado su cuenta en PALESTRA ({usuario.get_rol_display()}).\n"
            f"Para activar su cuenta y crear su contraseña personal, abra el siguiente enlace de un solo uso:\n"
            f"{enlace_absoluto}\n\n"
            f"Atentamente,\nCoordinación Deportiva - PALESTRA"
        ),
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-responder@palestra.cl"),
        recipient_list=[usuario.email],
        fail_silently=True,
    )
    return None, ruta_activacion


# ==============================================================================
# 1. CRUD DE DISCIPLINAS DEPORTIVAS
# ==============================================================================


class VistaListaDisciplinas(SoloCoordinadorMixin, View):
    plantilla = "deportes/lista_disciplinas.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        busqueda = request.GET.get("q", "").strip()
        estado = request.GET.get("estado", "").strip()

        disciplinas = (
            Disciplina.objects.annotate(
                inscritos_activos=Count(
                    "inscripciones",
                    filter=Q(
                        inscripciones__estado=Inscripcion.ESTADO_ACTIVA,
                        inscripciones__estudiante__activo=True,
                    ),
                )
            )
            .prefetch_related("entrenadores")
            .order_by("nombre")
        )
        if busqueda:
            disciplinas = disciplinas.filter(
                Q(nombre__icontains=busqueda) | Q(lugar__icontains=busqueda)
            )
        if estado == "activa":
            disciplinas = disciplinas.filter(activo=True)
        elif estado == "inactiva":
            disciplinas = disciplinas.filter(activo=False)

        paginador = Paginator(disciplinas, 15)
        pagina_obj = paginador.get_page(request.GET.get("pagina"))

        return render(
            request,
            self.plantilla,
            {
                "pagina_obj": pagina_obj,
                "busqueda": busqueda,
                "estado_filtro": estado,
            },
        )


class VistaCrearDisciplina(SoloCoordinadorMixin, View):
    plantilla = "deportes/formulario_disciplina.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        formulario = FormularioDisciplina()
        return render(
            request,
            self.plantilla,
            {"formulario": formulario, "modo_edicion": False},
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        formulario = FormularioDisciplina(request.POST)
        if formulario.is_valid():
            with transaction.atomic():
                disciplina = formulario.save()
                registrar_evento_auditoria(
                    usuario=request.user,
                    accion="alta_disciplina",
                    entidad="Disciplina",
                    identificador=str(disciplina.id),
                    request=request,
                    detalle={
                        "nombre": disciplina.nombre,
                        "cupo_maximo": disciplina.cupo_maximo,
                    },
                )
            messages.success(
                request,
                f"La disciplina «{disciplina.nombre}» fue creada exitosamente.",
            )
            return redirect("deportes:lista_disciplinas")
        return render(
            request,
            self.plantilla,
            {"formulario": formulario, "modo_edicion": False},
        )


class VistaEditarDisciplina(SoloCoordinadorMixin, View):
    plantilla = "deportes/formulario_disciplina.html"

    def get(self, request: HttpRequest, pk: str) -> HttpResponse:
        disciplina = get_object_or_404(Disciplina, pk=pk)
        formulario = FormularioDisciplina(instance=disciplina)
        return render(
            request,
            self.plantilla,
            {
                "formulario": formulario,
                "disciplina": disciplina,
                "modo_edicion": True,
            },
        )

    def post(self, request: HttpRequest, pk: str) -> HttpResponse:
        disciplina = get_object_or_404(Disciplina, pk=pk)
        formulario = FormularioDisciplina(request.POST, instance=disciplina)
        if formulario.is_valid():
            with transaction.atomic():
                disciplina = formulario.save()
                registrar_evento_auditoria(
                    usuario=request.user,
                    accion="edicion_disciplina",
                    entidad="Disciplina",
                    identificador=str(disciplina.id),
                    request=request,
                    detalle={
                        "nombre": disciplina.nombre,
                        "cupo_maximo": disciplina.cupo_maximo,
                        "activo": disciplina.activo,
                    },
                )
            messages.success(
                request,
                f"La disciplina «{disciplina.nombre}» fue actualizada correctamente.",
            )
            return redirect("deportes:lista_disciplinas")
        return render(
            request,
            self.plantilla,
            {
                "formulario": formulario,
                "disciplina": disciplina,
                "modo_edicion": True,
            },
        )


@require_POST
@csrf_protect
@rol_requerido(Usuario.ROL_COORDINADOR)
def vista_cambiar_estado_disciplina(request: HttpRequest, pk: str) -> HttpResponse:
    """Baja logica o reactivacion de una disciplina deportiva."""
    disciplina = get_object_or_404(Disciplina, pk=pk)
    with transaction.atomic():
        disciplina.activo = not disciplina.activo
        disciplina.save(update_fields=["activo", "actualizado_en"])
        accion = "reactivacion_disciplina" if disciplina.activo else "baja_logica_disciplina"
        registrar_evento_auditoria(
            usuario=request.user,
            accion=accion,
            entidad="Disciplina",
            identificador=str(disciplina.id),
            request=request,
            detalle={"nombre": disciplina.nombre, "activo": disciplina.activo},
        )
    estado_txt = "reactivada" if disciplina.activo else "desactivada (baja lógica)"
    messages.info(request, f"La disciplina «{disciplina.nombre}» fue {estado_txt}.")
    return redirect("deportes:lista_disciplinas")


# ==============================================================================
# 2. CRUD DE ENTRENADORES Y ASIGNACION A DISCIPLINAS
# ==============================================================================


class VistaListaEntrenadores(SoloCoordinadorMixin, View):
    plantilla = "deportes/lista_entrenadores.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        busqueda = request.GET.get("q", "").strip()
        entrenadores = (
            PerfilEntrenador.objects.select_related("usuario")
            .prefetch_related("disciplinas")
            .order_by("apellidos", "nombres")
        )
        if busqueda:
            indice_rut = calcular_indice_ciego_rut(normalizar_rut(busqueda))
            entrenadores = entrenadores.filter(
                Q(nombres__icontains=busqueda)
                | Q(apellidos__icontains=busqueda)
                | Q(especialidad__icontains=busqueda)
                | Q(usuario__email__icontains=busqueda)
                | Q(rut_indice_ciego=indice_rut)
            )

        paginador = Paginator(entrenadores, 15)
        pagina_obj = paginador.get_page(request.GET.get("pagina"))
        credencial_unica_vez = request.session.pop("credencial_unica_vez", None)

        return render(
            request,
            self.plantilla,
            {
                "pagina_obj": pagina_obj,
                "busqueda": busqueda,
                "credencial_unica_vez": credencial_unica_vez,
            },
        )


class VistaCrearEntrenador(SoloCoordinadorMixin, View):
    plantilla = "deportes/formulario_entrenador.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        formulario = FormularioEntrenador()
        return render(
            request,
            self.plantilla,
            {"formulario": formulario, "modo_edicion": False},
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        formulario = FormularioEntrenador(request.POST)
        if formulario.is_valid():
            with transaction.atomic():
                correo = formulario.cleaned_data["correo"]
                nombres = formulario.cleaned_data["nombres"]
                apellidos = formulario.cleaned_data["apellidos"]
                activo = formulario.cleaned_data["activo"]
                modo_cuenta = (
                    formulario.cleaned_data.get("modo_creacion_cuenta")
                    or FormularioEntrenador.MODE_ENLACE
                )

                base_user = correo.split("@")[0][:30]
                username_unico = f"{base_user}_{secrets.token_hex(3)}"
                usuario = Usuario(
                    username=username_unico,
                    email=correo,
                    first_name=nombres,
                    last_name=apellidos,
                    rol=Usuario.ROL_ENTRENADOR,
                    activo=activo,
                )
                clave_temporal, ruta_activacion = _configurar_acceso_nueva_cuenta(
                    request, usuario, modo_cuenta
                )

                perfil: PerfilEntrenador = formulario.save(commit=False)
                perfil.usuario = usuario
                perfil.save()

                disciplinas_sel = formulario.cleaned_data.get("disciplinas_asignadas", [])
                for disc in disciplinas_sel:
                    EntrenadorDisciplina.objects.get_or_create(
                        entrenador=perfil, disciplina=disc
                    )

                registrar_evento_auditoria(
                    usuario=request.user,
                    accion="alta_entrenador",
                    entidad="PerfilEntrenador",
                    identificador=str(perfil.id),
                    request=request,
                    detalle={
                        "correo": correo,
                        "especialidad": perfil.especialidad,
                        "modo_habilitacion": modo_cuenta,
                        "disciplinas_count": len(disciplinas_sel),
                    },
                )

                if clave_temporal:
                    request.session["credencial_unica_vez"] = {
                        "nombre": perfil.nombre_completo,
                        "correo": correo,
                        "tipo": "temporal",
                        "valor": clave_temporal,
                    }
                elif ruta_activacion:
                    request.session["credencial_unica_vez"] = {
                        "nombre": perfil.nombre_completo,
                        "correo": correo,
                        "tipo": "enlace",
                        "valor": ruta_activacion,
                    }

            messages.success(
                request,
                f"El entrenador «{perfil.nombre_completo}» fue registrado exitosamente.",
            )
            return redirect("deportes:lista_entrenadores")
        return render(
            request,
            self.plantilla,
            {"formulario": formulario, "modo_edicion": False},
        )


class VistaEditarEntrenador(SoloCoordinadorMixin, View):
    plantilla = "deportes/formulario_entrenador.html"

    def get(self, request: HttpRequest, pk: str) -> HttpResponse:
        perfil = get_object_or_404(
            PerfilEntrenador.objects.select_related("usuario"), pk=pk
        )
        formulario = FormularioEntrenador(instance=perfil)
        return render(
            request,
            self.plantilla,
            {"formulario": formulario, "entrenador": perfil, "modo_edicion": True},
        )

    def post(self, request: HttpRequest, pk: str) -> HttpResponse:
        perfil = get_object_or_404(
            PerfilEntrenador.objects.select_related("usuario"), pk=pk
        )
        formulario = FormularioEntrenador(request.POST, instance=perfil)
        if formulario.is_valid():
            with transaction.atomic():
                perfil = formulario.save()
                usuario = perfil.usuario
                usuario.email = formulario.cleaned_data["correo"]
                usuario.first_name = perfil.nombres
                usuario.last_name = perfil.apellidos
                usuario.activo = perfil.activo
                usuario.save()

                disciplinas_nuevas = set(
                    formulario.cleaned_data.get("disciplinas_asignadas", [])
                )
                EntrenadorDisciplina.objects.filter(entrenador=perfil).exclude(
                    disciplina__in=disciplinas_nuevas
                ).delete()
                for disc in disciplinas_nuevas:
                    EntrenadorDisciplina.objects.get_or_create(
                        entrenador=perfil, disciplina=disc
                    )

                registrar_evento_auditoria(
                    usuario=request.user,
                    accion="edicion_entrenador",
                    entidad="PerfilEntrenador",
                    identificador=str(perfil.id),
                    request=request,
                    detalle={
                        "correo": usuario.email,
                        "activo": perfil.activo,
                        "disciplinas_count": len(disciplinas_nuevas),
                    },
                )
            messages.success(
                request,
                f"Los datos del entrenador «{perfil.nombre_completo}» fueron actualizados.",
            )
            return redirect("deportes:lista_entrenadores")
        return render(
            request,
            self.plantilla,
            {"formulario": formulario, "entrenador": perfil, "modo_edicion": True},
        )


@require_POST
@csrf_protect
@rol_requerido(Usuario.ROL_COORDINADOR)
def vista_cambiar_estado_entrenador(request: HttpRequest, pk: str) -> HttpResponse:
    """Baja logica o reactivacion de un entrenador y su cuenta."""
    perfil = get_object_or_404(
        PerfilEntrenador.objects.select_related("usuario"), pk=pk
    )
    with transaction.atomic():
        nuevo_estado = not perfil.activo
        perfil.activo = nuevo_estado
        perfil.save(update_fields=["activo", "actualizado_en"])
        perfil.usuario.activo = nuevo_estado
        perfil.usuario.save(update_fields=["activo", "is_active", "actualizado_en"])
        registrar_evento_auditoria(
            usuario=request.user,
            accion="reactivacion_entrenador" if nuevo_estado else "baja_logica_entrenador",
            entidad="PerfilEntrenador",
            identificador=str(perfil.id),
            request=request,
            detalle={"correo": perfil.usuario.email, "activo": nuevo_estado},
        )
    estado_txt = "reactivado" if perfil.activo else "desactivado (baja lógica)"
    messages.info(request, f"El entrenador «{perfil.nombre_completo}» fue {estado_txt}.")
    return redirect("deportes:lista_entrenadores")


# ==============================================================================
# 3. CRUD DE ESTUDIANTES
# ==============================================================================


class VistaListaEstudiantes(SoloCoordinadorMixin, View):
    plantilla = "deportes/lista_estudiantes.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        busqueda = request.GET.get("q", "").strip()
        estado = request.GET.get("estado", "").strip()

        estudiantes = (
            PerfilEstudiante.objects.select_related("usuario")
            .annotate(
                disciplinas_activas_count=Count(
                    "inscripciones",
                    filter=Q(inscripciones__estado=Inscripcion.ESTADO_ACTIVA),
                )
            )
            .order_by("apellidos", "nombres")
        )
        if busqueda:
            indice_rut = calcular_indice_ciego_rut(normalizar_rut(busqueda))
            estudiantes = estudiantes.filter(
                Q(nombres__icontains=busqueda)
                | Q(apellidos__icontains=busqueda)
                | Q(curso_o_carrera__icontains=busqueda)
                | Q(usuario__email__icontains=busqueda)
                | Q(rut_indice_ciego=indice_rut)
            )
        if estado == "activo":
            estudiantes = estudiantes.filter(activo=True)
        elif estado == "inactivo":
            estudiantes = estudiantes.filter(activo=False)

        paginador = Paginator(estudiantes, 15)
        pagina_obj = paginador.get_page(request.GET.get("pagina"))
        credencial_unica_vez = request.session.pop("credencial_unica_vez", None)

        return render(
            request,
            self.plantilla,
            {
                "pagina_obj": pagina_obj,
                "busqueda": busqueda,
                "estado_filtro": estado,
                "credencial_unica_vez": credencial_unica_vez,
            },
        )


class VistaCrearEstudiante(SoloCoordinadorMixin, View):
    plantilla = "deportes/formulario_estudiante.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        formulario = FormularioEstudiante()
        return render(
            request,
            self.plantilla,
            {"formulario": formulario, "modo_edicion": False},
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        formulario = FormularioEstudiante(request.POST)
        if formulario.is_valid():
            with transaction.atomic():
                correo = formulario.cleaned_data["correo"]
                nombres = formulario.cleaned_data["nombres"]
                apellidos = formulario.cleaned_data["apellidos"]
                activo = formulario.cleaned_data["activo"]
                modo_cuenta = (
                    formulario.cleaned_data.get("modo_creacion_cuenta")
                    or FormularioEstudiante.MODE_ENLACE
                )

                base_user = correo.split("@")[0][:30]
                username_unico = f"{base_user}_{secrets.token_hex(3)}"
                usuario = Usuario(
                    username=username_unico,
                    email=correo,
                    first_name=nombres,
                    last_name=apellidos,
                    rol=Usuario.ROL_ESTUDIANTE,
                    activo=activo,
                )
                clave_temporal, ruta_activacion = _configurar_acceso_nueva_cuenta(
                    request, usuario, modo_cuenta
                )

                perfil: PerfilEstudiante = formulario.save(commit=False)
                perfil.usuario = usuario
                perfil.save()

                registrar_evento_auditoria(
                    usuario=request.user,
                    accion="alta_estudiante",
                    entidad="PerfilEstudiante",
                    identificador=str(perfil.id),
                    request=request,
                    detalle={
                        "correo": correo,
                        "curso_o_carrera": perfil.curso_o_carrera,
                        "modo_habilitacion": modo_cuenta,
                    },
                )

                if clave_temporal:
                    request.session["credencial_unica_vez"] = {
                        "nombre": perfil.nombre_completo,
                        "correo": correo,
                        "tipo": "temporal",
                        "valor": clave_temporal,
                    }
                elif ruta_activacion:
                    request.session["credencial_unica_vez"] = {
                        "nombre": perfil.nombre_completo,
                        "correo": correo,
                        "tipo": "enlace",
                        "valor": ruta_activacion,
                    }

            messages.success(
                request,
                f"El estudiante «{perfil.nombre_completo}» fue registrado exitosamente con RUT cifrado.",
            )
            return redirect("deportes:lista_estudiantes")
        return render(
            request,
            self.plantilla,
            {"formulario": formulario, "modo_edicion": False},
        )


class VistaEditarEstudiante(SoloCoordinadorMixin, View):
    plantilla = "deportes/formulario_estudiante.html"

    def get(self, request: HttpRequest, pk: str) -> HttpResponse:
        perfil = get_object_or_404(
            PerfilEstudiante.objects.select_related("usuario"), pk=pk
        )
        formulario = FormularioEstudiante(instance=perfil)
        return render(
            request,
            self.plantilla,
            {"formulario": formulario, "estudiante": perfil, "modo_edicion": True},
        )

    def post(self, request: HttpRequest, pk: str) -> HttpResponse:
        perfil = get_object_or_404(
            PerfilEstudiante.objects.select_related("usuario"), pk=pk
        )
        formulario = FormularioEstudiante(request.POST, instance=perfil)
        if formulario.is_valid():
            with transaction.atomic():
                perfil = formulario.save()
                usuario = perfil.usuario
                usuario.email = formulario.cleaned_data["correo"]
                usuario.first_name = perfil.nombres
                usuario.last_name = perfil.apellidos
                usuario.activo = perfil.activo
                usuario.save()

                registrar_evento_auditoria(
                    usuario=request.user,
                    accion="edicion_estudiante",
                    entidad="PerfilEstudiante",
                    identificador=str(perfil.id),
                    request=request,
                    detalle={
                        "correo": usuario.email,
                        "curso_o_carrera": perfil.curso_o_carrera,
                        "activo": perfil.activo,
                    },
                )
            messages.success(
                request,
                f"Los datos del estudiante «{perfil.nombre_completo}» fueron actualizados.",
            )
            return redirect("deportes:lista_estudiantes")
        return render(
            request,
            self.plantilla,
            {"formulario": formulario, "estudiante": perfil, "modo_edicion": True},
        )


@require_POST
@csrf_protect
@rol_requerido(Usuario.ROL_COORDINADOR)
def vista_cambiar_estado_estudiante(request: HttpRequest, pk: str) -> HttpResponse:
    """Baja logica o reactivacion de un estudiante y su cuenta."""
    perfil = get_object_or_404(
        PerfilEstudiante.objects.select_related("usuario"), pk=pk
    )
    with transaction.atomic():
        nuevo_estado = not perfil.activo
        perfil.activo = nuevo_estado
        perfil.save(update_fields=["activo", "actualizado_en"])
        perfil.usuario.activo = nuevo_estado
        perfil.usuario.save(update_fields=["activo", "is_active", "actualizado_en"])
        registrar_evento_auditoria(
            usuario=request.user,
            accion="reactivacion_estudiante" if nuevo_estado else "baja_logica_estudiante",
            entidad="PerfilEstudiante",
            identificador=str(perfil.id),
            request=request,
            detalle={"correo": perfil.usuario.email, "activo": nuevo_estado},
        )
    estado_txt = "reactivado" if perfil.activo else "desactivado (baja lógica)"
    messages.info(request, f"El estudiante «{perfil.nombre_completo}» fue {estado_txt}.")
    return redirect("deportes:lista_estudiantes")


# ==============================================================================
# 4. INSCRIPCIONES DE ESTUDIANTES EN DISCIPLINAS
# ==============================================================================


class VistaListaInscripciones(SoloCoordinadorMixin, View):
    plantilla = "deportes/lista_inscripciones.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        disciplina_id = request.GET.get("disciplina", "").strip()
        estado = request.GET.get("estado", "").strip()
        busqueda = request.GET.get("q", "").strip()

        inscripciones = Inscripcion.objects.select_related(
            "estudiante", "estudiante__usuario", "disciplina"
        ).order_by("-fecha_inscripcion", "-creado_en")

        if disciplina_id:
            inscripciones = inscripciones.filter(disciplina_id=disciplina_id)
        if estado in (Inscripcion.ESTADO_ACTIVA, Inscripcion.ESTADO_BAJA):
            inscripciones = inscripciones.filter(estado=estado)
        if busqueda:
            indice_rut = calcular_indice_ciego_rut(normalizar_rut(busqueda))
            inscripciones = inscripciones.filter(
                Q(estudiante__nombres__icontains=busqueda)
                | Q(estudiante__apellidos__icontains=busqueda)
                | Q(disciplina__nombre__icontains=busqueda)
                | Q(estudiante__rut_indice_ciego=indice_rut)
            )

        disciplinas_filtro = Disciplina.objects.order_by("nombre")
        paginador = Paginator(inscripciones, 15)
        pagina_obj = paginador.get_page(request.GET.get("pagina"))

        return render(
            request,
            self.plantilla,
            {
                "pagina_obj": pagina_obj,
                "disciplinas_filtro": disciplinas_filtro,
                "disciplina_seleccionada": disciplina_id,
                "estado_filtro": estado,
                "busqueda": busqueda,
            },
        )


class VistaCrearInscripcion(SoloCoordinadorMixin, View):
    plantilla = "deportes/formulario_inscripcion.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        formulario = FormularioInscripcion()
        return render(request, self.plantilla, {"formulario": formulario})

    def post(self, request: HttpRequest) -> HttpResponse:
        formulario = FormularioInscripcion(request.POST)
        if formulario.is_valid():
            with transaction.atomic():
                disciplina_bloqueada = Disciplina.objects.select_for_update().get(
                    pk=formulario.cleaned_data["disciplina"].pk
                )
                estudiante = formulario.cleaned_data["estudiante"]
                if disciplina_bloqueada.cupos_disponibles <= 0:
                    formulario.add_error(
                        "disciplina",
                        f"La disciplina «{disciplina_bloqueada.nombre}» ya no cuenta con cupos disponibles.",
                    )
                    return render(request, self.plantilla, {"formulario": formulario})

                inscripcion = formulario.save()
                registrar_evento_auditoria(
                    usuario=request.user,
                    accion="alta_inscripcion",
                    entidad="Inscripcion",
                    identificador=str(inscripcion.id),
                    request=request,
                    detalle={
                        "estudiante": estudiante.nombre_completo,
                        "disciplina": disciplina_bloqueada.nombre,
                    },
                )
            messages.success(
                request,
                f"Se inscribió a «{inscripcion.estudiante.nombre_completo}» en «{inscripcion.disciplina.nombre}».",
            )
            return redirect("deportes:lista_inscripciones")
        return render(request, self.plantilla, {"formulario": formulario})


@require_POST
@csrf_protect
@rol_requerido(Usuario.ROL_COORDINADOR)
def vista_dar_baja_inscripcion(request: HttpRequest, pk: str) -> HttpResponse:
    """Da de baja logicamente una inscripcion conservando su historial."""
    inscripcion = get_object_or_404(
        Inscripcion.objects.select_related("estudiante", "disciplina"), pk=pk
    )
    if inscripcion.estado == Inscripcion.ESTADO_ACTIVA:
        with transaction.atomic():
            inscripcion.dar_de_baja()
            registrar_evento_auditoria(
                usuario=request.user,
                accion="baja_logica_inscripcion",
                entidad="Inscripcion",
                identificador=str(inscripcion.id),
                request=request,
                detalle={
                    "estudiante": inscripcion.estudiante.nombre_completo,
                    "disciplina": inscripcion.disciplina.nombre,
                    "fecha_baja": str(inscripcion.fecha_baja),
                },
            )
        messages.info(
            request,
            f"La inscripción de «{inscripcion.estudiante.nombre_completo}» en «{inscripcion.disciplina.nombre}» fue dada de baja conservando el historial.",
        )
    return redirect("deportes:lista_inscripciones")
