"""Validadores de servidor para RUT chileno (modulo 11) y politicas de contrasenas."""
import re
from typing import Any
from django.core.exceptions import ValidationError
from .campos import normalizar_rut


def calcular_digito_verificador(cuerpo_rut: str) -> str:
    """Calcula el digito verificador de un RUT chileno mediante el algoritmo Modulo 11."""
    suma = 0
    multiplicador = 2
    for digito in reversed(cuerpo_rut):
        suma += int(digito) * multiplicador
        multiplicador = 2 if multiplicador == 7 else multiplicador + 1
    resto = 11 - (suma % 11)
    if resto == 11:
        return "0"
    if resto == 10:
        return "K"
    return str(resto)


def validar_rut_chileno(valor: str) -> str:
    """
    Valida que el RUT tenga formato correcto y que su digito verificador cumpla Modulo 11.
    Retorna el RUT normalizado si es valido o lanza ValidationError en espanol.
    """
    canonico = normalizar_rut(valor)
    if not re.match(r"^\d{7,8}-[\dK]$", canonico):
        raise ValidationError(
            "El formato del RUT no es valido. Ingrese un RUT chileno valido (ejemplo: 12.345.678-5).",
            code="rut_formato_invalido",
        )
    cuerpo, dv = canonico.split("-", 1)
    if int(cuerpo) < 1000000:
        raise ValidationError(
            "El numero de RUT ingresado no se encuentra en un rango valido.",
            code="rut_rango_invalido",
        )
    dv_esperado = calcular_digito_verificador(cuerpo)
    if dv != dv_esperado:
        raise ValidationError(
            "El RUT ingresado no es valido (el digito verificador no coincide).",
            code="rut_dv_invalido",
        )
    return canonico


class ValidadorComplejidadContrasena:
    """
    Valida que la contrasena cumpla con complejidad robusta y mensajes en espanol:
    - Al menos 12 caracteres
    - Al menos una letra mayuscula, una minuscula y un numero
    - Sin limite de caracteres especiales (compatible con gestores de contrasenas)
    """

    def validate(self, password: str, user: Any = None) -> None:
        if len(password) < 12:
            raise ValidationError(
                "La contrasena debe tener al menos 12 caracteres.",
                code="contrasena_muy_corta",
            )
        if not any(c.isupper() for c in password):
            raise ValidationError(
                "La contrasena debe incluir al menos una letra mayuscula.",
                code="contrasena_sin_mayuscula",
            )
        if not any(c.islower() for c in password):
            raise ValidationError(
                "La contrasena debe incluir al menos una letra minuscula.",
                code="contrasena_sin_minuscula",
            )
        if not any(c.isdigit() for c in password):
            raise ValidationError(
                "La contrasena debe incluir al menos un numero.",
                code="contrasena_sin_numero",
            )

    def get_help_text(self) -> str:
        return (
            "Su contrasena debe contener al menos 12 caracteres, incluyendo "
            "mayusculas, minusculas y numeros. Se admiten todos los caracteres especiales."
        )
