"""
Modelos relacionales normalizados (3FN) del modulo deportes:
- PerfilEstudiante (cifrado de RUT y telefono + indice ciego HMAC-SHA256)
- PerfilEntrenador (cifrado de RUT y telefono + indice ciego HMAC-SHA256)
- Disciplina (restricciones CHECK de cupo > 0 y hora_termino > hora_inicio)
- EntrenadorDisciplina (unico por par entrenador + disciplina)
- Inscripcion (baja logica y restriccion UNIQUE parcial para estado='activa')
"""
import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from apps.cuentas.campos import (
    CampoCifrado,
    calcular_indice_ciego_rut,
    formatear_rut_chileno,
)
from apps.cuentas.validadores import validar_rut_chileno


class PerfilEstudiante(models.Model):
    """Perfil de un estudiante con datos personales sensibles cifrados en reposo."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="Identificador",
    )
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="perfil_estudiante",
        verbose_name="Cuenta de usuario",
    )
    rut = CampoCifrado(
        verbose_name="RUT (cifrado en reposo)",
    )
    rut_indice_ciego = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        editable=False,
        verbose_name="Indice ciego HMAC del RUT",
        error_messages={
            "unique": "Ya existe un estudiante registrado con este RUT."
        },
    )
    nombres = models.CharField(
        max_length=100,
        verbose_name="Nombres",
    )
    apellidos = models.CharField(
        max_length=100,
        verbose_name="Apellidos",
    )
    curso_o_carrera = models.CharField(
        max_length=120,
        verbose_name="Curso o carrera",
    )
    telefono = CampoCifrado(
        blank=True,
        default="",
        verbose_name="Telefono de contacto (cifrado)",
    )
    activo = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Estado activo",
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
        db_table = "perfil_estudiante"
        verbose_name = "Perfil de Estudiante"
        verbose_name_plural = "Perfiles de Estudiantes"
        ordering = ["apellidos", "nombres"]
        indexes = [
            models.Index(fields=["activo", "apellidos"], name="idx_estudiante_activo_ape"),
        ]

    def clean(self) -> None:
        super().clean()
        if self.rut:
            rut_canonico = validar_rut_chileno(self.rut)
            self.rut = rut_canonico
            self.rut_indice_ciego = calcular_indice_ciego_rut(rut_canonico)
            duplicado = (
                PerfilEstudiante.objects.filter(rut_indice_ciego=self.rut_indice_ciego)
                .exclude(pk=self.pk)
                .exists()
            )
            if duplicado:
                raise ValidationError(
                    {"rut": "Ya existe un estudiante registrado con este RUT."}
                )

    def save(self, *args, **kwargs) -> None:
        if self.rut:
            rut_canonico = validar_rut_chileno(self.rut)
            self.rut = rut_canonico
            self.rut_indice_ciego = calcular_indice_ciego_rut(rut_canonico)
        super().save(*args, **kwargs)

    @property
    def rut_formateado(self) -> str:
        return formatear_rut_chileno(self.rut)

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombres} {self.apellidos}".strip()

    def __str__(self) -> str:
        return f"{self.nombre_completo} ({self.rut_formateado})"


class PerfilEntrenador(models.Model):
    """Perfil de un entrenador deportivo con RUT y telefono cifrados en reposo."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="Identificador",
    )
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="perfil_entrenador",
        verbose_name="Cuenta de usuario",
    )
    rut = CampoCifrado(
        verbose_name="RUT (cifrado en reposo)",
    )
    rut_indice_ciego = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        editable=False,
        verbose_name="Indice ciego HMAC del RUT",
        error_messages={
            "unique": "Ya existe un entrenador registrado con este RUT."
        },
    )
    nombres = models.CharField(
        max_length=100,
        verbose_name="Nombres",
    )
    apellidos = models.CharField(
        max_length=100,
        verbose_name="Apellidos",
    )
    especialidad = models.CharField(
        max_length=120,
        verbose_name="Especialidad deportiva",
    )
    telefono = CampoCifrado(
        blank=True,
        default="",
        verbose_name="Telefono de contacto (cifrado)",
    )
    activo = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Estado activo",
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
        db_table = "perfil_entrenador"
        verbose_name = "Perfil de Entrenador"
        verbose_name_plural = "Perfiles de Entrenadores"
        ordering = ["apellidos", "nombres"]
        indexes = [
            models.Index(fields=["activo", "apellidos"], name="idx_entrenador_activo_ape"),
        ]

    def clean(self) -> None:
        super().clean()
        if self.rut:
            rut_canonico = validar_rut_chileno(self.rut)
            self.rut = rut_canonico
            self.rut_indice_ciego = calcular_indice_ciego_rut(rut_canonico)
            duplicado = (
                PerfilEntrenador.objects.filter(rut_indice_ciego=self.rut_indice_ciego)
                .exclude(pk=self.pk)
                .exists()
            )
            if duplicado:
                raise ValidationError(
                    {"rut": "Ya existe un entrenador registrado con este RUT."}
                )

    def save(self, *args, **kwargs) -> None:
        if self.rut:
            rut_canonico = validar_rut_chileno(self.rut)
            self.rut = rut_canonico
            self.rut_indice_ciego = calcular_indice_ciego_rut(rut_canonico)
        super().save(*args, **kwargs)

    @property
    def rut_formateado(self) -> str:
        return formatear_rut_chileno(self.rut)

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombres} {self.apellidos}".strip()

    def __str__(self) -> str:
        return f"{self.nombre_completo} - {self.especialidad}"


class Disciplina(models.Model):
    """Disciplina deportiva ofrecida por la institucion."""

    DIA_LUNES = "Lunes"
    DIA_MARTES = "Martes"
    DIA_MIERCOLES = "Miercoles"
    DIA_JUEVES = "Jueves"
    DIA_VIERNES = "Viernes"
    DIA_SABADO = "Sabado"

    OPCIONES_DIA = [
        (DIA_LUNES, "Lunes"),
        (DIA_MARTES, "Martes"),
        (DIA_MIERCOLES, "Miércoles"),
        (DIA_JUEVES, "Jueves"),
        (DIA_VIERNES, "Viernes"),
        (DIA_SABADO, "Sábado"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="Identificador",
    )
    nombre = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nombre de la disciplina",
        error_messages={
            "unique": "Ya existe una disciplina registrada con este nombre."
        },
    )
    descripcion = models.TextField(
        verbose_name="Descripcion",
    )
    cupo_maximo = models.PositiveIntegerField(
        verbose_name="Cupo maximo de estudiantes",
    )
    dia = models.CharField(
        max_length=20,
        choices=OPCIONES_DIA,
        verbose_name="Dia de entrenamiento",
    )
    hora_inicio = models.TimeField(
        verbose_name="Hora de inicio",
    )
    hora_termino = models.TimeField(
        verbose_name="Hora de termino",
    )
    lugar = models.CharField(
        max_length=120,
        verbose_name="Lugar o recinto",
    )
    activo = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Estado activo",
    )
    entrenadores = models.ManyToManyField(
        PerfilEntrenador,
        through="EntrenadorDisciplina",
        related_name="disciplinas",
        verbose_name="Entrenadores asignados",
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
        db_table = "disciplina"
        verbose_name = "Disciplina Deportiva"
        verbose_name_plural = "Disciplinas Deportivas"
        ordering = ["nombre"]
        constraints = [
            models.CheckConstraint(
                condition=Q(cupo_maximo__gt=0),
                name="chk_disciplina_cupo_positivo",
            ),
            models.CheckConstraint(
                condition=Q(hora_termino__gt=F("hora_inicio")),
                name="chk_disciplina_horario_coherente",
            ),
        ]
        indexes = [
            models.Index(fields=["activo", "nombre"], name="idx_disciplina_activo_nom"),
        ]

    def clean(self) -> None:
        super().clean()
        if self.cupo_maximo is not None and self.cupo_maximo <= 0:
            raise ValidationError(
                {"cupo_maximo": "El cupo maximo debe ser mayor a cero."}
            )
        if self.hora_inicio and self.hora_termino and self.hora_termino <= self.hora_inicio:
            raise ValidationError(
                {"hora_termino": "La hora de termino debe ser posterior a la hora de inicio."}
            )

    @property
    def inscritos_activos_count(self) -> int:
        return self.inscripciones.filter(
            estado=Inscripcion.ESTADO_ACTIVA,
            estudiante__activo=True,
        ).count()

    @property
    def cupos_disponibles(self) -> int:
        return max(0, self.cupo_maximo - self.inscritos_activos_count)

    @property
    def porcentaje_ocupacion(self) -> float:
        if not self.cupo_maximo:
            return 0.0
        return round((self.inscritos_activos_count / self.cupo_maximo) * 100.0, 1)

    @property
    def horario_formateado(self) -> str:
        return f"{self.get_dia_display()} {self.hora_inicio:%H:%M} a {self.hora_termino:%H:%M}"

    def __str__(self) -> str:
        return f"{self.nombre} ({self.horario_formateado})"


class EntrenadorDisciplina(models.Model):
    """Asignacion muchos-a-muchos entre Entrenador y Disciplina."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="Identificador",
    )
    entrenador = models.ForeignKey(
        PerfilEntrenador,
        on_delete=models.PROTECT,
        related_name="asignaciones_disciplina",
        verbose_name="Entrenador",
    )
    disciplina = models.ForeignKey(
        Disciplina,
        on_delete=models.PROTECT,
        related_name="asignaciones_entrenador",
        verbose_name="Disciplina",
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
        db_table = "entrenador_disciplina"
        verbose_name = "Asignacion Entrenador-Disciplina"
        verbose_name_plural = "Asignaciones Entrenador-Disciplina"
        constraints = [
            models.UniqueConstraint(
                fields=["entrenador", "disciplina"],
                name="uq_entrenador_disciplina_par",
            )
        ]
        indexes = [
            models.Index(
                fields=["entrenador", "disciplina"],
                name="idx_ent_disc_par",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.entrenador.nombre_completo} -> {self.disciplina.nombre}"


class Inscripcion(models.Model):
    """
    Inscripcion de un estudiante en una disciplina deportiva.
    Soporta baja logica conservando el historial y garantiza unicidad de inscripcion
    activa por par (estudiante, disciplina) a nivel de base de datos.
    """

    ESTADO_ACTIVA = "activa"
    ESTADO_BAJA = "baja"

    OPCIONES_ESTADO = [
        (ESTADO_ACTIVA, "Activa"),
        (ESTADO_BAJA, "Baja"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="Identificador",
    )
    estudiante = models.ForeignKey(
        PerfilEstudiante,
        on_delete=models.PROTECT,
        related_name="inscripciones",
        verbose_name="Estudiante",
    )
    disciplina = models.ForeignKey(
        Disciplina,
        on_delete=models.PROTECT,
        related_name="inscripciones",
        verbose_name="Disciplina",
    )
    fecha_inscripcion = models.DateField(
        default=timezone.localdate,
        verbose_name="Fecha de inscripcion",
    )
    estado = models.CharField(
        max_length=15,
        choices=OPCIONES_ESTADO,
        default=ESTADO_ACTIVA,
        db_index=True,
        verbose_name="Estado de la inscripcion",
    )
    fecha_baja = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha de baja",
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
        db_table = "inscripcion"
        verbose_name = "Inscripcion"
        verbose_name_plural = "Inscripciones"
        ordering = ["-fecha_inscripcion", "-creado_en"]
        constraints = [
            models.UniqueConstraint(
                fields=["estudiante", "disciplina"],
                condition=Q(estado="activa"),
                name="uq_inscripcion_estudiante_disciplina_activa",
            )
        ]
        indexes = [
            models.Index(
                fields=["disciplina", "estado"],
                name="idx_inscripcion_disc_estado",
            ),
            models.Index(
                fields=["estudiante", "estado"],
                name="idx_inscripcion_est_estado",
            ),
        ]

    def dar_de_baja(self) -> None:
        """Aplica baja logica a la inscripcion conservando todo su historial."""
        self.estado = self.ESTADO_BAJA
        self.fecha_baja = timezone.localdate()
        self.save(update_fields=["estado", "fecha_baja", "actualizado_en"])

    def __str__(self) -> str:
        return f"{self.estudiante.nombre_completo} en {self.disciplina.nombre} ({self.get_estado_display()})"
