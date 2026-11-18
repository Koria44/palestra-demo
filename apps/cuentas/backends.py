"""
Backend de autenticacion que permite iniciar sesion con correo institucional o RUT chileno.
Cumple con tiempo de respuesta uniforme contra enumeracion de usuarios (Seccion 6.1.A).
"""
from typing import Any
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.hashers import make_password
from django.http import HttpRequest
from .campos import calcular_indice_ciego_rut, normalizar_rut
from .models import Usuario


class AutenticacionCorreoORutBackend(ModelBackend):
    """
    Permite autenticar a un usuario ingresando:
    1) Su correo institucional (email), o
    2) Su RUT chileno (buscando por el indice ciego HMAC-SHA256 en PerfilEstudiante o PerfilEntrenador), o
    3) Su nombre de usuario (username).
    """

    def authenticate(
        self,
        request: HttpRequest | None,
        username: str | None = None,
        password: str | None = None,
        **kwargs: Any,
    ) -> Usuario | None:
        identificador = (username or kwargs.get("identificador") or "").strip()
        if not identificador or not password:
            return None

        usuario = self._buscar_usuario(identificador)
        if usuario is None:
            # Ejecuta hash ficticio en tiempo constante para mitigar ataques de temporizacion
            make_password(password)
            return None

        if usuario.check_password(password) and self.user_can_authenticate(usuario):
            return usuario
        return None

    def user_can_authenticate(self, user: Any) -> bool:
        es_activo = getattr(user, "activo", True) and getattr(user, "is_active", True)
        return bool(es_activo)

    def _buscar_usuario(self, identificador: str) -> Usuario | None:
        # 1. Busqueda por correo institucional
        if "@" in identificador:
            return Usuario.objects.filter(email__iexact=identificador).first()

        # 2. Busqueda por RUT mediante indice ciego HMAC-SHA256
        rut_canonico = normalizar_rut(identificador)
        if "-" in rut_canonico:
            indice_ciego = calcular_indice_ciego_rut(rut_canonico)
            from apps.deportes.models import PerfilEntrenador, PerfilEstudiante

            perfil_est = (
                PerfilEstudiante.objects.select_related("usuario")
                .filter(rut_indice_ciego=indice_ciego)
                .first()
            )
            if perfil_est:
                return perfil_est.usuario

            perfil_ent = (
                PerfilEntrenador.objects.select_related("usuario")
                .filter(rut_indice_ciego=indice_ciego)
                .first()
            )
            if perfil_ent:
                return perfil_ent.usuario

        # 3. Busqueda por username
        return Usuario.objects.filter(username__iexact=identificador).first()
