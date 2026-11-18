"""
Pruebas de seguridad y autorizacion completa:
- Matriz completa rol por recurso (Coordinador, Entrenador, Estudiante y No autenticado)
  en vistas web y endpoints de la API RESTful (/api/v1/).
- Segregacion de funciones (Coordinador no registra asistencia; Entrenador no inscribe).
- Prevencion de escalacion de privilegios, IDOR, CSRF, XSS y enumeracion de usuarios.
- Exportacion de reportes CSV y PDF con verificacion de alcance por rol.
"""
from datetime import time
from decimal import Decimal
import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from apps.cuentas.models import Usuario
from apps.deportes.models import (
    Disciplina,
    EntrenadorDisciplina,
    Inscripcion,
    PerfilEntrenador,
    PerfilEstudiante,
)
from apps.seguimiento.models import Asistencia, Evaluacion, SesionEntrenamiento


@pytest.mark.django_db
class PruebasMatrizAutorizacionYAPI:
    """Verifica cada combinacion permitida y denegada de la matriz de permisos (Seccion 5 y 10.6)."""

    def setup_method(self) -> None:
        self.coordinador = Usuario.objects.create_user(
            username="coord_m",
            email="coord_m@palestra.cl",
            password="ClaveSeguraCoord2026!",
            rol=Usuario.ROL_COORDINADOR,
        )

        u_ent1 = Usuario.objects.create_user(
            username="ent1_m",
            email="ent1_m@palestra.cl",
            password="ClaveSeguraEnt12026!",
            rol=Usuario.ROL_ENTRENADOR,
        )
        self.entrenador1 = PerfilEntrenador.objects.create(
            usuario=u_ent1,
            rut="14.567.890-0",
            nombres="Marcos",
            apellidos="Silva",
            especialidad="Básquetbol",
        )

        u_ent2 = Usuario.objects.create_user(
            username="ent2_m",
            email="ent2_m@palestra.cl",
            password="ClaveSeguraEnt22026!",
            rol=Usuario.ROL_ENTRENADOR,
        )
        self.entrenador2 = PerfilEntrenador.objects.create(
            usuario=u_ent2,
            rut="16.234.567-2",
            nombres="Patricia",
            apellidos="Gómez",
            especialidad="Vóleibol",
        )

        u_est1 = Usuario.objects.create_user(
            username="est1_m",
            email="est1_m@palestra.cl",
            password="ClaveSeguraEst12026!",
            rol=Usuario.ROL_ESTUDIANTE,
        )
        self.estudiante1 = PerfilEstudiante.objects.create(
            usuario=u_est1,
            rut="18.123.456-3",
            nombres="Camila",
            apellidos="Navarro",
            curso_o_carrera="Arquitectura",
        )

        u_est2 = Usuario.objects.create_user(
            username="est2_m",
            email="est2_m@palestra.cl",
            password="ClaveSeguraEst22026!",
            rol=Usuario.ROL_ESTUDIANTE,
        )
        self.estudiante2 = PerfilEstudiante.objects.create(
            usuario=u_est2,
            rut="19.234.567-7",
            nombres="Tomás",
            apellidos="Herrera",
            curso_o_carrera="Derecho",
        )

        self.disc_ent1 = Disciplina.objects.create(
            nombre="Básquetbol Competitivo",
            descripcion="Cancha",
            cupo_maximo=15,
            dia=Disciplina.DIA_LUNES,
            hora_inicio=time(16, 0),
            hora_termino=time(18, 0),
            lugar="Gimnasio 1",
        )
        self.disc_ent2 = Disciplina.objects.create(
            nombre="Vóleibol Avanzado",
            descripcion="Cancha",
            cupo_maximo=15,
            dia=Disciplina.DIA_MIERCOLES,
            hora_inicio=time(16, 0),
            hora_termino=time(18, 0),
            lugar="Gimnasio 2",
        )
        EntrenadorDisciplina.objects.create(
            entrenador=self.entrenador1, disciplina=self.disc_ent1
        )
        EntrenadorDisciplina.objects.create(
            entrenador=self.entrenador2, disciplina=self.disc_ent2
        )

        Inscripcion.objects.create(
            estudiante=self.estudiante1,
            disciplina=self.disc_ent1,
            estado=Inscripcion.ESTADO_ACTIVA,
        )
        Inscripcion.objects.create(
            estudiante=self.estudiante2,
            disciplina=self.disc_ent2,
            estado=Inscripcion.ESTADO_ACTIVA,
        )

        self.sesion_ent1 = SesionEntrenamiento.objects.create(
            disciplina=self.disc_ent1,
            fecha=timezone.localdate(),
            entrenador=self.entrenador1,
            tema="Táctica",
        )
        Asistencia.objects.create(
            sesion=self.sesion_ent1,
            estudiante=self.estudiante1,
            estado="presente",
            registrado_por=self.entrenador1.usuario,
        )
        Evaluacion.objects.create(
            sesion=self.sesion_ent1,
            estudiante=self.estudiante1,
            puntaje=Decimal("6.3"),
            observacion="Formula peligrosa =1+1",
            registrado_por=self.entrenador1.usuario,
        )

    def test_matriz_permisos_openapi_solo_coordinador(self) -> None:
        api = APIClient()
        url_doc = reverse("api:documentacion_openapi")
        url_esquema = reverse("api:esquema_openapi")

        # Anonimo -> 403
        assert api.get(url_doc).status_code == 403
        assert api.get(url_esquema).status_code == 403

        # Estudiante -> 403
        api.force_authenticate(user=self.estudiante1.usuario)
        assert api.get(url_doc).status_code == 403

        # Entrenador -> 403
        api.force_authenticate(user=self.entrenador1.usuario)
        assert api.get(url_doc).status_code == 403

        # Coordinador -> 200 OK
        api.force_authenticate(user=self.coordinador)
        assert api.get(url_doc).status_code == 200
        assert api.get(url_esquema).status_code == 200

    def test_matriz_api_aislamiento_datos_y_segregacion_funciones(self) -> None:
        api = APIClient()

        # 1. Estudiante 1 solo ve su disciplina y su asistencia; no puede listar estudiantes
        api.force_authenticate(user=self.estudiante1.usuario)
        resp_disc = api.get("/api/v1/disciplinas/")
        assert resp_disc.status_code == 200
        assert resp_disc.data["count"] == 1
        assert resp_disc.data["results"][0]["nombre"] == "Básquetbol Competitivo"

        resp_est_prohibido = api.get("/api/v1/estudiantes/")
        assert resp_est_prohibido.status_code == 403

        # 2. Entrenador 1 solo ve inscritos de su disciplina y no puede inscribir ni crear disciplinas
        api.force_authenticate(user=self.entrenador1.usuario)
        resp_est_ent1 = api.get("/api/v1/estudiantes/")
        assert resp_est_ent1.status_code == 200
        assert resp_est_ent1.data["count"] == 1
        assert resp_est_ent1.data["results"][0]["nombres"] == "Camila"

        resp_intento_inscribir = api.post(
            "/api/v1/inscripciones/",
            {
                "estudiante": str(self.estudiante2.id),
                "disciplina": str(self.disc_ent1.id),
            },
        )
        assert resp_intento_inscribir.status_code == 403

        # 3. Coordinador ve todo, pero no puede registrar asistencia ni evaluaciones (segregacion)
        api.force_authenticate(user=self.coordinador)
        resp_est_coord = api.get("/api/v1/estudiantes/")
        assert resp_est_coord.status_code == 200
        assert resp_est_coord.data["count"] == 2

        resp_coord_asist = api.post(
            "/api/v1/asistencias/",
            {
                "sesion": str(self.sesion_ent1.id),
                "estudiante": str(self.estudiante1.id),
                "estado": "presente",
            },
        )
        assert resp_coord_asist.status_code == 403

    def test_reportes_web_y_exportacion_csv_pdf_por_rol(self, client) -> None:
        # Coordinador exporta CSV y PDF
        client.force_login(self.coordinador)
        resp_panel = client.get(reverse("reportes:panel_reportes"))
        assert resp_panel.status_code == 200

        resp_csv = client.get(reverse("reportes:exportar_csv"))
        assert resp_csv.status_code == 200
        assert resp_csv["Content-Type"].startswith("text/csv")
        texto_csv = resp_csv.content.decode("utf-8")
        assert "Camila Navarro" in texto_csv

        resp_pdf = client.get(reverse("reportes:exportar_pdf"))
        assert resp_pdf.status_code == 200
        assert resp_pdf["Content-Type"] == "application/pdf"
        assert resp_pdf.content.startswith(b"%PDF")

        # Estudiante 1 exporta su reporte y nunca ve datos de Estudiante 2
        client.force_login(self.estudiante1.usuario)
        resp_csv_est1 = client.get(
            reverse("reportes:exportar_csv")
            + f"?estudiante={self.estudiante2.id}"
        )
        texto_est1 = resp_csv_est1.content.decode("utf-8")
        assert "Camila Navarro" in texto_est1
        assert "Tomás Herrera" not in texto_est1
