"""Formularios de autenticacion, activacion de cuenta y cambio de contrasena."""
from typing import Any
from django import forms
from django.contrib.auth import authenticate, password_validation
from django.contrib.auth.forms import PasswordChangeForm, PasswordResetForm, SetPasswordForm
from .models import Usuario


CLASES_INPUT_PALESTRA = (
    "form-control w-full rounded border border-palestra-borde bg-white px-3 py-2 "
    "text-palestra-texto focus:border-palestra-primario-500 focus:outline-none"
)


class FormularioInicioSesion(forms.Form):
    """Formulario de inicio de sesion por correo institucional o RUT chileno."""

    identificador = forms.CharField(
        label="Correo institucional o RUT",
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": CLASES_INPUT_PALESTRA,
                "placeholder": "nombre@institucion.cl o 12.345.678-5",
                "autocomplete": "username",
                "autofocus": True,
            }
        ),
        error_messages={
            "required": "Ingrese su correo institucional o RUT.",
        },
    )
    contrasena = forms.CharField(
        label="Contraseña",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": CLASES_INPUT_PALESTRA,
                "placeholder": "Ingrese su contraseña",
                "autocomplete": "current-password",
            }
        ),
        error_messages={
            "required": "Ingrese su contraseña.",
        },
    )

    mensaje_error_generico = (
        "Las credenciales ingresadas no son válidas o la cuenta no se encuentra activa."
    )

    def __init__(self, request: Any = None, *args: Any, **kwargs: Any) -> None:
        self.request = request
        self.usuario_autenticado: Usuario | None = None
        super().__init__(*args, **kwargs)

    def clean(self) -> dict[str, Any]:
        datos = super().clean()
        identificador = datos.get("identificador")
        contrasena = datos.get("contrasena")

        if identificador and contrasena:
            self.usuario_autenticado = authenticate(
                self.request,
                username=identificador,
                password=contrasena,
            )
            if self.usuario_autenticado is None:
                raise forms.ValidationError(
                    self.mensaje_error_generico,
                    code="credenciales_invalidas",
                )
            if not self.usuario_autenticado.activo or not self.usuario_autenticado.is_active:
                raise forms.ValidationError(
                    self.mensaje_error_generico,
                    code="cuenta_inactiva",
                )
        return datos

    def obtener_usuario(self) -> Usuario | None:
        return self.usuario_autenticado


class FormularioDefinirContrasena(SetPasswordForm):
    """Formulario para activacion de cuenta y restablecimiento de contrasena."""

    new_password1 = forms.CharField(
        label="Nueva contraseña",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": CLASES_INPUT_PALESTRA,
                "autocomplete": "new-password",
                "placeholder": "Mínimo 12 caracteres",
            }
        ),
        help_text=password_validation.password_validators_help_text_html(),
    )
    new_password2 = forms.CharField(
        label="Confirmar nueva contraseña",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": CLASES_INPUT_PALESTRA,
                "autocomplete": "new-password",
                "placeholder": "Repita la nueva contraseña",
            }
        ),
    )

    error_messages = {
        "password_mismatch": "Las contraseñas ingresadas no coinciden.",
    }


class FormularioCambioContrasena(PasswordChangeForm):
    """Formulario de cambio de contrasena para usuarios autenticados."""

    old_password = forms.CharField(
        label="Contraseña actual",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": CLASES_INPUT_PALESTRA,
                "autocomplete": "current-password",
                "placeholder": "Ingrese su contraseña actual",
            }
        ),
    )
    new_password1 = forms.CharField(
        label="Nueva contraseña",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": CLASES_INPUT_PALESTRA,
                "autocomplete": "new-password",
                "placeholder": "Mínimo 12 caracteres (mayúsculas, minúsculas y números)",
            }
        ),
    )
    new_password2 = forms.CharField(
        label="Confirmar nueva contraseña",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": CLASES_INPUT_PALESTRA,
                "autocomplete": "new-password",
                "placeholder": "Repita su nueva contraseña",
            }
        ),
    )

    error_messages = {
        "password_incorrect": "Su contraseña actual no es correcta.",
        "password_mismatch": "Las contraseñas nuevas no coinciden.",
    }


class FormularioRecuperarContrasena(PasswordResetForm):
    """Formulario de solicitud de recuperacion de contrasena por correo."""

    email = forms.EmailField(
        label="Correo institucional",
        max_length=254,
        widget=forms.EmailInput(
            attrs={
                "class": CLASES_INPUT_PALESTRA,
                "autocomplete": "email",
                "placeholder": "usuario@institucion.cl",
            }
        ),
    )

    def get_users(self, email: str):
        usuarios_activos = Usuario.objects.filter(
            email__iexact=email.strip(),
            activo=True,
            is_active=True,
        )
        return (u for u in usuarios_activos if u.has_usable_password())
