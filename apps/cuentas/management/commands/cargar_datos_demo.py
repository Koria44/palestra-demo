"""
Comando de gestion `cargar_datos_demo` (Seccion 12).
Carga datos ficticios completos con RUT chilenos validos:
- 1 Coordinador Deportivo
- 2 Entrenadores
- 10 Estudiantes
- 5 Disciplinas deportivas
- Inscripciones activas e historicas (baja logica)
- Sesiones de entrenamiento pasadas y recientes con asistencia y evaluaciones.
Se niega a ejecutarse si DEBUG=False.
"""
from datetime import time, timedelta
from decimal import Decimal
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from apps.auditoria.models import registrar_evento_auditoria
from apps.cuentas.models import Usuario
from apps.deportes.models import (
    Disciplina,
    EntrenadorDisciplina,
    Inscripcion,
    PerfilEntrenador,
    PerfilEstudiante,
)
from apps.seguimiento.models import Asistencia, Evaluacion, SesionEntrenamiento


CONTRASENA_DEMO = "PalestraDemo2026!"


class Command(BaseCommand):
    help = "Carga datos de demostracion ficticios en la base de datos (solo permitido con DEBUG=True)."

    def handle(self, *args, **options) -> None:
        if not getattr(settings, "DEBUG", False):
            raise CommandError(
                "Operacion bloqueada: el comando cargar_datos_demo no puede ejecutarse cuando DEBUG=False."
            )

        with transaction.atomic():
            # 1. Coordinador Deportivo
            coordinador, creado_coord = Usuario.objects.get_or_create(
                email="coordinador@palestra.cl",
                defaults={
                    "username": "coordinador",
                    "first_name": "Roberto",
                    "last_name": "Valdivia",
                    "rol": Usuario.ROL_COORDINADOR,
                    "activo": True,
                    "is_staff": True,
                },
            )
            if creado_coord:
                coordinador.set_password(CONTRASENA_DEMO)
                coordinador.save()

            # 2. Dos Entrenadores con RUT chilenos validos
            datos_entrenadores = [
                {
                    "email": "entrenador.futbol@palestra.cl",
                    "username": "entrenador_futbol",
                    "rut": "14.567.890-0",
                    "nombres": "Marcelo",
                    "apellidos": "Arancibia",
                    "especialidad": "Deportes Colectivos y Fútbol",
                    "telefono": "+56991234501",
                },
                {
                    "email": "entrenadora.atletismo@palestra.cl",
                    "username": "entrenadora_atletismo",
                    "rut": "16.234.567-2",
                    "nombres": "Valentina",
                    "apellidos": "Riquelme",
                    "especialidad": "Atletismo, Natación y Acondicionamiento",
                    "telefono": "+56991234502",
                },
            ]

            perfiles_entrenadores: list[PerfilEntrenador] = []
            for d_ent in datos_entrenadores:
                u_ent, creado = Usuario.objects.get_or_create(
                    email=d_ent["email"],
                    defaults={
                        "username": d_ent["username"],
                        "first_name": d_ent["nombres"],
                        "last_name": d_ent["apellidos"],
                        "rol": Usuario.ROL_ENTRENADOR,
                        "activo": True,
                    },
                )
                if creado:
                    u_ent.set_password(CONTRASENA_DEMO)
                    u_ent.save()

                perfil_ent, _ = PerfilEntrenador.objects.update_or_create(
                    usuario=u_ent,
                    defaults={
                        "rut": d_ent["rut"],
                        "nombres": d_ent["nombres"],
                        "apellidos": d_ent["apellidos"],
                        "especialidad": d_ent["especialidad"],
                        "telefono": d_ent["telefono"],
                        "activo": True,
                    },
                )
                perfiles_entrenadores.append(perfil_ent)

            # 3. Cinco Disciplinas Deportivas
            datos_disciplinas = [
                {
                    "nombre": "Fútbol Varones y Damas",
                    "descripcion": "Entrenamiento táctico, técnico y preparación física en cancha sintética.",
                    "cupo_maximo": 22,
                    "dia": Disciplina.DIA_LUNES,
                    "hora_inicio": time(16, 0),
                    "hora_termino": time(18, 0),
                    "lugar": "Cancha Sintética Central",
                    "indice_entrenador": 0,
                },
                {
                    "nombre": "Básquetbol Universitario",
                    "descripcion": "Fundamentos ofensivos, defensivos y sistemas de juego en gimnasio techado.",
                    "cupo_maximo": 15,
                    "dia": Disciplina.DIA_MIERCOLES,
                    "hora_inicio": time(17, 0),
                    "hora_termino": time(19, 0),
                    "lugar": "Gimnasio Polideportivo A",
                    "indice_entrenador": 0,
                },
                {
                    "nombre": "Atletismo y Velocidad",
                    "descripcion": "Pruebas de pista, resistencia aeróbica, relevos y técnica de carrera.",
                    "cupo_maximo": 20,
                    "dia": Disciplina.DIA_MARTES,
                    "hora_inicio": time(15, 30),
                    "hora_termino": time(17, 30),
                    "lugar": "Pista Atlética Institucional",
                    "indice_entrenador": 1,
                },
                {
                    "nombre": "Vóleibol Mixto",
                    "descripcion": "Técnica de recepción, armado, bloqueo y trabajo en equipo.",
                    "cupo_maximo": 18,
                    "dia": Disciplina.DIA_JUEVES,
                    "hora_inicio": time(16, 30),
                    "hora_termino": time(18, 30),
                    "lugar": "Gimnasio Polideportivo B",
                    "indice_entrenador": 0,
                },
                {
                    "nombre": "Natación Formativa",
                    "descripcion": "Estilos crol, espalda y resistencia en piscina temperada semiolímpica.",
                    "cupo_maximo": 12,
                    "dia": Disciplina.DIA_VIERNES,
                    "hora_inicio": time(14, 0),
                    "hora_termino": time(16, 0),
                    "lugar": "Piscina Temperada Institucional",
                    "indice_entrenador": 1,
                },
            ]

            disciplinas_creadas: list[Disciplina] = []
            for d_disc in datos_disciplinas:
                disc, _ = Disciplina.objects.update_or_create(
                    nombre=d_disc["nombre"],
                    defaults={
                        "descripcion": d_disc["descripcion"],
                        "cupo_maximo": d_disc["cupo_maximo"],
                        "dia": d_disc["dia"],
                        "hora_inicio": d_disc["hora_inicio"],
                        "hora_termino": d_disc["hora_termino"],
                        "lugar": d_disc["lugar"],
                        "activo": True,
                    },
                )
                entrenador_asignado = perfiles_entrenadores[d_disc["indice_entrenador"]]
                EntrenadorDisciplina.objects.get_or_create(
                    entrenador=entrenador_asignado,
                    disciplina=disc,
                )
                disciplinas_creadas.append(disc)

            # 4. Nueve Estudiantes con RUT chilenos validos (Modulo 11)
            datos_estudiantes = [
                ("18.123.456-3", "Catalina", "Muñoz Rojas", "Ingeniería en Informática", "catalina.munoz@estudiante.palestra.cl", "+56982345601"),
                ("19.234.567-7", "Matías", "González Contreras", "Pedagogía en Educación Física", "matias.gonzalez@estudiante.palestra.cl", "+56982345602"),
                ("20.345.678-6", "Javiera", "Fernández Silva", "Arquitectura", "javiera.fernandez@estudiante.palestra.cl", "+56982345603"),
                ("21.456.789-K", "Sebastián", "López Morales", "Ingeniería Comercial", "sebastian.lopez@estudiante.palestra.cl", "+56982345604"),
                ("22.567.890-1", "Francisca", "Díaz Fuentes", "Derecho", "francisca.diaz@estudiante.palestra.cl", "+56982345605"),
                ("17.654.321-3", "Diego", "Martínez Vergara", "Kinesiología", "diego.martinez@estudiante.palestra.cl", "+56982345606"),
                ("18.765.432-7", "Constanza", "Pérez Carrasco", "Psicología", "constanza.perez@estudiante.palestra.cl", "+56982345607"),
                ("19.876.543-0", "Nicolás", "Sánchez Tapia", "Ingeniería Civil Industrial", "nicolas.sanchez@estudiante.palestra.cl", "+56982345608"),
                ("20.987.654-K", "Antonia", "Ramírez Castillo", "Enfermería", "antonia.ramirez@estudiante.palestra.cl", "+56982345609"),
            ]

            perfiles_estudiantes: list[PerfilEstudiante] = []
            for idx, (rut, nombres, apellidos, carrera, correo, fono) in enumerate(datos_estudiantes, start=1):
                u_est, creado = Usuario.objects.get_or_create(
                    email=correo,
                    defaults={
                        "username": f"estudiante_{idx}",
                        "first_name": nombres,
                        "last_name": apellidos,
                        "rol": Usuario.ROL_ESTUDIANTE,
                        "activo": True,
                    },
                )
                if creado:
                    u_est.set_password(CONTRASENA_DEMO)
                    u_est.save()

                perfil_est, _ = PerfilEstudiante.objects.update_or_create(
                    usuario=u_est,
                    defaults={
                        "rut": rut,
                        "nombres": nombres,
                        "apellidos": apellidos,
                        "curso_o_carrera": carrera,
                        "telefono": fono,
                        "activo": True,
                    },
                )
                perfiles_estudiantes.append(perfil_est)

            # 5. Inscripciones de estudiantes en disciplinas
            mapa_inscripciones = [
                (0, [0, 2]),        # Catalina: Futbol y Atletismo
                (1, [0, 1]),        # Matias: Futbol y Basquetbol
                (2, [2, 4]),        # Javiera: Atletismo y Natacion
                (3, [0, 3]),        # Sebastian: Futbol y Voleibol
                (4, [1, 3]),        # Francisca: Basquetbol y Voleibol
                (5, [0, 2]),        # Diego: Futbol y Atletismo
                (6, [2, 4]),        # Constanza: Atletismo y Natacion
                (7, [1, 3]),        # Nicolas: Basquetbol y Voleibol
                (8, [4]),           # Antonia: Natacion
            ]
            for est_idx, disc_indices in mapa_inscripciones:
                estudiante = perfiles_estudiantes[est_idx]
                for d_idx in disc_indices:
                    disciplina = disciplinas_creadas[d_idx]
                    Inscripcion.objects.get_or_create(
                        estudiante=estudiante,
                        disciplina=disciplina,
                        estado=Inscripcion.ESTADO_ACTIVA,
                        defaults={
                            "fecha_inscripcion": timezone.localdate() - timedelta(days=30),
                        },
                    )

            # 6. Sesiones de entrenamiento con asistencia y evaluaciones
            hoy = timezone.localdate()
            fechas_sesiones = [
                hoy - timedelta(days=14),
                hoy - timedelta(days=7),
                hoy - timedelta(days=2),
            ]

            for d_idx, disciplina in enumerate(disciplinas_creadas[:3]):
                entrenador = perfiles_entrenadores[0 if d_idx in (0, 1) else 1]
                inscritos = [
                    i.estudiante
                    for i in Inscripcion.objects.filter(
                        disciplina=disciplina,
                        estado=Inscripcion.ESTADO_ACTIVA,
                    ).select_related("estudiante")
                ]

                for s_idx, fecha_ses in enumerate(fechas_sesiones):
                    sesion, _ = SesionEntrenamiento.objects.update_or_create(
                        disciplina=disciplina,
                        fecha=fecha_ses,
                        defaults={
                            "entrenador": entrenador,
                            "tema": f"Sesión técnica y control físico #{s_idx + 1}",
                        },
                    )
                    for e_idx, estudiante in enumerate(inscritos):
                        estado_asist = (
                            Asistencia.ESTADO_PRESENTE
                            if (e_idx + s_idx) % 4 != 0
                            else (
                                Asistencia.ESTADO_JUSTIFICADO
                                if s_idx == 1
                                else Asistencia.ESTADO_AUSENTE
                            )
                        )
                        Asistencia.objects.update_or_create(
                            sesion=sesion,
                            estudiante=estudiante,
                            defaults={
                                "estado": estado_asist,
                                "observacion": "Participación puntual" if estado_asist == "presente" else "Registro verificado",
                                "registrado_por": entrenador.usuario,
                            },
                        )

                        nota_base = Decimal("5.4") + Decimal(str(((e_idx + s_idx) % 4) * 0.4))
                        nota_final = min(Decimal("7.0"), nota_base)
                        Evaluacion.objects.update_or_create(
                            sesion=sesion,
                            estudiante=estudiante,
                            defaults={
                                "puntaje": nota_final,
                                "observacion": "Buen desempeño técnico en la sesión.",
                                "registrado_por": entrenador.usuario,
                            },
                        )

            registrar_evento_auditoria(
                usuario=coordinador,
                accion="carga_datos_demo",
                entidad="Sistema",
                identificador="seed_inicial",
                detalle={"estudiantes": len(perfiles_estudiantes), "disciplinas": len(disciplinas_creadas)},
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Datos de demostración cargados exitosamente: 1 coordinador, "
                "2 entrenadores, 9 estudiantes, 5 disciplinas, inscripciones y sesiones."
            )
        )
