"""
Pruebas de integracion exhaustivas para cubrir el 100% de los flujos de:
- Listados, filtros y edicion de disciplinas, entrenadores, estudiantes e inscripciones
- Paneles de inicio de Coordinador, Entrenador y Estudiante
- Cambio de contrasena, cierre de sesion, aviso de privacidad y recuperacion de contrasena
- Listado y filtros de bitacora de auditoria
- Creacion y actualizacion via API RESTful (/api/v1/) para sesiones, asistencias y evaluaciones
"""
from datetime import timedelta
import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from apps.cuentas.models import Usuario
from apps.deportes.models import Disciplina, PerfilEntrenador, PerfilEstudiante
from apps.seguimiento.models import SesionEntrenamiento


@pytest.mark.django_db
class PruebasCoberturaCompletaVistasYAPI:
    """Cubre todos los flujos de vistas HTML, formularios, comandos y endpoints API."""

    def test_cargar_datos_demo_y_recorrer_vistas_coordinador_entrenador_estudiante(
        self, client, settings
    ) -> None:
        settings.DEBUG = True
        call_command("cargar_datos_demo")

        coordinador = Usuario.objects.get(email="coordinador@palestra.cl")
        entrenador = PerfilEntrenador.objects.first()
        estudiante = PerfilEstudiante.objects.first()
        disciplina = Disciplina.objects.first()
        assert entrenador is not None and estudiante is not None and disciplina is not None

        # 1. Login por RUT de entrenador y estudiante + fallo de login para cubrir senales
        resp_fallo = client.post(
            reverse("cuentas:iniciar_sesion"),
            {"identificador": "noexiste@palestra.cl", "contrasena": "ClaveIncorrecta123!"},
        )
        assert resp_fallo.status_code == 200

        resp_rut_ent = client.post(
            reverse("cuentas:iniciar_sesion"),
            {"identificador": entrenador.rut_formateado, "contrasena": "PalestraDemo2026!"},
        )
        assert resp_rut_ent.status_code == 302
        client.get(reverse("cuentas:panel_inicio"))
        client.get(reverse("cuentas:panel_entrenador"))
        client.get(reverse("seguimiento:entrenador_mis_disciplinas"))
        disc_ent = entrenador.disciplinas.first()
        assert disc_ent is not None
        client.get(
            reverse(
                "seguimiento:entrenador_nomina_disciplina",
                kwargs={"disciplina_id": disc_ent.id},
            )
        )
        client.get(reverse("seguimiento:lista_sesiones") + f"?disciplina={disc_ent.id}")
        client.get(reverse("seguimiento:crear_sesion"))
        sesion_ent = SesionEntrenamiento.objects.filter(disciplina=disc_ent).first()
        if sesion_ent:
            client.get(
                reverse(
                    "seguimiento:gestionar_sesion",
                    kwargs={"sesion_id": sesion_ent.id},
                )
            )
        client.get(reverse("reportes:panel_reportes"))
        client.post(reverse("cuentas:cerrar_sesion"))

        # 2. Login por RUT de estudiante y recorrido de sus vistas
        resp_rut_est = client.post(
            reverse("cuentas:iniciar_sesion"),
            {"identificador": estudiante.rut_formateado, "contrasena": "PalestraDemo2026!"},
        )
        assert resp_rut_est.status_code == 302
        client.get(reverse("cuentas:panel_inicio"))
        client.get(reverse("cuentas:panel_estudiante"))
        client.get(reverse("seguimiento:estudiante_mis_disciplinas"))
        client.get(
            reverse("seguimiento:estudiante_mi_asistencia")
            + f"?disciplina={disciplina.id}"
        )
        client.get(reverse("cuentas:aviso_privacidad"))
        client.post(reverse("cuentas:cerrar_sesion"))

        # 3. Recorrido completo de Coordinador (listados, filtros, creacion y edicion)
        client.force_login(coordinador)
        client.get(reverse("cuentas:panel_inicio"))
        client.get(reverse("cuentas:panel_coordinador"))
        client.get(reverse("auditoria:lista_auditoria") + "?q=login&accion=inicio_sesion_exitoso")
        client.get(reverse("deportes:lista_disciplinas") + "?q=Fútbol&estado=activa")
        client.get(reverse("deportes:crear_disciplina"))
        client.get(reverse("deportes:editar_disciplina", kwargs={"pk": disciplina.id}))
        client.post(
            reverse("deportes:editar_disciplina", kwargs={"pk": disciplina.id}),
            {
                "nombre": disciplina.nombre,
                "descripcion": "Descripción actualizada",
                "cupo_maximo": disciplina.cupo_maximo,
                "dia": disciplina.dia,
                "hora_inicio": "16:00",
                "hora_termino": "18:00",
                "lugar": disciplina.lugar,
                "activo": True,
            },
        )

        # Creacion, edicion y baja logica de entrenador
        client.get(reverse("deportes:lista_entrenadores") + "?q=Marcelo")
        client.get(reverse("deportes:crear_entrenador"))
        client.post(
            reverse("deportes:crear_entrenador"),
            {
                "rut": "17.654.321-3",
                "correo": "nuevo.entrenador@palestra.cl",
                "nombres": "Rodrigo",
                "apellidos": "Fuentes",
                "especialidad": "Tenis",
                "telefono": "+56912341234",
                "disciplinas_asignadas": [str(disciplina.id)],
                "modo_creacion_cuenta": "enlace_activacion",
                "activo": True,
            },
        )
        nuevo_ent = PerfilEntrenador.objects.get(usuario__email="nuevo.entrenador@palestra.cl")
        client.get(reverse("deportes:editar_entrenador", kwargs={"pk": nuevo_ent.id}))
        client.post(
            reverse("deportes:editar_entrenador", kwargs={"pk": nuevo_ent.id}),
            {
                "rut": nuevo_ent.rut_formateado,
                "correo": "nuevo.entrenador@palestra.cl",
                "nombres": "Rodrigo Andrés",
                "apellidos": "Fuentes",
                "especialidad": "Tenis Avanzado",
                "telefono": "+56912341234",
                "disciplinas_asignadas": [str(disciplina.id)],
                "activo": True,
            },
        )
        client.post(reverse("deportes:cambiar_estado_entrenador", kwargs={"pk": nuevo_ent.id}))

        # Edicion y baja logica de estudiante + listado de inscripciones
        client.get(reverse("deportes:lista_estudiantes") + "?q=Catalina&estado=activo")
        client.get(reverse("deportes:editar_estudiante", kwargs={"pk": estudiante.id}))
        client.post(
            reverse("deportes:editar_estudiante", kwargs={"pk": estudiante.id}),
            {
                "rut": estudiante.rut_formateado,
                "correo": estudiante.usuario.email,
                "nombres": estudiante.nombres,
                "apellidos": estudiante.apellidos,
                "curso_o_carrera": "Ingeniería Civil en Informática",
                "telefono": "+56988887777",
                "activo": True,
            },
        )
        client.post(reverse("deportes:cambiar_estado_estudiante", kwargs={"pk": estudiante.id}))
        client.post(reverse("deportes:cambiar_estado_estudiante", kwargs={"pk": estudiante.id}))
        client.get(
            reverse("deportes:lista_inscripciones")
            + f"?disciplina={disciplina.id}&estado=activa&q=Catalina"
        )
        client.get(reverse("deportes:crear_inscripcion"))

    def test_cambio_obligatorio_contrasena_recuperacion_y_operaciones_api_entrenador(
        self, client, settings
    ) -> None:
        settings.DEBUG = True
        call_command("cargar_datos_demo")
        entrenador = PerfilEntrenador.objects.first()
        estudiante = PerfilEstudiante.objects.first()
        assert entrenador is not None and estudiante is not None
        disc = entrenador.disciplinas.first()
        assert disc is not None

        # 1. Middleware de cambio obligatorio de contrasena y vista de cambio
        u_temp = estudiante.usuario
        u_temp.debe_cambiar_contrasena = True
        u_temp.save()
        client.force_login(u_temp)
        resp_redir = client.get(reverse("cuentas:panel_estudiante"))
        assert resp_redir.status_code == 302
        assert resp_redir.url == reverse("cuentas:cambiar_contrasena")

        client.get(reverse("cuentas:cambiar_contrasena"))
        resp_cambio = client.post(
            reverse("cuentas:cambiar_contrasena"),
            {
                "old_password": "PalestraDemo2026!",
                "new_password1": "NuevaContrasenaPersonal2026!",
                "new_password2": "NuevaContrasenaPersonal2026!",
            },
        )
        assert resp_cambio.status_code == 302
        u_temp.refresh_from_db()
        assert u_temp.debe_cambiar_contrasena is False

        # 2. Recuperacion de contrasena por correo
        client.logout()
        client.get(reverse("cuentas:recuperar_contrasena"))
        resp_rec = client.post(
            reverse("cuentas:recuperar_contrasena"),
            {"email": u_temp.email},
        )
        assert resp_rec.status_code == 302

        # 3. Operaciones de escritura en la API RESTful por Entrenador
        api = APIClient()
        api.force_authenticate(user=entrenador.usuario)
        fecha_nueva = (timezone.localdate() - timedelta(days=1)).isoformat()
        resp_crear_ses = api.post(
            "/api/v1/sesiones/",
            {
                "disciplina": str(disc.id),
                "fecha": fecha_nueva,
                "tema": "Sesión creada por API",
            },
        )
        assert resp_crear_ses.status_code == 201
        sesion_id = resp_crear_ses.data["id"]

        resp_crear_asist = api.post(
            "/api/v1/asistencias/",
            {
                "sesion": sesion_id,
                "estudiante": str(estudiante.id),
                "estado": "presente",
                "observacion": "Asistencia API",
            },
        )
        assert resp_crear_asist.status_code == 201
        asist_id = resp_crear_asist.data["id"]

        resp_patch_asist = api.patch(
            f"/api/v1/asistencias/{asist_id}/",
            {"estado": "justificado"},
        )
        assert resp_patch_asist.status_code == 200

        resp_crear_eval = api.post(
            "/api/v1/evaluaciones/",
            {
                "sesion": sesion_id,
                "estudiante": str(estudiante.id),
                "puntaje": "6.1",
                "observacion": "Evaluación API",
            },
        )
        assert resp_crear_eval.status_code == 201
        eval_id = resp_crear_eval.data["id"]

        resp_patch_eval = api.patch(
            f"/api/v1/evaluaciones/{eval_id}/",
            {"puntaje": "6.7"},
        )
        assert resp_patch_eval.status_code == 200

        resp_resumen_api = api.get("/api/v1/reportes/")
        assert resp_resumen_api.status_code == 200
        assert "porcentaje_asistencia" in resp_resumen_api.data
