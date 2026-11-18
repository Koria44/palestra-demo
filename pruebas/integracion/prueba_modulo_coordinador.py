"""
Pruebas de integracion del Modulo Coordinador Deportivo (Fase 3):
- CRUD de disciplinas, validacion de cupos y horarios
- Creacion de entrenadores y estudiantes con enlace de activacion o contrasena temporal
- Flujo de inscripcion con validacion de cupo maximo, duplicados, estado inactivo y baja logica
- Segregacion de funciones: ni Entrenador ni Estudiante pueden acceder a vistas de Coordinador
"""
from datetime import time
import pytest
from django.urls import reverse
from apps.cuentas.models import Usuario
from apps.deportes.models import Disciplina, Inscripcion, PerfilEstudiante


@pytest.mark.django_db
class PruebasModuloCoordinador:
    def setup_method(self) -> None:
        self.coordinador = Usuario.objects.create_user(
            username="coord_f3",
            email="coord_f3@palestra.cl",
            password="ClaveSeguraCoord2026!",
            rol=Usuario.ROL_COORDINADOR,
            activo=True,
        )
        self.entrenador_usr = Usuario.objects.create_user(
            username="ent_f3",
            email="ent_f3@palestra.cl",
            password="ClaveSeguraEntren2026!",
            rol=Usuario.ROL_ENTRENADOR,
            activo=True,
        )

    def test_crear_editar_y_baja_logica_disciplina(self, client) -> None:
        client.force_login(self.coordinador)
        resp = client.post(
            reverse("deportes:crear_disciplina"),
            {
                "nombre": "Tenis de Mesa",
                "descripcion": "Entrenamiento de reflejos y técnica.",
                "cupo_maximo": 10,
                "dia": Disciplina.DIA_LUNES,
                "hora_inicio": "15:00",
                "hora_termino": "17:00",
                "lugar": "Sala Multiuso 2",
                "activo": True,
            },
        )
        assert resp.status_code == 302
        disc = Disciplina.objects.get(nombre="Tenis de Mesa")
        assert disc.cupo_maximo == 10

        # Baja logica
        resp_baja = client.post(
            reverse("deportes:cambiar_estado_disciplina", kwargs={"pk": disc.id})
        )
        assert resp_baja.status_code == 302
        disc.refresh_from_db()
        assert disc.activo is False

    def test_crear_estudiante_con_enlace_y_con_contrasena_temporal(self, client) -> None:
        client.force_login(self.coordinador)
        # 1. Por enlace de activacion
        resp1 = client.post(
            reverse("deportes:crear_estudiante"),
            {
                "rut": "14.567.890-0",
                "correo": "est_enlace@palestra.cl",
                "nombres": "Pedro",
                "apellidos": "Valenzuela",
                "curso_o_carrera": "Medicina",
                "telefono": "+56911223344",
                "modo_creacion_cuenta": "enlace_activacion",
                "activo": True,
            },
        )
        assert resp1.status_code == 302
        est1 = PerfilEstudiante.objects.get(usuario__email="est_enlace@palestra.cl")
        assert est1.usuario.has_usable_password() is False
        assert est1.usuario.hash_token_activacion != ""

        # 2. Por contrasena temporal
        resp2 = client.post(
            reverse("deportes:crear_estudiante"),
            {
                "rut": "16.234.567-2",
                "correo": "est_temp@palestra.cl",
                "nombres": "Laura",
                "apellidos": "Molina",
                "curso_o_carrera": "Odontología",
                "telefono": "+56955667788",
                "modo_creacion_cuenta": "contrasena_temporal",
                "activo": True,
            },
        )
        assert resp2.status_code == 302
        est2 = PerfilEstudiante.objects.get(usuario__email="est_temp@palestra.cl")
        assert est2.usuario.debe_cambiar_contrasena is True
        assert est2.usuario.password.startswith("argon2$argon2id$")

    def test_flujo_inscripcion_validacion_cupo_duplicado_y_baja_logica(self, client) -> None:
        client.force_login(self.coordinador)
        disc_cupo_1 = Disciplina.objects.create(
            nombre="Ajedrez Deportivo",
            descripcion="Estrategia",
            cupo_maximo=1,
            dia=Disciplina.DIA_VIERNES,
            hora_inicio=time(14, 0),
            hora_termino=time(16, 0),
            lugar="Biblioteca",
            activo=True,
        )
        u1 = Usuario.objects.create_user(
            username="e1", email="e1@palestra.cl", rol=Usuario.ROL_ESTUDIANTE
        )
        est1 = PerfilEstudiante.objects.create(
            usuario=u1,
            rut="18.123.456-3",
            nombres="Ana",
            apellidos="Pino",
            curso_o_carrera="Derecho",
        )
        u2 = Usuario.objects.create_user(
            username="e2", email="e2@palestra.cl", rol=Usuario.ROL_ESTUDIANTE
        )
        est2 = PerfilEstudiante.objects.create(
            usuario=u2,
            rut="19.234.567-7",
            nombres="Luis",
            apellidos="Tapia",
            curso_o_carrera="Derecho",
        )

        # Inscribe al primer estudiante (ocupa el unico cupo)
        resp_ok = client.post(
            reverse("deportes:crear_inscripcion"),
            {"estudiante": str(est1.id), "disciplina": str(disc_cupo_1.id)},
        )
        assert resp_ok.status_code == 302
        assert Inscripcion.objects.filter(estado="activa").count() == 1

        # Intenta inscribir un segundo estudiante sin cupo disponible -> debe rechazarse
        resp_sin_cupo = client.post(
            reverse("deportes:crear_inscripcion"),
            {"estudiante": str(est2.id), "disciplina": str(disc_cupo_1.id)},
        )
        assert resp_sin_cupo.status_code == 200
        assert Inscripcion.objects.filter(estado="activa").count() == 1

        # Da de baja logica la primera inscripcion -> libera el cupo y conserva historial
        insc_1 = Inscripcion.objects.get(estudiante=est1, disciplina=disc_cupo_1)
        client.post(reverse("deportes:dar_baja_inscripcion", kwargs={"pk": insc_1.id}))
        insc_1.refresh_from_db()
        assert insc_1.estado == Inscripcion.ESTADO_BAJA
        assert insc_1.fecha_baja is not None

        # Ahora el segundo estudiante si puede inscribirse
        resp_ahora_si = client.post(
            reverse("deportes:crear_inscripcion"),
            {"estudiante": str(est2.id), "disciplina": str(disc_cupo_1.id)},
        )
        assert resp_ahora_si.status_code == 302
        assert Inscripcion.objects.filter(estudiante=est2, estado="activa").exists()

    def test_entrenador_no_puede_acceder_a_gestion_de_coordinador(self, client) -> None:
        client.force_login(self.entrenador_usr)
        for ruta in [
            reverse("deportes:lista_disciplinas"),
            reverse("deportes:crear_disciplina"),
            reverse("deportes:lista_entrenadores"),
            reverse("deportes:lista_estudiantes"),
            reverse("deportes:crear_inscripcion"),
        ]:
            respuesta = client.get(ruta)
            assert respuesta.status_code == 403
