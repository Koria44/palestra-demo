-- =============================================================================
-- PALESTRA — Gestion de Actividades Deportivas Estudiantiles
-- Archivo: supabase/roles.sql
-- Descripcion: Crea el rol dedicado de base de datos 'palestra_app' con privilegios
-- minimos (principio de menor privilegio, ISO/IEC 27002) para que la aplicacion
-- Django en produccion no se conecte usando el superusuario 'postgres'.
-- =============================================================================

-- NOTA: Al ejecutar este script en el SQL Editor de Supabase, reemplace
-- 'CAMBIAR_POR_CONTRASENA_ALEATORIA_DEL_GESTOR_DE_SECRETOS' por una clave generada
-- fuera del repositorio y configurela en DATABASE_URL dentro de su archivo .env.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'palestra_app') THEN
        CREATE ROLE palestra_app WITH
            LOGIN
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOINHERIT
            NOREPLICATION
            BYPASSRLS
            PASSWORD 'CAMBIAR_POR_CONTRASENA_ALEATORIA_DEL_GESTOR_DE_SECRETOS';
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO palestra_app;

-- Otorga solo permisos DML necesarios (SELECT, INSERT, UPDATE, DELETE) sobre las tablas
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO palestra_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO palestra_app;

-- Proteccion adicional sobre la bitacora de auditoria: prohibe DELETE y UPDATE en BD
REVOKE UPDATE, DELETE ON TABLE public.registro_auditoria FROM palestra_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO palestra_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO palestra_app;
