"""
Serializadores de la API RESTful v1 de PALESTRA (Seccion 9).
Aplica validacion estricta y nunca expone hashes de contrasenas, tokens ni indices ciegos.
"""
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from rest_framework import serializers
from apps.deportes.models import (
    Disciplina,
    Inscripcion,
    PerfilEntrenador,
    PerfilEstudiante,
)
from apps.seguimiento.models import Asistencia, Evaluacion, SesionEntrenamiento


class DisciplinaSerializador(serializers.ModelSerializer):
    inscritos_activos = serializers.IntegerField(
        source="inscritos_activos_count", read_only=True
    )
    cupos_disponibles = serializers.IntegerField(read_only=True)
    porcentaje_ocupacion = serializers.FloatField(read_only=True)

    class Meta:
        model = Disciplina
        fields = [
            "id",
            "nombre",
            "descripcion",
            "cupo_maximo",
            "dia",
            "hora_inicio",
            "hora_termino",
            "lugar",
            "activo",
            "inscritos_activos",
            "cupos_disponibles",
            "porcentaje_ocupacion",
            "creado_en",
            "actualizado_en",
        ]
        read_only_fields = ["id", "creado_en", "actualizado_en"]

    def validate(self, attrs: dict) -> dict:
        cupo = attrs.get(
            "cupo_maximo", getattr(self.instance, "cupo_maximo", 1)
        )
        h_ini = attrs.get(
            "hora_inicio", getattr(self.instance, "hora_inicio", None)
        )
        h_fin = attrs.get(
            "hora_termino", getattr(self.instance, "hora_termino", None)
        )
        if cupo is not None and cupo <= 0:
            raise serializers.ValidationError(
                {"cupo_maximo": "El cupo máximo debe ser mayor a cero."}
            )
        if h_ini and h_fin and h_fin <= h_ini:
            raise serializers.ValidationError(
                {"hora_termino": "La hora de término debe ser posterior a la hora de inicio."}
            )
        return attrs


class PerfilEntrenadorSerializador(serializers.ModelSerializer):
    correo = serializers.EmailField(source="usuario.email", read_only=True)
    rut_formateado = serializers.CharField(read_only=True)

    class Meta:
        model = PerfilEntrenador
        fields = [
            "id",
            "rut_formateado",
            "nombres",
            "apellidos",
            "correo",
            "especialidad",
            "activo",
            "creado_en",
            "actualizado_en",
        ]
        read_only_fields = fields


class PerfilEstudianteSerializador(serializers.ModelSerializer):
    correo = serializers.EmailField(source="usuario.email", read_only=True)
    rut_formateado = serializers.CharField(read_only=True)

    class Meta:
        model = PerfilEstudiante
        fields = [
            "id",
            "rut_formateado",
            "nombres",
            "apellidos",
            "curso_o_carrera",
            "correo",
            "activo",
            "creado_en",
            "actualizado_en",
        ]
        read_only_fields = fields


class InscripcionSerializador(serializers.ModelSerializer):
    estudiante_nombre = serializers.CharField(
        source="estudiante.nombre_completo", read_only=True
    )
    disciplina_nombre = serializers.CharField(
        source="disciplina.nombre", read_only=True
    )

    class Meta:
        model = Inscripcion
        fields = [
            "id",
            "estudiante",
            "estudiante_nombre",
            "disciplina",
            "disciplina_nombre",
            "fecha_inscripcion",
            "estado",
            "fecha_baja",
            "creado_en",
            "actualizado_en",
        ]
        read_only_fields = [
            "id",
            "fecha_inscripcion",
            "fecha_baja",
            "creado_en",
            "actualizado_en",
        ]

    def validate(self, attrs: dict) -> dict:
        estudiante = attrs.get("estudiante")
        disciplina = attrs.get("disciplina")
        if self.instance is None and estudiante and disciplina:
            if not estudiante.activo:
                raise serializers.ValidationError(
                    {"estudiante": "El estudiante debe encontrarse activo."}
                )
            if not disciplina.activo:
                raise serializers.ValidationError(
                    {"disciplina": "La disciplina debe encontrarse activa."}
                )
            if Inscripcion.objects.filter(
                estudiante=estudiante,
                disciplina=disciplina,
                estado=Inscripcion.ESTADO_ACTIVA,
            ).exists():
                raise serializers.ValidationError(
                    "El estudiante ya cuenta con una inscripción activa en esta disciplina."
                )
            if disciplina.cupos_disponibles <= 0:
                raise serializers.ValidationError(
                    "La disciplina seleccionada no dispone de cupos vacantes."
                )
        return attrs


class SesionEntrenamientoSerializador(serializers.ModelSerializer):
    disciplina_nombre = serializers.CharField(
        source="disciplina.nombre", read_only=True
    )
    entrenador_nombre = serializers.CharField(
        source="entrenador.nombre_completo", read_only=True
    )
    editable = serializers.BooleanField(
        source="esta_dentro_ventana_correccion", read_only=True
    )

    class Meta:
        model = SesionEntrenamiento
        fields = [
            "id",
            "disciplina",
            "disciplina_nombre",
            "fecha",
            "entrenador",
            "entrenador_nombre",
            "tema",
            "editable",
            "creado_en",
            "actualizado_en",
        ]
        read_only_fields = ["id", "entrenador", "creado_en", "actualizado_en"]

    def validate_fecha(self, valor):
        if valor > timezone.localdate():
            raise serializers.ValidationError(
                "No se permite registrar sesiones con fechas futuras."
            )
        return valor


class AsistenciaSerializador(serializers.ModelSerializer):
    estudiante_nombre = serializers.CharField(
        source="estudiante.nombre_completo", read_only=True
    )
    disciplina_nombre = serializers.CharField(
        source="sesion.disciplina.nombre", read_only=True
    )
    fecha_sesion = serializers.DateField(source="sesion.fecha", read_only=True)

    class Meta:
        model = Asistencia
        fields = [
            "id",
            "sesion",
            "fecha_sesion",
            "disciplina_nombre",
            "estudiante",
            "estudiante_nombre",
            "estado",
            "observacion",
            "creado_en",
            "actualizado_en",
        ]
        read_only_fields = ["id", "creado_en", "actualizado_en"]


class EvaluacionSerializador(serializers.ModelSerializer):
    estudiante_nombre = serializers.CharField(
        source="estudiante.nombre_completo", read_only=True
    )
    disciplina_nombre = serializers.CharField(
        source="sesion.disciplina.nombre", read_only=True
    )
    fecha_sesion = serializers.DateField(source="sesion.fecha", read_only=True)

    class Meta:
        model = Evaluacion
        fields = [
            "id",
            "sesion",
            "fecha_sesion",
            "disciplina_nombre",
            "estudiante",
            "estudiante_nombre",
            "puntaje",
            "observacion",
            "creado_en",
            "actualizado_en",
        ]
        read_only_fields = ["id", "creado_en", "actualizado_en"]

    def validate_puntaje(self, valor: Decimal) -> Decimal:
        nota_min = Decimal(str(getattr(settings, "ESCALA_NOTAS_MINIMA", "1.0")))
        nota_max = Decimal(str(getattr(settings, "ESCALA_NOTAS_MAXIMA", "7.0")))
        if valor < nota_min or valor > nota_max:
            raise serializers.ValidationError(
                f"El puntaje debe estar entre {nota_min} y {nota_max}."
            )
        return valor
