# PALESTRA — Gestión de Actividades Deportivas Estudiantiles

Sistema centralizado para el seguimiento de la participación estudiantil en disciplinas deportivas institucionales, control de asistencia por sesión, registro de evaluaciones de rendimiento (escala chilena 1,0 a 7,0) y generación de reportes estadísticos con exportación segura a CSV y PDF.

---

## 1. Arquitectura y Decisiones Técnicas Relevantes

| Capa | Tecnología | Justificación y Uso en PALESTRA |
|---|---|---|
| Backend | Python 3.12+ y Django 5.x/6.x | Lógica de negocio, control de acceso en servidor (`RolRequeridoMixin`), ORM parametrizado y plantillas autoescapadas. |
| API RESTful | Django REST Framework + `drf-spectacular` | Endpoints versionados bajo `/api/v1/` con filtrado (`django-filter`), paginación, limitación de tasa (throttling) y esquema OpenAPI exclusivo para el Coordinador. |
| Base de Datos | Supabase (PostgreSQL) | Única fuente de verdad relacional en Tercera Forma Normal (3FN) con restricciones `CHECK`, `UNIQUE`, `ON DELETE PROTECT`, baja lógica y Row Level Security (RLS). |
| Seguridad Criptográfica | `argon2-cffi` + `cryptography` (Fernet / MultiFernet + HMAC-SHA256) | Hash irreversible Argon2id para contraseñas y cifrado autenticado a nivel de campo para datos personales sensibles (`rut` y `telefono`). |
| Interfaz (UI/UX) | Tailwind CSS (`preflight: false`) + Bootstrap 5 + SVG | Tokens de color unificados en variables CSS, diseño responsivo (360 px a 1440 px), controles táctiles >= 44 px, respeto a `prefers-reduced-motion` y cero scripts inline (compatible con CSP estricta). |

### Decisiones de Seguridad y Arquitectura (Explicación Técnica)

1. **Por qué se usa la autenticación de Django en lugar de Supabase Auth:**
   Toda la lógica de autorización basada en roles (`coordinador`, `entrenador`, `estudiante`), el inicio de sesión híbrido por **correo institucional o RUT chileno** (mediante índice ciego HMAC), el bloqueo por intentos fallidos (`django-axes`), la política de contraseñas de 12+ caracteres con hash **Argon2id**, el enlace firmado de activación de un solo uso y la bitácora inmutable (`RegistroAuditoria`) se gobiernan de forma centralizada y atómica en el servidor Django. Usar Supabase Auth introduciría una segunda fuente de identidad desconectada de los mixins de vista, del middleware de cambio obligatorio de contraseña y del índice ciego del RUT.

2. **Diferencia entre Hash de Contraseñas y Cifrado de Datos Personales (Sección 6.1):**
   - **Las contraseñas no se cifran, se transforman con hash:** Un cifrado es matemático y reversible con una clave; un hash criptográfico con sal única (**Argon2id**, memoria >= 19 MiB, iteraciones >= 2) es irreversible. Ni siquiera un administrador con acceso directo a la base de datos puede recuperar la contraseña de un usuario.
   - **Los datos personales sensibles sí se cifran en reposo:** El `rut` y el `telefono` deben poder mostrarse de vuelta en la interfaz a los roles autorizados (Coordinador, o Entrenador respecto de su nómina). Por ello se cifran en la capa de aplicación mediante `CampoCifrado` usando **Fernet / MultiFernet** (AES-128-CBC con autenticación HMAC-SHA256).
   - **Índice ciego (`rut_indice_ciego`):** Como el cifrado Fernet es probabilístico (produce un texto cifrado distinto cada vez), para buscar por RUT en el login y garantizar su restricción `UNIQUE` en la base de datos sin revelar el RUT, se almacena el `HMAC-SHA256` del RUT normalizado calculado con una clave independiente (`CLAVE_INDICE_CIEGO`).

3. **Cifrado en Reposo en Supabase:**
   Además del cifrado a nivel de campo realizado por PALESTRA antes de enviar los datos a la base de datos, Supabase cifra todos los discos de bases de datos PostgreSQL y copias de seguridad en reposo a nivel de infraestructura en la nube mediante AES-256 (según la documentación oficial de seguridad de Supabase Platform).

---

## 2. Estructura del Proyecto

```text
palestra/
  manage.py
  config/                  # Configuraciones divididas: base.py, desarrollo.py, produccion.py, hashers.py
  apps/
    cuentas/               # Usuario, login correo/RUT, roles, activacion de un solo uso, CampoCifrado
    deportes/              # Disciplinas, entrenadores, estudiantes e inscripciones (con baja logica)
    seguimiento/           # Sesiones, asistencia en lote y evaluaciones (ventana de 7 dias)
    reportes/              # Reportes filtrables y exportacion segura a CSV y PDF
    auditoria/             # RegistroAuditoria inmutable y sanitizacion de secretos
    api/                   # Endpoints RESTful (/api/v1/), serializadores y OpenAPI
  templates/               # Plantillas HTML5 organizadas por modulo y paginas 403, 404 y 500
  static/                  # Hoja de estilos compilada, JS modular sin inline, isotipo SVG y favicon
  assets/                  # Fuente de configuracion de Tailwind CSS (preflight desactivado)
  pruebas/                 # Suites automatizadas: unitarias, integracion, sistema (Playwright), seguridad
  docs/evidencia/          # Resultados de pytest, cobertura (91%), escaneo ZAP, hallazgos.md y capturas
  supabase/                # esquema.sql, rls.sql, roles.sql, datos_demo.sql y LEEME.md
  .github/workflows/ci.yml # Pipeline CI: Gitleaks, Ruff, pip-audit, migraciones y pytest-cov
  .env.example
  .gitignore
  requirements.txt
  README.md
  LICENSE
```

---

## 3. Requisitos e Instalación Paso a Paso

### Requisitos Previos
- Python 3.12 o superior
- Git
- Proyecto en Supabase (PostgreSQL) o entorno local de desarrollo

### Pasos de Instalación Local

1. **Clonar el repositorio e ingresar al directorio:**
   ```bash
   git clone <URL_DEL_REPOSITORIO>
   cd palestra
   ```

2. **Crear y activar el entorno virtual:**
   ```bash
   # En Windows (PowerShell)
   python -m venv env
   .\env\Scripts\Activate.ps1

   # En Linux / macOS
   python3 -m venv env
   source env/bin/activate
   ```

3. **Instalar las dependencias fijadas:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurar las variables de entorno (`.env`):**
   Copie el archivo de plantilla `.env.example` a `.env`:
   ```bash
   cp .env.example .env
   ```
   Genere claves criptográficas nuevas para su entorno ejecutando:
   ```bash
   python manage.py generar_claves
   ```
   Copie los valores generados (`SECRET_KEY`, `CLAVE_CIFRADO_CAMPOS`, `CLAVE_INDICE_CIEGO`) dentro de su archivo `.env`.

5. **Ejecutar las migraciones de la base de datos:**
   ```bash
   python manage.py migrate
   ```

6. **Cargar los datos ficticios de demostración (solo con `DEBUG=True`):**
   ```bash
   python manage.py cargar_datos_demo
   ```

7. **Iniciar el servidor de desarrollo:**
   ```bash
   python manage.py runserver
   ```
   Abra `http://127.0.0.1:8000/iniciar-sesion/` en su navegador.

---

## 4. Configuración de Supabase (PostgreSQL, RLS y Menor Privilegio)

1. Cree un nuevo proyecto en [Supabase](https://supabase.com/).
2. En **Project Settings -> Database**, copie:
   - La cadena del **Connection Pooler (Transaction mode, puerto 6543)** y asígnela a `DATABASE_URL` en su `.env` añadiendo `?sslmode=require`.
   - La cadena de **Direct Connection (puerto 5432)** y asígnela a `DATABASE_URL_DIRECT` en su `.env` añadiendo `?sslmode=require`.
   - Cambie `USAR_SQLITE_LOCAL=False` en su `.env`.
3. Aplique las migraciones de Django hacia Supabase:
   ```bash
   python manage.py migrate
   ```
4. En el **SQL Editor** de Supabase, ejecute en orden:
   - `supabase/rls.sql`: Habilita Row Level Security (RLS) en todas las tablas del esquema `public` y revoca el acceso a los roles `anon` y `authenticated`, bloqueando la API pública PostgREST como defensa en profundidad.
   - `supabase/roles.sql`: Crea el rol dedicado `palestra_app` con privilegios mínimos (sin superusuario y sin permiso para alterar o borrar `registro_auditoria`). Actualice luego `DATABASE_URL` para usar el usuario `palestra_app`.

---

## 5. Credenciales Ficticias de Demostración

> **ADVERTENCIA DE SEGURIDAD:** Las siguientes credenciales corresponden exclusivamente a datos ficticios generados por `python manage.py cargar_datos_demo` (comando que se bloquea automáticamente si `DEBUG=False`). **Jamás deben utilizarse en entornos de producción.**

| Rol | Correo Institucional | RUT (Alternativo para Login) | Contraseña de Prueba |
|---|---|---|---|
| **Coordinador Deportivo** | `coordinador@palestra.cl` | — | `PalestraDemo2026!` |
| **Entrenador (Fútbol / Básquetbol / Vóleibol)** | `entrenador.futbol@palestra.cl` | `14.567.890-0` | `PalestraDemo2026!` |
| **Entrenadora (Atletismo / Natación)** | `entrenadora.atletismo@palestra.cl` | `16.234.567-2` | `PalestraDemo2026!` |
| **Estudiante 1** | `catalina.munoz@estudiante.palestra.cl` | `18.123.456-3` | `PalestraDemo2026!` |
| **Estudiante 2** | `matias.gonzalez@estudiante.palestra.cl` | `19.234.567-7` | `PalestraDemo2026!` |

---

## 6. Rotación de Claves y Respuesta ante Incidentes

### Procedimiento de Rotación Sin Pérdida de Acceso
1. **Rotación de `SECRET_KEY`:**
   - Genere una nueva clave con `python manage.py generar_claves`.
   - Mueva el valor anterior de `SECRET_KEY` a la variable `SECRET_KEY_FALLBACKS` en `.env` y coloque la nueva clave en `SECRET_KEY`. Las sesiones y enlaces vigentes seguirán validándose durante la ventana de transición.
2. **Rotación de `CLAVE_CIFRADO_CAMPOS` (`MultiFernet`):**
   - Genere una nueva clave Fernet y colóquela **al inicio** de `CLAVE_CIFRADO_CAMPOS` separada por coma de la clave anterior: `CLAVE_CIFRADO_CAMPOS=NUEVA_CLAVE,CLAVE_ANTERIOR`.
   - `MultiFernet` cifrará todos los registros nuevos con la primera clave y seguirá descifrando los registros históricos con cualquiera de las claves listadas.

### Qué hacer ante una filtración de credenciales
1. Revocar de inmediato la credencial de base de datos comprometida en Supabase (`ALTER ROLE palestra_app WITH PASSWORD '...'`).
2. Rotar `SECRET_KEY` vaciando `SECRET_KEY_FALLBACKS` para invalidar instantáneamente todas las sesiones y tokens firmados previos.
3. Rotar `CLAVE_CIFRADO_CAMPOS` y re-cifrar los perfiles con `rotar_texto_cifrado`.
4. Inspeccionar la tabla inmutable `registro_auditoria` filtrando por rango horario y dirección IP.

---

## 7. Ejecución de Pruebas Automatizadas y Verificación de Calidad

Toda la evidencia generada se almacena en `docs/evidencia/`:

```bash
# Ejecutar todas las suites (unitarias, integracion, seguridad, penetracion y E2E Playwright) con cobertura
pytest --cov=apps --cov-report=term-missing pruebas/

# Ejecutar linter Ruff
ruff check apps config pruebas manage.py

# Auditar vulnerabilidades en paquetes
pip-audit -r requirements.txt

# Generar un respaldo logico cifrado
python manage.py exportar_respaldo
```

---

## 8. Trabajo Colaborativo en Equipo (GitHub y Supabase)

1. **Repositorio GitHub:**
   - Invite a los colaboradores desde **Settings -> Collaborators** en GitHub.
   - Utilice el flujo de ramas: `main` (producción estable), `develop` (integración) y ramas `feature/<descripcion-corta>`, empleando commits convencionales en español (`feat:`, `fix:`, `docs:`, `test:`) sin emojis.
2. **Proyecto Supabase y `.env`:**
   - Invite a los integrantes desde el panel de organización de Supabase (**Team Settings -> Invite member**).
   - Cada integrante debe copiar `.env.example` a su propio `.env` local y configurar sus credenciales de forma privada. El archivo `.env` está excluido en `.gitignore` y protegido por `gitleaks` en GitHub Actions.
