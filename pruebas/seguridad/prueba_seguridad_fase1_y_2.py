"""
Pruebas automatizadas de seguridad, hash Argon2id, sal unica, tokens de un solo uso,
cifrado a nivel de campo (MultiFernet), indice ciego HMAC, bitacora inmutable y cookies
(Seccion 6.1.F y Seccion 10).
"""
import pytest
from cryptography.fernet import Fernet
from django.contrib.auth.hashers import PBKDF2PasswordHasher
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.urls import reverse
from apps.auditoria.models import registrar_evento_auditoria
from apps.cuentas.campos import (
    calcular_indice_ciego_rut,
    cifrar_texto,
    descifrar_texto,
    rotar_texto_cifrado,
)
from apps.cuentas.models import Usuario
from apps.cuentas.validadores import validar_rut_chileno
from apps.deportes.models import PerfilEstudiante


@pytest.mark.django_db
class PruebasHashContrasenasYPolitica:
    """Verifica el cumplimiento de Argon2id, sal unica, migracion de hash y rechazo de claves debiles."""

    def test_hash_argon2id_y_ausencia_texto_plano(self) -> None:
        contrasena_clara = "ClaveSeguraPalestra2026!"
        usuario = Usuario.objects.create_user(
            username="coord_test",
            email="coord_test@palestra.cl",
            password=contrasena_clara,
            rol=Usuario.ROL_COORDINADOR,
        )
        # Verifica prefijo Argon2id y que nunca contenga la contrasena en claro
        assert usuario.password.startswith("argon2$argon2id$")
        assert contrasena_clara not in usuario.password

    def test_sal_unica_para_misma_contrasena(self) -> None:
        contrasena_comun = "MismaContrasenaSegura2026!"
        u1 = Usuario.objects.create_user(
            username="usuario_uno",
            email="uno@palestra.cl",
            password=contrasena_comun,
        )
        u2 = Usuario.objects.create_user(
            username="usuario_dos",
            email="dos@palestra.cl",
            password=contrasena_comun,
        )
        assert u1.password != u2.password

    @pytest.mark.parametrize(
        "contrasena_debil",
        [
            "corta1A",           # Menos de 12 caracteres
            "123456789012",      # Solo numerica
            "password123456",    # Sin mayusculas / comun
            "SOLOMAYUSCULAS12",  # Sin minusculas
            "SoloLetrasSinNumeros",  # Sin numeros
        ],
    )
    def test_rechaza_contrasenas_debiles_o_cortas(self, contrasena_debil: str) -> None:
        with pytest.raises(ValidationError):
            validate_password(contrasena_debil)

    def test_hash_antiguo_se_actualiza_a_argon2id_al_iniciar_sesion(self, client) -> None:
        contrasena = "ClaveMigracionSegura2026!"
        hasher_antiguo = PBKDF2PasswordHasher()
        hash_pbkdf2 = hasher_antiguo.encode(contrasena, "sal_prueba_123")
        usuario = Usuario.objects.create(
            username="migrado",
            email="migrado@palestra.cl",
            password=hash_pbkdf2,
            rol=Usuario.ROL_ESTUDIANTE,
            activo=True,
        )
        assert usuario.password.startswith("pbkdf2_sha256$")

        respuesta = client.post(
            reverse("cuentas:iniciar_sesion"),
            {"identificador": "migrado@palestra.cl", "contrasena": contrasena},
        )
        assert respuesta.status_code == 302
        usuario.refresh_from_db()
        assert usuario.password.startswith("argon2$argon2id$")


@pytest.mark.django_db
class PruebasTokensUnSoloUsoYAuditoria:
    """Verifica que los tokens de activacion sean de un solo uso, expiren y no queden en logs."""

    def test_token_activacion_un_solo_uso_y_alteracion(self, client) -> None:
        usuario = Usuario.objects.create_user(
            username="nuevo_est",
            email="nuevo_est@palestra.cl",
            rol=Usuario.ROL_ESTUDIANTE,
        )
        usuario.set_unusable_password()
        usuario.save()

        token = usuario.generar_token_activacion()
        # El token en claro nunca se guarda en la base de datos
        assert token not in usuario.hash_token_activacion

        # 1. Token alterado falla
        assert Usuario.validar_token_activacion(token + "alterado") is None

        # 2. Token expirado falla
        assert Usuario.validar_token_activacion(token, max_age_segundos=-1) is None

        # 3. Primer uso exitoso mediante la vista de activacion
        url_activar = reverse("cuentas:activar_cuenta", kwargs={"token": token})
        nueva_clave = "NuevaClaveActivada2026!"
        resp = client.post(
            url_activar,
            {"new_password1": nueva_clave, "new_password2": nueva_clave},
        )
        assert resp.status_code == 302
        usuario.refresh_from_db()
        assert usuario.check_password(nueva_clave)
        assert usuario.hash_token_activacion == ""

        # 4. Reutilizar el mismo token falla inmediatamente
        assert Usuario.validar_token_activacion(token) is None
        resp_reuso = client.get(url_activar)
        assert resp_reuso.status_code == 400

    def test_ninguna_contrasena_ni_token_aparece_en_auditoria_y_es_inmutable(self) -> None:
        secreto_clave = "SecretoSuperConfidencial2026!"
        secreto_token = "tok_secreto_999888777"
        reg = registrar_evento_auditoria(
            accion="prueba_sanitizacion",
            entidad="Usuario",
            identificador="123",
            detalle={
                "correo": "seguro@palestra.cl",
                "contrasena": secreto_clave,
                "password1": secreto_clave,
                "token_activacion": secreto_token,
            },
        )
        volcado = str(reg.detalle)
        assert secreto_clave not in volcado
        assert secreto_token not in volcado
        assert reg.detalle.get("correo") == "seguro@palestra.cl"

        # Verifica inmutabilidad de RegistroAuditoria
        reg.accion = "intento_alteracion"
        with pytest.raises(PermissionDenied):
            reg.save()
        with pytest.raises(PermissionDenied):
            reg.delete()


@pytest.mark.django_db
class PruebasCifradoEnReposoYRotacionMultiFernet:
    """Verifica cifrado de RUT y telefono en BD mediante SQL directo y rotacion MultiFernet."""

    def test_campos_sensibles_cifrados_en_bd_y_descifrados_en_app(self) -> None:
        rut_claro = "11.111.111-1"
        telefono_claro = "+56987654321"
        usuario = Usuario.objects.create_user(
            username="est_cifrado",
            email="est_cifrado@palestra.cl",
            password="ClaveCifradoSegura2026!",
            rol=Usuario.ROL_ESTUDIANTE,
        )
        perfil = PerfilEstudiante.objects.create(
            usuario=usuario,
            rut=rut_claro,
            nombres="Camila",
            apellidos="Soto",
            curso_o_carrera="Ingenieria Civil",
            telefono=telefono_claro,
        )

        # Consulta SQL directa a la tabla para comprobar que en disco el texto esta cifrado
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT rut, telefono, rut_indice_ciego FROM perfil_estudiante WHERE id = %s",
                [str(perfil.id).replace("-", "") if connection.vendor == "sqlite" else str(perfil.id)],
            )
            fila = cursor.fetchone()
            if fila is None:
                cursor.execute(
                    "SELECT rut, telefono, rut_indice_ciego FROM perfil_estudiante"
                )
                fila = cursor.fetchone()

        rut_en_bd, telefono_en_bd, indice_en_bd = fila
        assert rut_en_bd.startswith("enc1:")
        assert "11111111" not in rut_en_bd
        assert telefono_en_bd.startswith("enc1:")
        assert telefono_claro not in telefono_en_bd
        assert indice_en_bd == calcular_indice_ciego_rut("11111111-1")

        # En la capa de aplicacion se descifra transparentemente
        perfil_recargado = PerfilEstudiante.objects.get(pk=perfil.pk)
        assert perfil_recargado.rut == "11111111-1"
        assert perfil_recargado.rut_formateado == "11.111.111-1"
        assert perfil_recargado.telefono == telefono_claro

    def test_rotacion_claves_con_multifernet(self) -> None:
        clave_vieja = Fernet.generate_key().decode("utf-8")
        clave_nueva = Fernet.generate_key().decode("utf-8")

        texto_original = "15432987-K"
        cifrado_viejo = cifrar_texto(texto_original, claves_configuradas=clave_vieja)

        # Con ambas claves (nueva primero, vieja como respaldo) descifra y rota
        combinadas = f"{clave_nueva},{clave_vieja}"
        assert descifrar_texto(cifrado_viejo, claves_configuradas=combinadas) == texto_original

        cifrado_rotado = rotar_texto_cifrado(cifrado_viejo, claves_configuradas=combinadas)
        # Ahora puede descifrarse unicamente con la clave nueva
        assert descifrar_texto(cifrado_rotado, claves_configuradas=clave_nueva) == texto_original

    def test_validador_rut_chileno_modulo_11(self) -> None:
        assert validar_rut_chileno("11.111.111-1") == "11111111-1"
        with pytest.raises(ValidationError):
            validar_rut_chileno("11.111.111-9")
        with pytest.raises(ValidationError):
            validar_rut_chileno("abc-1")


@pytest.mark.django_db
class PruebasCabecerasYCookiesSeguras:
    """Verifica cabeceras CSP, X-Frame-Options, nosniff y atributos de cookies."""

    def test_cabeceras_seguridad_y_csp_en_login(self, client, settings) -> None:
        settings.SESSION_COOKIE_SECURE = True
        settings.CSRF_COOKIE_SECURE = True
        respuesta = client.get(reverse("cuentas:iniciar_sesion"), secure=True)
        assert respuesta.status_code == 200
        assert "Content-Security-Policy" in respuesta.headers
        assert "script-src 'self'" in respuesta.headers["Content-Security-Policy"]
        assert respuesta.headers.get("X-Frame-Options") == "DENY"
        assert respuesta.headers.get("X-Content-Type-Options") == "nosniff"

        cookie_csrf = respuesta.cookies.get("csrftoken")
        if cookie_csrf:
            assert cookie_csrf["httponly"] is True
            assert cookie_csrf["samesite"] == "Lax"
            assert cookie_csrf["secure"] is True
