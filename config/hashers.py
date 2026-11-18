"""Configuracion de hash Argon2id parametrizable por entorno para PALESTRA."""
from django.conf import settings
from django.contrib.auth.hashers import Argon2PasswordHasher


class Argon2PalestraHasher(Argon2PasswordHasher):
    """
    Hasher Argon2id con parametros de costo configurables por entorno.
    Cumple con las recomendaciones de OWASP:
    - Memoria minima: 19 MiB (19456 KiB)
    - Iteraciones minimas (time_cost): 2
    - Paralelismo: 1
    Las contrasenas nunca se cifran; se transforman mediante este hash irreversible con sal unica.
    """

    @property
    def memory_cost(self) -> int:
        return int(getattr(settings, "ARGON2_MEMORIA_KIB", 19456))

    @property
    def time_cost(self) -> int:
        return int(getattr(settings, "ARGON2_ITERACIONES", 2))

    @property
    def parallelism(self) -> int:
        return int(getattr(settings, "ARGON2_PARALELISMO", 1))
