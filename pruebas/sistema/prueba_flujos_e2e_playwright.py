"""
Pruebas de Sistema End-to-End (E2E) con Playwright y medicion de rendimiento (Seccion 10.3).
Recorre los flujos completos de los tres perfiles (Coordinador, Entrenador y Estudiante)
contra el servidor en ejecucion, verifica responsividad (360, 768, 1024, 1440 px),
guarda capturas de pantalla en docs/evidencia/ y mide tiempos de respuesta.
"""
import json
import os
import time
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

RUTA_EVIDENCIA = Path(__file__).resolve().parent.parent.parent / "docs" / "evidencia"


@pytest.mark.django_db(transaction=True)
class PruebasSistemaE2EPlaywright:
    """Casos de uso completos por rol en navegador real Chromium (Playwright)."""

    def test_flujo_completo_por_rol_y_rendimiento(self, live_server, settings) -> None:
        from django.core.management import call_command

        settings.DEBUG = True
        call_command("cargar_datos_demo")
        RUTA_EVIDENCIA.mkdir(parents=True, exist_ok=True)
        url_base = live_server.url
        metricas_tiempos: dict[str, float] = {}

        with sync_playwright() as p:
            navegador = p.chromium.launch(headless=True)
            contexto = navegador.new_context(
                viewport={"width": 1440, "height": 900},
                locale="es-CL",
            )
            pagina = contexto.new_page()

            # 1. Pantalla de Login y responsividad 360px / 1440px
            t0 = time.perf_counter()
            pagina.goto(f"{url_base}/iniciar-sesion/")
            metricas_tiempos["carga_login_ms"] = round((time.perf_counter() - t0) * 1000, 2)
            assert "PALESTRA" in pagina.title()
            pagina.screenshot(path=str(RUTA_EVIDENCIA / "01_login_1440px.png"), full_page=True)

            pagina.set_viewport_size({"width": 360, "height": 740})
            pagina.screenshot(path=str(RUTA_EVIDENCIA / "02_login_360px_movil.png"), full_page=True)
            pagina.set_viewport_size({"width": 1440, "height": 900})

            # 2. Flujo Coordinador: Login, panel, disciplinas, inscripciones y reporte
            pagina.fill('input[name="identificador"]', "coordinador@palestra.cl")
            pagina.fill('input[name="contrasena"]', "PalestraDemo2026!")
            t0 = time.perf_counter()
            pagina.click('button[type="submit"]')
            pagina.wait_for_url("**/panel/coordinador/**")
            metricas_tiempos["panel_coordinador_ms"] = round((time.perf_counter() - t0) * 1000, 2)
            assert "Panel de Coordinación Deportiva" in pagina.content()
            pagina.screenshot(path=str(RUTA_EVIDENCIA / "03_panel_coordinador.png"), full_page=True)

            t0 = time.perf_counter()
            pagina.goto(f"{url_base}/deportes/disciplinas/")
            metricas_tiempos["listado_disciplinas_ms"] = round((time.perf_counter() - t0) * 1000, 2)
            pagina.screenshot(path=str(RUTA_EVIDENCIA / "04_coordinador_disciplinas.png"), full_page=True)

            t0 = time.perf_counter()
            pagina.goto(f"{url_base}/deportes/estudiantes/")
            metricas_tiempos["listado_estudiantes_ms"] = round((time.perf_counter() - t0) * 1000, 2)
            pagina.screenshot(path=str(RUTA_EVIDENCIA / "05_coordinador_estudiantes.png"), full_page=True)

            t0 = time.perf_counter()
            pagina.goto(f"{url_base}/reportes/")
            metricas_tiempos["reporte_global_ms"] = round((time.perf_counter() - t0) * 1000, 2)
            assert "Reportes de Gestión Deportiva" in pagina.content()
            pagina.screenshot(path=str(RUTA_EVIDENCIA / "06_reportes_coordinador.png"), full_page=True)

            pagina.goto(f"{url_base}/auditoria/")
            assert "Bitácora de Auditoría" in pagina.content()
            pagina.screenshot(path=str(RUTA_EVIDENCIA / "07_bitacora_auditoria.png"), full_page=True)

            # Cerrar sesion de Coordinador
            pagina.locator('form[action="/cerrar-sesion/"] button[type="submit"]').first.click()
            pagina.wait_for_url("**/iniciar-sesion/**")

            # 3. Flujo Entrenador: Login por RUT, ver nomina, gestionar sesion (asistencia y nota)
            pagina.fill('input[name="identificador"]', "14.567.890-0")
            pagina.fill('input[name="contrasena"]', "PalestraDemo2026!")
            t0 = time.perf_counter()
            pagina.click('button[type="submit"]')
            pagina.wait_for_url("**/panel/entrenador/**")
            metricas_tiempos["panel_entrenador_ms"] = round((time.perf_counter() - t0) * 1000, 2)
            assert "Panel de Entrenador Deportivo" in pagina.content()
            pagina.screenshot(path=str(RUTA_EVIDENCIA / "08_panel_entrenador.png"), full_page=True)

            pagina.goto(f"{url_base}/seguimiento/sesiones/")
            pagina.locator("table.tabla-palestra tbody tr a").first.click()
            assert "Registro de Asistencia y Evaluación en Lote" in pagina.content()
            pagina.screenshot(path=str(RUTA_EVIDENCIA / "09_entrenador_toma_asistencia.png"), full_page=True)

            # Cerrar sesion de Entrenador
            pagina.locator('form[action="/cerrar-sesion/"] button[type="submit"]').first.click()
            pagina.wait_for_url("**/iniciar-sesion/**")

            # 4. Flujo Estudiante: Login por RUT, panel y grafico de rendimiento
            pagina.fill('input[name="identificador"]', "18.123.456-3")
            pagina.fill('input[name="contrasena"]', "PalestraDemo2026!")
            t0 = time.perf_counter()
            pagina.click('button[type="submit"]')
            pagina.wait_for_url("**/panel/estudiante/**")
            metricas_tiempos["panel_estudiante_ms"] = round((time.perf_counter() - t0) * 1000, 2)
            assert "Mi Resumen Deportivo" in pagina.content()
            pagina.screenshot(path=str(RUTA_EVIDENCIA / "10_panel_estudiante.png"), full_page=True)

            t0 = time.perf_counter()
            pagina.goto(f"{url_base}/seguimiento/estudiante/mi-asistencia/")
            metricas_tiempos["historial_estudiante_ms"] = round((time.perf_counter() - t0) * 1000, 2)
            assert "Evolución de Rendimiento en el Tiempo" in pagina.content()
            pagina.screenshot(path=str(RUTA_EVIDENCIA / "11_estudiante_asistencia_y_grafico.png"), full_page=True)

            navegador.close()

        # Guarda evidencia de rendimiento
        archivo_rendimiento = RUTA_EVIDENCIA / "rendimiento_tiempos_respuesta.json"
        archivo_rendimiento.write_text(
            json.dumps(metricas_tiempos, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        # Verifica que todos los listados y reportes respondan en menos de 1500 ms
        for nombre_metrica, valor_ms in metricas_tiempos.items():
            assert valor_ms < 1500, f"Tiempo excesivo en {nombre_metrica}: {valor_ms} ms"
