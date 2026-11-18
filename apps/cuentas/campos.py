"""
Cifrado a nivel de campo (Fernet / MultiFernet) e indice ciego HMAC-SHA256.

Diferencia fundamental (Seccion 6.1):
- Las contrasenas se transforman con HASH (Argon2id) porque nunca deben recuperarse.
- Los datos personales sensibles (RUT, telefono) se CIFRAN en reposo mediante AES
  autenticado (Fernet) porque la aplicacion necesita descifrarlos para mostrarlos
  a roles autorizados.
- Para buscar por RUT y garantizar su unicidad sin almacenarlo en texto plano, se
  calcula un indice ciego deterministico con HMAC-SHA256 usando una clave separada.
"""
import base64
import hashlib
import hmac
from typing import Any
from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.db import models


def _normalizar_clave_fernet(clave_cruda: str) -> bytes:
    """Asegura que una clave tenga formato Fernet valido de 32 bytes url-safe base64."""
    limpia = clave_cruda.strip()
    try:
        decodificada = base64.urlsafe_b64decode(limpia.encode("utf-8"))
        if len(decodificada) == 32:
            return limpia.encode("utf-8")
    except Exception:
        pass
    # Si se paso una frase en entorno de desarrollo, deriva 32 bytes de forma determinista
    derivada = hashlib.sha256(limpia.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(derivada)


def obtener_multifernet(claves_configuradas: str | None = None) -> MultiFernet:
    """
    Construye una instancia MultiFernet a partir de CLAVE_CIFRADO_CAMPOS.
    Soporta multiples claves separadas por coma: la primera cifra datos nuevos y
    todas permiten descifrar datos existentes, habilitando rotacion sin perdida.
    """
    cadena_claves = (
        claves_configuradas
        if claves_configuradas is not None
        else getattr(settings, "CLAVE_CIFRADO_CAMPOS", "")
    )
    lista_claves = [c.strip() for c in cadena_claves.split(",") if c.strip()]
    if not lista_claves:
        lista_claves = ["clave-por-defecto-desarrollo-palestra"]
    instancias_fernet = [Fernet(_normalizar_clave_fernet(c)) for c in lista_claves]
    return MultiFernet(instancias_fernet)


def cifrar_texto(valor: str, claves_configuradas: str | None = None) -> str:
    """Cifra una cadena en texto plano y retorna el token Fernet con prefijo 'enc1:'."""
    if valor is None or valor == "":
        return ""
    if valor.startswith("enc1:"):
        return valor
    multifernet = obtener_multifernet(claves_configuradas)
    token = multifernet.encrypt(valor.encode("utf-8")).decode("utf-8")
    return f"enc1:{token}"


def descifrar_texto(valor_cifrado: str, claves_configuradas: str | None = None) -> str:
    """Descifra un token con prefijo 'enc1:' usando MultiFernet."""
    if not valor_cifrado:
        return ""
    if not valor_cifrado.startswith("enc1:"):
        return valor_cifrado
    token_puro = valor_cifrado[5:]
    multifernet = obtener_multifernet(claves_configuradas)
    try:
        return multifernet.decrypt(token_puro.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("No fue posible descifrar el campo con las claves actuales.") from exc


def rotar_texto_cifrado(valor_cifrado: str, claves_configuradas: str | None = None) -> str:
    """Re-cifra un token existente bajo la clave principal activa de MultiFernet."""
    if not valor_cifrado or not valor_cifrado.startswith("enc1:"):
        return cifrar_texto(valor_cifrado, claves_configuradas)
    token_puro = valor_cifrado[5:]
    multifernet = obtener_multifernet(claves_configuradas)
    token_rotado = multifernet.rotate(token_puro.encode("utf-8")).decode("utf-8")
    return f"enc1:{token_rotado}"


def normalizar_rut(rut: str) -> str:
    """
    Normaliza un RUT chileno al formato canonico sin puntos y con guion en mayuscula
    (ejemplo: '12.345.678-k' -> '12345678-K').
    """
    if not rut:
        return ""
    limpio = (
        str(rut)
        .strip()
        .replace(".", "")
        .replace(" ", "")
        .replace("‐", "-")
        .replace("–", "-")
        .upper()
    )
    if "-" not in limpio and len(limpio) >= 2:
        limpio = f"{limpio[:-1]}-{limpio[-1]}"
    return limpio


def formatear_rut_chileno(rut: str) -> str:
    """
    Formatea un RUT chileno con puntos de miles y guion para visualizacion local
    (ejemplo: '12345678-5' -> '12.345.678-5').
    """
    canonico = normalizar_rut(rut)
    if "-" not in canonico:
        return canonico
    cuerpo, dv = canonico.split("-", 1)
    if not cuerpo.isdigit():
        return canonico
    cuerpo_con_puntos = f"{int(cuerpo):,}".replace(",", ".")
    return f"{cuerpo_con_puntos}-{dv}"


def calcular_indice_ciego_rut(rut: str, clave_hmac: str | None = None) -> str:
    """
    Calcula el HMAC-SHA256 del RUT normalizado usando CLAVE_INDICE_CIEGO.
    Permite buscar por RUT e imponer restriccion UNIQUE sin revelar el RUT en la BD.
    """
    canonico = normalizar_rut(rut)
    if not canonico:
        return ""
    clave = (
        clave_hmac
        if clave_hmac is not None
        else getattr(settings, "CLAVE_INDICE_CIEGO", "clave-hmac-defecto")
    )
    return hmac.new(
        clave.encode("utf-8"),
        canonico.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


class CampoCifrado(models.TextField):
    """
    Campo de modelo reutilizable que cifra automaticamente en la base de datos
    mediante MultiFernet y descifra de forma transparente en la capa de aplicacion.
    """

    description = "Campo de texto cifrado en reposo con Fernet/MultiFernet"

    def get_prep_value(self, value: Any) -> Any:
        valor = super().get_prep_value(value)
        if valor is None or valor == "":
            return valor
        return cifrar_texto(str(valor))

    def from_db_value(self, value: Any, expression: Any, connection: Any) -> Any:
        if value is None or value == "":
            return value
        return descifrar_texto(str(value))

    def to_python(self, value: Any) -> Any:
        if value is None or value == "":
            return value
        if isinstance(value, str) and value.startswith("enc1:"):
            return descifrar_texto(value)
        return str(value)
