"""
Pruebas de integracion y seguridad de los Modulos Entrenador y Estudiante (Fases 4 y 5):
- Registro de sesion, asistencia en lote y evaluaciones en escala 1.0 a 7.0
- Bloqueo de fechas futuras y sesiones duplicadas
- Ventana de correccion de 7 dias y registro en RegistroAuditoria al corregir
- Prevencion de IDOR: un entrenador no accede a disciplinas ajenas; Coordinador no registra asistencia;
  Estudiante solo ve sus propios datos.
"""
from datetime import time, timedelta
import pytest
from django.urls import reverse
from django.utils import timezone
from apps.auditoria.models import RegistroAuditoria
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
class PruebasModuloEntrenadorYEstudiante:
    def setup_method(self) -> None:
        self.coordinador = Usuario.objects.create_user(
            username="coord_f4",
            email="coord_f4@palestra.cl",
            password="ClaveSeguraCoord2026!",
            rol=Usuario.ROL_COORDINADOR,
        )

        # Entrenador 1 (Titular de Natacion)
        u_ent1 = Usuario.objects.create_user(
            username="ent1_f4",
            email="ent1_f4@palestra.cl",
            password="ClaveSeguraEnt12026!",
            rol=Usuario.ROL_ENTRENADOR,
        )
        self.entrenador1 = PerfilEntrenador.objects.create(
            usuario=u_ent1,
            rut="14.567.890-0",
            nombres="Carlos",
            apellidos="Vega",
            especialidad="Natación",
        )

        # Entrenador 2 (Ajeno a Natacion)
        u_ent2 = Usuario.objects.create_user(
            username="ent2_f4",
            email="ent2_f4@palestra.cl",
            password="ClaveSeguraEnt22026!",
            rol=Usuario.ROL_ENTRENADOR,
        )
        self.entrenador2 = PerfilEntrenador.objects.create(
            usuario=u_ent2,
            rut="16.234.567-2",
            nombres="Elena",
            apellidos="Pardo",
            especialidad="Atletismo",
        )

        self.disciplina1 = Disciplina.objects.create(
            nombre="Natación Avanzada",
            descripcion="Entrenamiento piscina",
            cupo_maximo=15,
            dia=Disciplina.DIA_MARTES,
            hora_inicio=time(16, 0),
            hora_termino=time(18, 0),
            lugar="Piscina",
            activo=True,
        )
        EntrenadorDisciplina.objects.create(
            entrenador=self.entrenador1, disciplina=self.disciplina1
        )

        # Estudiante 1 inscrito en Natacion
        u_est1 = Usuario.objects.create_user(
            username="est1_f4",
            email="est1_f4@palestra.cl",
            password="ClaveSeguraEst12026!",
            rol=Usuario.ROL_ESTUDIANTE,
        )
        self.estudiante1 = PerfilEstudiante.objects.create(
            usuario=u_est1,
            rut="18.123.456-3",
            nombres="Sofía",
            apellidos="Bravo",
            curso_o_carrera="Enfermería",
        )
        Inscripcion.objects.create(
            estudiante=self.estudiante1,
            disciplina=self.disciplina1,
            estado=Inscripcion.ESTADO_ACTIVA,
        )

    def test_entrenador_crea_sesion_registra_asistencia_evaluacion_y_corrige_en_7_dias(
        self, client
    ) -> None:
        client.force_login(self.entrenador1.usuario)
        hoy = timezone.localdate()

        # 1. Crear sesion con fecha futura debe fallar
        fecha_futura = (hoy + timedelta(days=3)).isoformat()
        resp_futura = client.post(
            reverse("seguimiento:crear_sesion"),
            {"disciplina": str(self.disciplina1.id), "fecha": fecha_futura},
        )
        assert resp_futura.status_code == 200
        assert SesionEntrenamiento.objects.count() == 0

        # 2. Crear sesion hoy funciona
        resp_ok = client.post(
            reverse("seguimiento:crear_sesion"),
            {
                "disciplina": str(self.disciplina1.id),
                "fecha": hoy.isoformat(),
                "tema": "Resistencia aeróbica",
            },
        )
        assert resp_ok.status_code == 302
        sesion = SesionEntrenamiento.objects.get(
            disciplina=self.disciplina1, fecha=hoy
        )

        # 3. Guardar asistencia y nota en lote
        url_gestion = reverse(
            "seguimiento:gestionar_sesion", kwargs={"sesion_id": sesion.id}
        )
        est_id = str(self.estudiante1.id)
        resp_lote = client.post(
            url_gestion,
            {
                "tema": "Resistencia aeróbica",
                f"estado_{est_id}": "presente",
                f"obs_asist_{est_id}": "Puntual",
                f"puntaje_{est_id}": "6.4",
                f"obs_eval_{est_id}": "Excelente técnica",
            },
        )
        assert resp_lote.status_code == 302
        asist = Asistencia.objects.get(sesion=sesion, estudiante=self.estudiante1)
        eval_obj = Evaluacion.objects.get(sesion=sesion, estudiante=self.estudiante1)
        assert asist.estado == "presente"
        assert str(eval_obj.puntaje) == "6.4"

        # 4. Corregir dentro de los 7 dias genera registro en bitacora de auditoria
        resp_corr = client.post(
            url_gestion,
            {
                "tema": "Resistencia aeróbica",
                f"estado_{est_id}": "justificado",
                f"obs_asist_{est_id}": "Certificado médico",
                f"puntaje_{est_id}": "6.8",
                f"obs_eval_{est_id}": "Corrección técnica",
            },
        )
        assert resp_corr.status_code == 302
        assert RegistroAuditoria.objects.filter(accion="correccion_asistencia").exists()
        assert RegistroAuditoria.objects.filter(accion="correccion_evaluacion").exists()

        # 5. Si la sesion tiene mas de 7 dias, rechaza la edicion con 403
        sesion.fecha = hoy - timedelta(days=10)
        sesion.save(update_fields=["fecha"])
        resp_expirada = client.post(
            url_gestion,
            {
                "tema": "Intento fuera de plazo",
                f"estado_{est_id}": "ausente",
                f"puntaje_{est_id}": "2.0",
            },
        )
        assert resp_expirada.status_code == 403

    def test_prevencion_idor_y_segregacion_de_funciones(self, client) -> None:
        sesion = SesionEntrenamiento.objects.create(
            disciplina=self.disciplina1,
            fecha=timezone.localdate(),
            entrenador=self.entrenador1,
            tema="Sesión protegida",
        )
        url_nomina = reverse(
            "seguimiento:entrenador_nomina_disciplina",
            kwargs={"disciplina_id": self.disciplina1.id},
        )
        url_sesion = reverse(
            "seguimiento:gestionar_sesion",
            kwargs={"sesion_id": sesion.id},
        )

        # Entrenador 2 (no asignado a Natacion) recibe 403 al intentar acceder por URL directa
        client.force_login(self.entrenador2.usuario)
        assert client.get(url_nomina).status_code == 403
        assert client.get(url_sesion).status_code == 403

        # El Coordinador tampoco puede registrar asistencia (segregacion de funciones)
        client.force_login(self.coordinador)
        assert client.get(url_sesion).status_code == 403

        # El Estudiante puede consultar su propio resumen pero recibe 403 en vistas de entrenador
        client.force_login(self.estudiante1.usuario)
        assert client.get(url_sesion).status_code == 403
        resp_est = client.get(reverse("seguimiento:estudiante_mi_asistencia"))
        assert resp_est.status_code == 200
        assert "Natación Avanzada" in resp_est.content.decode("utf-8")
