"""
Pruebas unitarias exhaustivas de modelos, validadores (RUT chileno Modulo 11,
puntajes en escala 1.0 a 7.0, cupos y horarios), servicios de reportes,
sanitizacion contra inyeccion de formulas CSV y comandos de gestion (Seccion 10.1).
"""
from datetime import time
from decimal import Decimal
from pathlib import Path
import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
from apps.cuentas.models import Usuario
from apps.cuentas.validadores import validar_rut_chileno
from apps.deportes.models import Disciplina, PerfilEntrenador, PerfilEstudiante
from apps.reportes.servicios import (
    calcular_tendencia_evaluaciones,
    sanitizar_celda_csv,
)
from apps.seguimiento.models import Evaluacion, SesionEntrenamiento


class PruebasUnitariasValidadoresYServicios:
    """Pruebas unitarias de funciones de validacion, calculo y sanitizacion CSV."""

    @pytest.mark.parametrize(
        "rut_entrada,rut_esperado",
        [
            ("14.567.890-0", "14567890-0"),
            ("16234567-2", "16234567-2"),
            ("21.456.789-k", "21456789-K"),
            ("181234563", "18123456-3"),
        ],
    )
    def test_validar_rut_chileno_casos_validos(
        self, rut_entrada: str, rut_esperado: str
    ) -> None:
        assert validar_rut_chileno(rut_entrada) == rut_esperado

    @pytest.mark.parametrize(
        "rut_invalido",
        [
            "",
            "123-4",
            "00.500.123-4",
            "14.567.890-9",
            "21.456.789-0",
        ],
    )
    def test_validar_rut_chileno_casos_invalidos(self, rut_invalido: str) -> None:
        with pytest.raises(ValidationError):
            validar_rut_chileno(rut_invalido)

    @pytest.mark.parametrize(
        "valor_peligroso,esperado",
        [
            ("=cmd|' /C calc'!A0", "'=cmd|' /C calc'!A0"),
            ("+SUM(A1:A10)", "'+SUM(A1:A10)"),
            ("-2+3+cmd", "'-2+3+cmd"),
            ("@SUM(1+1)", "'@SUM(1+1)"),
            ("  =HYPERLINK()", "'  =HYPERLINK()"),
            ("Texto seguro normal", "Texto seguro normal"),
        ],
    )
    def test_sanitizacion_inyeccion_formulas_csv(
        self, valor_peligroso: str, esperado: str
    ) -> None:
        assert sanitizar_celda_csv(valor_peligroso) == esperado

    def test_calculo_tendencia_evaluaciones(self) -> None:
        assert calcular_tendencia_evaluaciones([]) == "Sin evaluaciones"
        assert calcular_tendencia_evaluaciones([5.5]) == "Estable"
        assert calcular_tendencia_evaluaciones([4.5, 4.8, 6.0, 6.5]) == "En alza"
        assert calcular_tendencia_evaluaciones([6.5, 6.2, 4.5, 4.0]) == "En baja"
        assert calcular_tendencia_evaluaciones([5.5, 5.6, 5.5, 5.6]) == "Estable"


@pytest.mark.django_db
class PruebasUnitariasModelosYRestricciones:
    """Pruebas unitarias de reglas de negocio en modelos Disciplina, Sesion y Evaluacion."""

    def test_validacion_cupo_y_horario_en_disciplina(self) -> None:
        disc_cupo_cero = Disciplina(
            nombre="Disciplina Invalida Cupo",
            descripcion="Prueba",
            cupo_maximo=0,
            dia=Disciplina.DIA_LUNES,
            hora_inicio=time(10, 0),
            hora_termino=time(12, 0),
            lugar="Cancha",
        )
        with pytest.raises(ValidationError):
            disc_cupo_cero.clean()

        disc_horario_invertido = Disciplina(
            nombre="Disciplina Horario Invertido",
            descripcion="Prueba",
            cupo_maximo=15,
            dia=Disciplina.DIA_LUNES,
            hora_inicio=time(18, 0),
            hora_termino=time(16, 0),
            lugar="Cancha",
        )
        with pytest.raises(ValidationError):
            disc_horario_invertido.clean()

    def test_validacion_escala_chilena_en_evaluacion(self) -> None:
        u_ent = Usuario.objects.create_user(
            username="ent_u", email="ent_u@palestra.cl", rol=Usuario.ROL_ENTRENADOR
        )
        ent = PerfilEntrenador.objects.create(
            usuario=u_ent,
            rut="14.567.890-0",
            nombres="Juan",
            apellidos="Pérez",
            especialidad="Fútbol",
        )
        u_est = Usuario.objects.create_user(
            username="est_u", email="est_u@palestra.cl", rol=Usuario.ROL_ESTUDIANTE
        )
        est = PerfilEstudiante.objects.create(
            usuario=u_est,
            rut="18.123.456-3",
            nombres="Diego",
            apellidos="Rojas",
            curso_o_carrera="Ingeniería",
        )
        disc = Disciplina.objects.create(
            nombre="Fútbol Sala",
            descripcion="Test",
            cupo_maximo=12,
            dia=Disciplina.DIA_JUEVES,
            hora_inicio=time(14, 0),
            hora_termino=time(16, 0),
            lugar="Gimnasio",
        )
        sesion = SesionEntrenamiento.objects.create(
            disciplina=disc, fecha=timezone.localdate(), entrenador=ent
        )

        # Nota menor a 1.0 falla
        eval_baja = Evaluacion(
            sesion=sesion,
            estudiante=est,
            puntaje=Decimal("0.5"),
            registrado_por=u_ent,
        )
        with pytest.raises(ValidationError):
            eval_baja.clean()

        # Nota mayor a 7.0 falla
        eval_alta = Evaluacion(
            sesion=sesion,
            estudiante=est,
            puntaje=Decimal("7.5"),
            registrado_por=u_ent,
        )
        with pytest.raises(ValidationError):
            eval_alta.clean()

        # Nota 6.5 es valida
        eval_ok = Evaluacion(
            sesion=sesion,
            estudiante=est,
            puntaje=Decimal("6.5"),
            registrado_por=u_ent,
        )
        eval_ok.clean()
        eval_ok.save()
        assert eval_ok.pk is not None

    def test_comandos_gestion_generar_claves_respaldo_y_bloqueo_seed_produccion(
        self, tmp_path: Path, settings
    ) -> None:
        # 1. generar_claves se ejecuta sin error
        call_command("generar_claves")

        # 2. exportar_respaldo cifra y luego descifra verificando integridad
        archivo_enc = tmp_path / "respaldo_test.json.enc"
        call_command("exportar_respaldo", salida=str(archivo_enc))
        assert archivo_enc.exists()
        contenido = archivo_enc.read_text(encoding="utf-8")
        assert contenido.startswith("enc1:")
        call_command("exportar_respaldo", descifrar=str(archivo_enc))

        # 3. cargar_datos_demo se niega a ejecutarse si DEBUG=False (Seccion 12)
        settings.DEBUG = False
        with pytest.raises(CommandError):
            call_command("cargar_datos_demo")
