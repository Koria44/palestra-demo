"""
Modelos relacionales (3FN) del modulo seguimiento:
- SesionEntrenamiento (unica por disciplina + fecha, prohibe fechas futuras)
- Asistencia (unica por sesion + estudiante, ventana de correccion de 7 dias)
- Evaluacion (unica por sesion + estudiante, escala chilena 1.0 a 7.0 con CHECK en BD)
"""
from datetime import timedelta
from decimal import Decimal
import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
from apps.deportes.models import Disciplina, PerfilEntrenador, PerfilEstudiante


class SesionEntrenamiento(models.Model):
    """Sesion de entrenamiento realizada en una fecha especifica para una disciplina."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="Identificador",
    )
    disciplina = models.ForeignKey(
        Disciplina,
        on_delete=models.PROTECT,
        related_name="sesiones",
        verbose_name="Disciplina",
    )
    fecha = models.DateField(
        db_index=True,
        verbose_name="Fecha de la sesion",
    )
    entrenador = models.ForeignKey(
        PerfilEntrenador,
        on_delete=models.PROTECT,
        related_name="sesiones_registradas",
        verbose_name="Entrenador que registra",
    )
    tema = models.CharField(
        max_length=160,
        blank=True,
        default="",
        verbose_name="Tema o contenido de la sesion",
    )
    creado_en = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Creado en",
    )
    actualizado_en = models.DateTimeField(
        auto_now=True,
        verbose_name="Actualizado en",
    )

    class Meta:
        db_table = "sesion_entrenamiento"
        verbose_name = "Sesion de Entrenamiento"
        verbose_name_plural = "Sesiones de Entrenamiento"
        ordering = ["-fecha", "-creado_en"]
        constraints = [
            models.UniqueConstraint(
                fields=["disciplina", "fecha"],
                name="uq_sesion_disciplina_fecha",
            )
        ]
        indexes = [
            models.Index(
                fields=["disciplina", "fecha"],
                name="idx_sesion_disc_fecha",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.fecha and self.fecha > timezone.localdate():
            raise ValidationError(
                {"fecha": "No se permite registrar sesiones con fechas futuras."}
            )
        if self.disciplina_id and self.fecha:
            duplicada = (
                SesionEntrenamiento.objects.filter(
                    disciplina_id=self.disciplina_id,
                    fecha=self.fecha,
                )
                .exclude(pk=self.pk)
                .exists()
            )
            if duplicada:
                raise ValidationError(
                    {"fecha": "Ya existe una sesion registrada para esta disciplina en la fecha seleccionada."}
                )

    def esta_dentro_ventana_correccion(self) -> bool:
        """
        Verifica si la sesion se encuentra dentro de la ventana de edicion permitida
        (por defecto 7 dias desde la fecha de la sesion o creacion).
        """
        dias_ventana = int(getattr(settings, "DIAS_VENTANA_CORRECCION", 7))
        hoy = timezone.localdate()
        return (hoy - self.fecha) <= timedelta(days=dias_ventana)

    def __str__(self) -> str:
        return f"{self.disciplina.nombre} - {self.fecha:%d/%m/%Y}"


class Asistencia(models.Model):
    """Registro de asistencia de un estudiante a una sesion de entrenamiento."""

    ESTADO_PRESENTE = "presente"
    ESTADO_AUSENTE = "ausente"
    ESTADO_JUSTIFICADO = "justificado"

    OPCIONES_ESTADO = [
        (ESTADO_PRESENTE, "Presente"),
        (ESTADO_AUSENTE, "Ausente"),
        (ESTADO_JUSTIFICADO, "Justificado"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="Identificador",
    )
    sesion = models.ForeignKey(
        SesionEntrenamiento,
        on_delete=models.PROTECT,
        related_name="asistencias",
        verbose_name="Sesion de entrenamiento",
    )
    estudiante = models.ForeignKey(
        PerfilEstudiante,
        on_delete=models.PROTECT,
        related_name="asistencias",
        verbose_name="Estudiante",
    )
    estado = models.CharField(
        max_length=15,
        choices=OPCIONES_ESTADO,
        default=ESTADO_PRESENTE,
        db_index=True,
        verbose_name="Estado de asistencia",
    )
    observacion = models.CharField(
        max_length=250,
        blank=True,
        default="",
        verbose_name="Observacion breve",
    )
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="asistencias_registradas",
        verbose_name="Registrado por",
    )
    creado_en = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Creado en",
    )
    actualizado_en = models.DateTimeField(
        auto_now=True,
        verbose_name="Actualizado en",
    )

    class Meta:
        db_table = "asistencia"
        verbose_name = "Asistencia"
        verbose_name_plural = "Asistencias"
        ordering = ["-sesion__fecha", "estudiante__apellidos"]
        constraints = [
            models.UniqueConstraint(
                fields=["sesion", "estudiante"],
                name="uq_asistencia_sesion_estudiante",
            )
        ]
        indexes = [
            models.Index(
                fields=["estudiante", "estado"],
                name="idx_asistencia_est_estado",
            ),
            models.Index(
                fields=["sesion", "estado"],
                name="idx_asistencia_ses_estado",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.estudiante.nombre_completo} - {self.sesion}: {self.get_estado_display()}"


class Evaluacion(models.Model):
    """
    Registro de puntaje o evaluacion de rendimiento por sesion de entrenamiento.
    Escala numerica chilena (1.0 a 7.0, configurable en settings).
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="Identificador",
    )
    sesion = models.ForeignKey(
        SesionEntrenamiento,
        on_delete=models.PROTECT,
        related_name="evaluaciones",
        verbose_name="Sesion de entrenamiento",
    )
    estudiante = models.ForeignKey(
        PerfilEstudiante,
        on_delete=models.PROTECT,
        related_name="evaluaciones",
        verbose_name="Estudiante",
    )
    puntaje = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        verbose_name="Puntaje (escala 1,0 a 7,0)",
    )
    observacion = models.CharField(
        max_length=250,
        blank=True,
        default="",
        verbose_name="Observacion breve",
    )
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="evaluaciones_registradas",
        verbose_name="Registrado por",
    )
    creado_en = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Creado en",
    )
    actualizado_en = models.DateTimeField(
        auto_now=True,
        verbose_name="Actualizado en",
    )

    class Meta:
        db_table = "evaluacion"
        verbose_name = "Evaluacion de Rendimiento"
        verbose_name_plural = "Evaluaciones de Rendimiento"
        ordering = ["-sesion__fecha", "estudiante__apellidos"]
        constraints = [
            models.UniqueConstraint(
                fields=["sesion", "estudiante"],
                name="uq_evaluacion_sesion_estudiante",
            ),
            models.CheckConstraint(
                condition=Q(puntaje__gte=Decimal("1.0")) & Q(puntaje__lte=Decimal("7.0")),
                name="chk_evaluacion_puntaje_escala_chilena",
            ),
        ]
        indexes = [
            models.Index(
                fields=["estudiante", "puntaje"],
                name="idx_evaluacion_est_puntaje",
            ),
            models.Index(
                fields=["sesion", "estudiante"],
                name="idx_evaluacion_ses_est",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        nota_min = Decimal(str(getattr(settings, "ESCALA_NOTAS_MINIMA", "1.0")))
        nota_max = Decimal(str(getattr(settings, "ESCALA_NOTAS_MAXIMA", "7.0")))
        if self.puntaje is not None:
            if self.puntaje < nota_min or self.puntaje > nota_max:
                raise ValidationError(
                    {
                        "puntaje": (
                            f"El puntaje debe estar entre {str(nota_min).replace('.', ',')} "
                            f"y {str(nota_max).replace('.', ',')}."
                        )
                    }
                )

    def __str__(self) -> str:
        nota_str = f"{self.puntaje:.1f}".replace(".", ",")
        return f"{self.estudiante.nombre_completo} - {self.sesion}: {nota_str}"
