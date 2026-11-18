"""
Comando de gestion `generar_claves` (Seccion 6.1.E).
Genera claves criptograficamente seguras para:
- SECRET_KEY de Django
- CLAVE_CIFRADO_CAMPOS (Fernet / MultiFernet)
- CLAVE_INDICE_CIEGO (HMAC-SHA256 para busqueda de RUT)
"""
import secrets
from cryptography.fernet import Fernet
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Genera claves criptograficamente seguras para SECRET_KEY, "
        "CLAVE_CIFRADO_CAMPOS (Fernet) y CLAVE_INDICE_CIEGO (HMAC-SHA256)."
    )

    def handle(self, *args, **options) -> None:
        clave_secreta_django = secrets.token_urlsafe(50)
        clave_fernet = Fernet.generate_key().decode("utf-8")
        clave_hmac = secrets.token_hex(32)

        self.stdout.write(
            self.style.SUCCESS(
                "Claves criptograficas generadas correctamente. "
                "Copie estas lineas en su archivo .env (nunca las suba al repositorio):"
            )
        )
        self.stdout.write(f"SECRET_KEY={clave_secreta_django}")
        self.stdout.write(f"CLAVE_CIFRADO_CAMPOS={clave_fernet}")
        self.stdout.write(f"CLAVE_INDICE_CIEGO={clave_hmac}")
