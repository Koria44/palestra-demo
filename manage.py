#!/usr/bin/env python
"""Utilidad de linea de comandos de Django para tareas administrativas de PALESTRA."""
import os
import sys
from pathlib import Path


def ejecutar_administracion() -> None:
    """Ejecuta las tareas administrativas configurando el entorno por defecto."""
    # Carga variables de entorno desde .env si existe
    try:
        from dotenv import load_dotenv
        ruta_base = Path(__file__).resolve().parent
        load_dotenv(ruta_base / ".env")
    except ImportError:
        pass

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.desarrollo")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "No fue posible importar Django. Verifique que este instalado y "
            "disponible en la variable PYTHONPATH, y que el entorno virtual este activo."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    ejecutar_administracion()
