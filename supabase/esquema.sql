-- =============================================================================
-- PALESTRA — Gestion de Actividades Deportivas Estudiantiles
-- Archivo: supabase/esquema.sql
-- Descripcion: Esquema relacional normalizado (3FN) para PostgreSQL (Supabase).
-- Nota: Las migraciones de Django son la fuente de verdad del esquema. Este archivo
-- refleja la estructura SQL generada por las migraciones con restricciones CHECK,
-- UNIQUE, claves foraneas con ON DELETE RESTRICT/PROTECT e indices de rendimiento.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. Tabla: usuario (hereda de AbstractUser con campos en espanol)
CREATE TABLE IF NOT EXISTS public.usuario (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    password VARCHAR(128) NOT NULL,
    last_login TIMESTAMPTZ NULL,
    is_superuser BOOLEAN NOT NULL DEFAULT FALSE,
    username VARCHAR(150) NOT NULL UNIQUE,
    first_name VARCHAR(150) NOT NULL DEFAULT '',
    last_name VARCHAR(150) NOT NULL DEFAULT '',
    is_staff BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    date_joined TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    email VARCHAR(254) NOT NULL UNIQUE,
    rol VARCHAR(20) NOT NULL DEFAULT 'estudiante' CHECK (rol IN ('coordinador', 'entrenador', 'estudiante')),
    debe_cambiar_contrasena BOOLEAN NOT NULL DEFAULT FALSE,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    ultimo_acceso TIMESTAMPTZ NULL,
    hash_token_activacion VARCHAR(64) NOT NULL DEFAULT '',
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_usuario_rol_activo ON public.usuario (rol, activo);

-- 2. Tabla: perfil_estudiante (datos sensibles cifrados en reposo con MultiFernet + indice ciego HMAC)
CREATE TABLE IF NOT EXISTS public.perfil_estudiante (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id UUID NOT NULL UNIQUE REFERENCES public.usuario(id) ON DELETE RESTRICT,
    rut TEXT NOT NULL,
    rut_indice_ciego VARCHAR(64) NOT NULL UNIQUE,
    nombres VARCHAR(100) NOT NULL,
    apellidos VARCHAR(100) NOT NULL,
    curso_o_carrera VARCHAR(120) NOT NULL,
    telefono TEXT NOT NULL DEFAULT '',
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_estudiante_activo_ape ON public.perfil_estudiante (activo, apellidos);

-- 3. Tabla: perfil_entrenador (datos sensibles cifrados en reposo con MultiFernet + indice ciego HMAC)
CREATE TABLE IF NOT EXISTS public.perfil_entrenador (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id UUID NOT NULL UNIQUE REFERENCES public.usuario(id) ON DELETE RESTRICT,
    rut TEXT NOT NULL,
    rut_indice_ciego VARCHAR(64) NOT NULL UNIQUE,
    nombres VARCHAR(100) NOT NULL,
    apellidos VARCHAR(100) NOT NULL,
    especialidad VARCHAR(120) NOT NULL,
    telefono TEXT NOT NULL DEFAULT '',
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_entrenador_activo_ape ON public.perfil_entrenador (activo, apellidos);

-- 4. Tabla: disciplina
CREATE TABLE IF NOT EXISTS public.disciplina (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre VARCHAR(100) NOT NULL UNIQUE,
    descripcion TEXT NOT NULL,
    cupo_maximo INTEGER NOT NULL CONSTRAINT chk_disciplina_cupo_positivo CHECK (cupo_maximo > 0),
    dia VARCHAR(20) NOT NULL,
    hora_inicio TIME NOT NULL,
    hora_termino TIME NOT NULL,
    lugar VARCHAR(120) NOT NULL,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_disciplina_horario_coherente CHECK (hora_termino > hora_inicio)
);

CREATE INDEX IF NOT EXISTS idx_disciplina_activo_nom ON public.disciplina (activo, nombre);

-- 5. Tabla: entrenador_disciplina
CREATE TABLE IF NOT EXISTS public.entrenador_disciplina (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entrenador_id UUID NOT NULL REFERENCES public.perfil_entrenador(id) ON DELETE RESTRICT,
    disciplina_id UUID NOT NULL REFERENCES public.disciplina(id) ON DELETE RESTRICT,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_entrenador_disciplina_par UNIQUE (entrenador_id, disciplina_id)
);

CREATE INDEX IF NOT EXISTS idx_ent_disc_par ON public.entrenador_disciplina (entrenador_id, disciplina_id);

-- 6. Tabla: inscripcion (con indice unico parcial para estudiante + disciplina activa)
CREATE TABLE IF NOT EXISTS public.inscripcion (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    estudiante_id UUID NOT NULL REFERENCES public.perfil_estudiante(id) ON DELETE RESTRICT,
    disciplina_id UUID NOT NULL REFERENCES public.disciplina(id) ON DELETE RESTRICT,
    fecha_inscripcion DATE NOT NULL DEFAULT CURRENT_DATE,
    estado VARCHAR(15) NOT NULL DEFAULT 'activa' CHECK (estado IN ('activa', 'baja')),
    fecha_baja DATE NULL,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_inscripcion_estudiante_disciplina_activa
    ON public.inscripcion (estudiante_id, disciplina_id)
    WHERE estado = 'activa';

CREATE INDEX IF NOT EXISTS idx_inscripcion_disc_estado ON public.inscripcion (disciplina_id, estado);
CREATE INDEX IF NOT EXISTS idx_inscripcion_est_estado ON public.inscripcion (estudiante_id, estado);

-- 7. Tabla: sesion_entrenamiento
CREATE TABLE IF NOT EXISTS public.sesion_entrenamiento (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    disciplina_id UUID NOT NULL REFERENCES public.disciplina(id) ON DELETE RESTRICT,
    fecha DATE NOT NULL CONSTRAINT chk_sesion_fecha_no_futura CHECK (fecha <= CURRENT_DATE),
    entrenador_id UUID NOT NULL REFERENCES public.perfil_entrenador(id) ON DELETE RESTRICT,
    tema VARCHAR(160) NOT NULL DEFAULT '',
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_sesion_disciplina_fecha UNIQUE (disciplina_id, fecha)
);

CREATE INDEX IF NOT EXISTS idx_sesion_disc_fecha ON public.sesion_entrenamiento (disciplina_id, fecha);

-- 8. Tabla: asistencia
CREATE TABLE IF NOT EXISTS public.asistencia (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sesion_id UUID NOT NULL REFERENCES public.sesion_entrenamiento(id) ON DELETE RESTRICT,
    estudiante_id UUID NOT NULL REFERENCES public.perfil_estudiante(id) ON DELETE RESTRICT,
    estado VARCHAR(15) NOT NULL DEFAULT 'presente' CHECK (estado IN ('presente', 'ausente', 'justificado')),
    observacion VARCHAR(250) NOT NULL DEFAULT '',
    registrado_por_id UUID NOT NULL REFERENCES public.usuario(id) ON DELETE RESTRICT,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_asistencia_sesion_estudiante UNIQUE (sesion_id, estudiante_id)
);

CREATE INDEX IF NOT EXISTS idx_asistencia_est_estado ON public.asistencia (estudiante_id, estado);
CREATE INDEX IF NOT EXISTS idx_asistencia_ses_estado ON public.asistencia (sesion_id, estado);

-- 9. Tabla: evaluacion (escala chilena 1.0 a 7.0)
CREATE TABLE IF NOT EXISTS public.evaluacion (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sesion_id UUID NOT NULL REFERENCES public.sesion_entrenamiento(id) ON DELETE RESTRICT,
    estudiante_id UUID NOT NULL REFERENCES public.perfil_estudiante(id) ON DELETE RESTRICT,
    puntaje NUMERIC(3, 1) NOT NULL CONSTRAINT chk_evaluacion_puntaje_escala_chilena CHECK (puntaje >= 1.0 AND puntaje <= 7.0),
    observacion VARCHAR(250) NOT NULL DEFAULT '',
    registrado_por_id UUID NOT NULL REFERENCES public.usuario(id) ON DELETE RESTRICT,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_evaluacion_sesion_estudiante UNIQUE (sesion_id, estudiante_id)
);

CREATE INDEX IF NOT EXISTS idx_evaluacion_est_puntaje ON public.evaluacion (estudiante_id, puntaje);
CREATE INDEX IF NOT EXISTS idx_evaluacion_ses_est ON public.evaluacion (sesion_id, estudiante_id);

-- 10. Tabla: registro_auditoria (bitacora inmutable)
CREATE TABLE IF NOT EXISTS public.registro_auditoria (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id UUID NULL REFERENCES public.usuario(id) ON DELETE RESTRICT,
    accion VARCHAR(80) NOT NULL,
    entidad VARCHAR(80) NOT NULL,
    identificador VARCHAR(120) NOT NULL DEFAULT '',
    fecha TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    direccion_ip INET NULL,
    detalle JSONB NOT NULL DEFAULT '{}'::jsonb,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_auditoria_accion_fecha ON public.registro_auditoria (accion, fecha);
CREATE INDEX IF NOT EXISTS idx_auditoria_entidad_fecha ON public.registro_auditoria (entidad, fecha);
