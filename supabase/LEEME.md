# Configuración de Supabase (PostgreSQL) para PALESTRA

Este directorio contiene los scripts SQL de infraestructura, seguridad en profundidad (Row Level Security) y principio de menor privilegio para conectar **PALESTRA** con **Supabase**.

## 1. Fuente de Verdad del Esquema

Las **migraciones de Django** (`apps/*/migrations/`) son la única fuente de verdad del esquema de base de datos. Al conectar un proyecto nuevo de Supabase:

1. Configure `DATABASE_URL` (pooler en modo transacción, puerto `6543`) y `DATABASE_URL_DIRECT` (conexión directa, puerto `5432`) en su archivo `.env` con `sslmode=require`, y establezca `USAR_SQLITE_LOCAL=False`.
2. Ejecute las migraciones desde la raíz del proyecto:
   ```bash
   python manage.py migrate
   ```
3. El archivo `supabase/esquema.sql` documenta el DDL completo equivalente (tablas en español, restricciones `CHECK`, `UNIQUE`, claves foráneas con `ON DELETE RESTRICT` e índices).

## 2. Defensa en Profundidad: Row Level Security (`rls.sql`)

En Supabase, todas las tablas del esquema `public` quedan expuestas por defecto a la API automática PostgREST si no se activa RLS. Debido a que toda la lógica de negocio y permisos de PALESTRA reside en el servidor Django:

- Abra el **SQL Editor** en el panel de Supabase y ejecute el contenido de `supabase/rls.sql`.
- Este script habilita `ROW LEVEL SECURITY` en todas las tablas del esquema `public` y revoca permisos a los roles `anon` y `authenticated` sin crear políticas públicas. Así, cualquier intento de consultar la API pública de Supabase desde fuera del backend Django es rechazado automáticamente.

## 3. Rol de Aplicación con Privilegios Mínimos (`roles.sql`)

Para cumplir con el control de menor privilegio (ISO/IEC 27002), la aplicación en producción no debe conectarse usando el superusuario `postgres`:

1. En el **SQL Editor** de Supabase, reemplace la contraseña de ejemplo dentro de `supabase/roles.sql` por una contraseña robusta generada fuera del repositorio y ejecute el script.
2. El rol `palestra_app` posee únicamente permisos `SELECT, INSERT, UPDATE, DELETE` sobre las tablas del esquema `public`, y tiene revocados los permisos `UPDATE` y `DELETE` sobre la tabla `registro_auditoria` para reforzar su inmutabilidad a nivel de motor de base de datos.

## 4. Respaldos y Restauración

- **Respaldos de infraestructura en Supabase:** Los respaldos automáticos diarios y la recuperación en un punto en el tiempo (PITR) en Supabase dependen del plan contratado (planes Pro y superiores).
- **Respaldo lógico cifrado en la aplicación:** PALESTRA incluye el comando de gestión `exportar_respaldo`, que genera un volcado lógico íntegro cifrado con **Fernet / MultiFernet (AES autenticado)**:
  ```bash
  # Generar respaldo cifrado en respaldos/respaldo_palestra_YYYYMMDD_HHMMSS.json.enc
  python manage.py exportar_respaldo

  # Verificar y descifrar un respaldo existente
  python manage.py exportar_respaldo --descifrar respaldos/archivo.json.enc
  ```
