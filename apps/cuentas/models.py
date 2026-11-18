"""
Modelo de Usuario personalizado y gestion de tokens de activacion de un solo uso.
Cumple con la Seccion 0.1 (nombres en espanol), Seccion 6 y Seccion 7.
"""
import hashlib
import secrets
import uuid
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core import signing
from django.db import models


class Usuario(AbstractUser):
    """
    Usuario del sistema PALESTRA. Hereda de AbstractUser para integrarse con el
    sistema de autenticacion y hash Argon2id de Django, exponiendo atributos
    y tabla en espanol.
    """

    ROL_COORDINADOR = "coordinador"
    ROL_ENTRENADOR = "entrenador"
    ROL_ESTUDIANTE = "estudiante"

    OPCIONES_ROL = [
        (ROL_COORDINADOR, "Coordinador Deportivo"),
        (ROL_ENTRENADOR, "Entrenador"),
        (ROL_ESTUDIANTE, "Estudiante"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="Identificador",
    )
    email = models.EmailField(
        unique=True,
        verbose_name="Correo institucional",
        error_messages={
            "unique": "Ya existe un usuario registrado con este correo institucional."
        },
    )
    rol = models.CharField(
        max_length=20,
        choices=OPCIONES_ROL,
        default=ROL_ESTUDIANTE,
        db_index=True,
        verbose_name="Rol en el sistema",
    )
    debe_cambiar_contrasena = models.BooleanField(
        default=False,
        verbose_name="Debe cambiar contrasena al iniciar sesion",
    )
    activo = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Estado activo",
    )
    ultimo_acceso = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Ultimo acceso",
    )
    # Hash del nonce de activacion vigente para garantizar un solo uso sin guardar el token en claro
    hash_token_activacion = models.CharField(
        max_length=64,
        blank=True,
        default="",
        verbose_name="Hash del token de activacion vigente",
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
        db_table = "usuario"
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        ordering = ["-creado_en"]
        indexes = [
            models.Index(fields=["rol", "activo"], name="idx_usuario_rol_activo"),
        ]

    def save(self, *args, **kwargs) -> None:
        # Mantiene sincronizado is_active de AbstractUser con el campo en espanol 'activo'
        self.is_active = self.activo
        if self.last_login and not self.ultimo_acceso:
            self.ultimo_acceso = self.last_login
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    @property
    def nombre_completo(self) -> str:
        """Retorna el nombre completo desde el perfil o desde los campos base."""
        if hasattr(self, "perfil_estudiante"):
            return f"{self.perfil_estudiante.nombres} {self.perfil_estudiante.apellidos}".strip()
        if hasattr(self, "perfil_entrenador"):
            return f"{self.perfil_entrenador.nombres} {self.perfil_entrenador.apellidos}".strip()
        nombre = f"{self.first_name} {self.last_name}".strip()
        return nombre or self.username

    @property
    def es_coordinador(self) -> bool:
        return self.rol == self.ROL_COORDINADOR

    @property
    def es_entrenador(self) -> bool:
        return self.rol == self.ROL_ENTRENADOR

    @property
    def es_estudiante(self) -> bool:
        return self.rol == self.ROL_ESTUDIANTE

    def generar_token_activacion(self) -> str:
        """
        Genera un token firmado criptograficamente y de un solo uso para que el
        usuario defina su propia contrasena. Nunca almacena el token en claro;
        solo guarda el hash SHA-256 del nonce en hash_token_activacion.
        """
        nonce = secrets.token_urlsafe(24)
        self.hash_token_activacion = hashlib.sha256(nonce.encode("utf-8")).hexdigest()
        self.save(update_fields=["hash_token_activacion", "actualizado_en"])
        carga = {
            "uid": str(self.id),
            "nonce": nonce,
            "pwd_prefix": self.password[:16],
        }
        return signing.dumps(carga, salt="palestra.activacion.cuenta.v1")

    @classmethod
    def validar_token_activacion(
        cls, token: str, max_age_segundos: int | None = None
    ) -> "Usuario | None":
        """
        Verifica firma, expiracion y que el token no haya sido utilizado ni invalidado.
        Retorna el Usuario si es valido o None en caso contrario.
        """
        tiempo_maximo = (
            max_age_segundos
            if max_age_segundos is not None
            else getattr(settings, "TIEMPO_EXPIRACION_ACTIVACION_SEGUNDOS", 86400)
        )
        try:
            datos = signing.loads(
                token,
                salt="palestra.activacion.cuenta.v1",
                max_age=tiempo_maximo,
            )
        except (signing.BadSignature, signing.SignatureExpired):
            return None

        uid = datos.get("uid")
        nonce = datos.get("nonce", "")
        pwd_prefix = datos.get("pwd_prefix", "")
        if not uid or not nonce:
            return None

        try:
            usuario = cls.objects.get(id=uid, activo=True)
        except (cls.DoesNotExist, ValueError):
            return None

        if not usuario.hash_token_activacion:
            return None

        hash_calculado = hashlib.sha256(nonce.encode("utf-8")).hexdigest()
        if not secrets.compare_digest(usuario.hash_token_activacion, hash_calculado):
            return None

        if usuario.password[:16] != pwd_prefix:
            return None

        return usuario

    def consumir_token_activacion(self) -> None:
        """Invalida el token de activacion tras su primer uso exitoso."""
        self.hash_token_activacion = ""
        self.debe_cambiar_contrasena = False
        self.save(
            update_fields=[
                "hash_token_activacion",
                "debe_cambiar_contrasena",
                "actualizado_en",
            ]
        )

    def __str__(self) -> str:
        return f"{self.email} ({self.get_rol_display()})"
