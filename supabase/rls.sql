-- =============================================================================
-- PALESTRA — Gestion de Actividades Deportivas Estudiantiles
-- Archivo: supabase/rls.sql
-- Descripcion: Habilita Row Level Security (RLS) en TODAS las tablas del esquema
-- publico (incluidas las tablas de sistema de Django y las tablas de negocio),
-- sin crear politicas permisivas para los roles 'anon' ni 'authenticated'.
-- De este modo, la API publica PostgREST de Supabase queda completamente bloqueada
-- como defensa en profundidad, mientras el backend Django opera con su rol de servidor.
-- =============================================================================

DO $$
DECLARE
    registro_tabla RECORD;
BEGIN
    FOR registro_tabla IN
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
    LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY;', registro_tabla.tablename);
        EXECUTE format('REVOKE ALL ON TABLE public.%I FROM anon, authenticated;', registro_tabla.tablename);
    END LOOP;
END
$$;

-- Verificacion explicita sobre las tablas principales del modelo de datos PALESTRA
ALTER TABLE IF EXISTS public.usuario ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.perfil_estudiante ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.perfil_entrenador ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.disciplina ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.entrenador_disciplina ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.inscripcion ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.sesion_entrenamiento ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.asistencia ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.evaluacion ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.registro_auditoria ENABLE ROW LEVEL SECURITY;
