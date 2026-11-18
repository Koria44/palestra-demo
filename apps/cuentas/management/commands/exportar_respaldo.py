"""
Comando de gestion `exportar_respaldo` (Seccion 6.1.E y Seccion 7).
Genera un volcado logico JSON de las entidades principales del sistema PALESTRA
y lo cifra en reposo mediante MultiFernet (AES autenticado) usando la clave
configurada en CLAVE_CIFRADO_CAMPOS (o una clave provista).
Permite tambien verificar/descifrar un respaldo mediante la opcion --descifrar.
"""
from pathlib import Path
from django.conf import settings
from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from apps.auditoria.models import RegistroAuditoria
from apps.cuentas.campos import descifrar_texto, obtener_multifernet
from apps.cuentas.models import Usuario
from apps.deportes.models import (
    Disciplina,
    EntrenadorDisciplina,
    Inscripcion,
    PerfilEntrenador,
    PerfilEstudiante,
)
from apps.seguimiento.models import Asistencia, Evaluacion, SesionEntrenamiento


class Command(BaseCommand):
    help = (
        "Genera un volcado logico de las tablas de PALESTRA y lo guarda cifrado "
        "en disco mediante Fernet/MultiFernet (AES-128-CBC + HMAC-SHA256)."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--salida",
            type=str,
            default="",
            help="Ruta del archivo de respaldo cifrado (.json.enc) a generar.",
        )
        parser.add_argument(
            "--descifrar",
            type=str,
            default="",
            help="Ruta de un archivo .json.enc existente para verificar y descifrar.",
        )

    def handle(self, *args, **options) -> None:
        ruta_descifrar = options.get("descifrar", "").strip()
        if ruta_descifrar:
            archivo = Path(ruta_descifrar)
            if not archivo.exists():
                raise CommandError(f"El archivo indicado no existe: {archivo}")
            contenido_cifrado = archivo.read_text(encoding="utf-8").strip()
            json_claro = descifrar_texto(contenido_cifrado)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Respaldo verificado y descifrado correctamente ({len(json_claro)} bytes JSON)."
                )
            )
            return

        carpeta_respaldos = Path(settings.RUTA_BASE) / "respaldos"
        carpeta_respaldos.mkdir(parents=True, exist_ok=True)
        marca = timezone.now().strftime("%Y%m%d_%H%M%S")
        ruta_salida = (
            Path(options["salida"])
            if options.get("salida")
            else carpeta_respaldos / f"respaldo_palestra_{marca}.json.enc"
        )

        objetos = (
            list(Usuario.objects.all())
            + list(PerfilEntrenador.objects.all())
            + list(PerfilEstudiante.objects.all())
            + list(Disciplina.objects.all())
            + list(EntrenadorDisciplina.objects.all())
            + list(Inscripcion.objects.all())
            + list(SesionEntrenamiento.objects.all())
            + list(Asistencia.objects.all())
            + list(Evaluacion.objects.all())
            + list(RegistroAuditoria.objects.all())
        )

        json_volcado = serializers.serialize("json", objetos, indent=2)
        multifernet = obtener_multifernet()
        token_fernet = multifernet.encrypt(json_volcado.encode("utf-8")).decode("utf-8")
        contenido_final = f"enc1:{token_fernet}"

        ruta_salida.parent.mkdir(parents=True, exist_ok=True)
        ruta_salida.write_text(contenido_final, encoding="utf-8")

        self.stdout.write(
            self.style.SUCCESS(
                f"Respaldo lógico cifrado generado exitosamente en: {ruta_salida} "
                f"({len(objetos)} registros respaldados)."
            )
        )
