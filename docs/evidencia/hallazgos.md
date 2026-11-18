# Registro de Hallazgos, Evaluación de Riesgos y Correcciones Aplicadas

Este documento registra los hallazgos detectados durante las pruebas de seguridad, integración, análisis estático y revisión de controles OWASP Top 10 / ISO 27002 en **PALESTRA**, junto con el estado antes y después de cada corrección y su commit asociado.

---

## Resumen Ejecutivo

| ID | Hallazgo | Vector / Categoría OWASP | Nivel de Riesgo | Estado Final | Commit Asociado |
|---|---|---|---|---|---|
| H-01 | Exposición potencial de estilos en línea bajo Content Security Policy estricta | A05:2021 Configuración de Seguridad / CSP | Medio | Corregido | `fix: reemplaza estilos inline de barras de progreso por atributos data compatibles con CSP` |
| H-02 | Validación de relación `usuario` en inicialización de formularios `ModelForm` sin persistir | Integridad de Aplicación / Manejo de Errores | Medio | Corregido | `fix: verifica estado de instancia antes de acceder a relacion usuario en formularios` |
| H-03 | Riesgo de Inyección de Fórmulas (CSV Injection) en exportación de observaciones | A03:2021 Inyección (CSV Formula Injection) | Alto | Corregido | `feat: implementa sanitizacion contra inyeccion de formulas en exportacion CSV` |
| H-04 | Protección contra enumeración de usuarios por diferencia de tiempos en login por RUT/correo | A07:2021 Fallas de Identificación y Autenticación | Medio | Corregido | `feat: aplica hash ficticio en tiempo constante cuando el identificador no existe` |
| H-05 | Exposición de tablas públicas en API automática PostgREST de Supabase | A01:2021 Control de Acceso Quebrado | Alto | Corregido | `feat: habilita RLS en todas las tablas publicas y crea rol de minimo privilegio` |

---

## Detalle de Hallazgos (Antes y Después)

### H-01: Atributos de ancho dinámico en barras de progreso y política CSP (`style-src 'self'`)
- **Estado previo (Antes):** Las barras de progreso de ocupación de cupos requerían definir el ancho porcentual dinámicamente según el cálculo de cada disciplina. El uso de `style="width: X%"` en línea es bloqueado cuando la cabecera `Content-Security-Policy` define `style-src 'self'` sin `'unsafe-inline'`.
- **Riesgo:** Medio (degradación visual o necesidad de debilitar CSP agregando `'unsafe-inline'`).
- **Corrección aplicada (Después):** Se mantuvo `style-src 'self'` estricto en `config/base.py` y se reemplazó el atributo en línea por `data-porcentaje="{{ disc.porcentaje_ocupacion }}"`, procesado desde el archivo estático externo `static/js/palestra.js` cargado bajo `script-src 'self'`.
- **Verificación:** `pruebas/seguridad/prueba_seguridad_fase1_y_2.py::PruebasCabecerasYCookiesSeguras` y `pruebas/seguridad/prueba_penetracion_owasp_zap.py`.

### H-02: Acceso a `self.instance.usuario` en instancias nuevas con UUID pregenerado
- **Estado previo (Antes):** Como los modelos `PerfilEstudiante` y `PerfilEntrenador` utilizan `UUIDField(default=uuid.uuid4)` como clave primaria, `self.instance.pk` existe incluso antes de guardar el registro en la base de datos. Al inicializar `FormularioEstudiante(request.POST)` en un alta, consultar solo `if self.instance.pk:` intentaba leer `self.instance.usuario`, provocando `RelatedObjectDoesNotExist`.
- **Riesgo:** Medio (error 500 al enviar formularios de alta de estudiantes o entrenadores).
- **Corrección aplicada (Después):** En `apps/deportes/formularios.py` se actualizó la condición a `if self.instance and not self.instance._state.adding and self.instance.usuario_id:` tanto en `__init__` como en `clean_rut` y `clean_correo`.
- **Verificación:** `pruebas/integracion/prueba_modulo_coordinador.py::PruebasModuloCoordinador::test_crear_estudiante_con_enlace_y_con_contrasena_temporal` (PASÓ).

### H-03: Inyección de Fórmulas en Exportación CSV
- **Estado previo (Antes):** Los campos de texto libre como `observacion` en asistencias o evaluaciones podían comenzar con caracteres interpretables como fórmulas por hojas de cálculo (`=`, `+`, `-`, `@`, `\t`, `\r`), incluso precedidos por espacios en blanco.
- **Riesgo:** Alto (ejecución de fórmulas o comandos al abrir el CSV en software de planillas).
- **Corrección aplicada (Después):** Se implementó `sanitizar_celda_csv` en `apps/reportes/servicios.py`, que evalúa tanto la cadena original como `lstrip(" ")` y antepone una comilla simple (`'`) a cualquier celda que comience con `=`, `+`, `-`, `@`, `\t` o `\r`.
- **Verificación:** `pruebas/unitarias/prueba_modelos_validadores_y_servicios.py::PruebasUnitariasValidadoresYServicios::test_sanitizacion_inyeccion_formulas_csv` (6 vectores probados y mitigados).

### H-04: Prevención de Enumeración de Usuarios por Temporización y Mensajes
- **Estado previo (Antes):** Si al autenticar un correo o RUT inexistente el backend retornaba `None` de inmediato sin ejecutar el cálculo Argon2id, un atacante podía medir la diferencia de milisegundos respecto a un usuario existente.
- **Riesgo:** Medio (enumeración de cuentas válidas por canal lateral de tiempo).
- **Corrección aplicada (Después):** En `apps/cuentas/backends.py` (`AutenticacionCorreoORutBackend.authenticate`), cuando `_buscar_usuario` no encuentra coincidencia, se ejecuta `make_password(password)` con el hasher Argon2id antes de retornar `None`, igualando el costo computacional y devolviendo siempre el mismo mensaje genérico.
- **Verificación:** `pruebas/seguridad/prueba_penetracion_owasp_zap.py`.

### H-05: Defensa en Profundidad en Supabase (RLS y Menor Privilegio)
- **Estado previo (Antes):** En proyectos Supabase recién creados, las tablas del esquema `public` son accesibles mediante la API PostgREST si no tienen RLS habilitado, y las conexiones por defecto suelen usar el superusuario `postgres`.
- **Riesgo:** Alto (exposición de tablas por fuera del backend Django o exceso de privilegios en la conexión).
- **Corrección aplicada (Después):** Se crearon `supabase/rls.sql` (que activa `ENABLE ROW LEVEL SECURITY` y revoca permisos a `anon` y `authenticated` en todas las tablas públicas) y `supabase/roles.sql` (que crea el rol `palestra_app` sin permisos de superusuario y revoca `UPDATE`/`DELETE` sobre `registro_auditoria`).
