-- =============================================================================
-- PALESTRA — Gestion de Actividades Deportivas Estudiantiles
-- Archivo: supabase/datos_demo.sql
-- Descripcion: Semilla SQL con datos ficticios de demostracion equivalentes al
-- comando `python manage.py cargar_datos_demo`.
-- IMPORTANTE: Las contrasenas estan almacenadas como hash Argon2id y los campos
-- RUT y telefono estan cifrados con Fernet (prefijo 'enc1:').
-- =============================================================================

BEGIN;

-- 1. Disciplinas deportivas ficticias
INSERT INTO public.disciplina (id, nombre, descripcion, cupo_maximo, dia, hora_inicio, hora_termino, lugar, activo, creado_en, actualizado_en)
VALUES
  ('11111111-1111-4111-8111-111111111101', 'Fútbol Varones y Damas', 'Entrenamiento táctico, técnico y preparación física en cancha sintética.', 22, 'Lunes', '16:00:00', '18:00:00', 'Cancha Sintética Central', TRUE, NOW(), NOW()),
  ('11111111-1111-4111-8111-111111111102', 'Básquetbol Universitario', 'Fundamentos ofensivos, defensivos y sistemas de juego en gimnasio techado.', 15, 'Miercoles', '17:00:00', '19:00:00', 'Gimnasio Polideportivo A', TRUE, NOW(), NOW()),
  ('11111111-1111-4111-8111-111111111103', 'Atletismo y Velocidad', 'Pruebas de pista, resistencia aeróbica, relevos y técnica de carrera.', 20, 'Martes', '15:30:00', '17:30:00', 'Pista Atlética Institucional', TRUE, NOW(), NOW()),
  ('11111111-1111-4111-8111-111111111104', 'Vóleibol Mixto', 'Técnica de recepción, armado, bloqueo y trabajo en equipo.', 18, 'Jueves', '16:30:00', '18:30:00', 'Gimnasio Polideportivo B', TRUE, NOW(), NOW()),
  ('11111111-1111-4111-8111-111111111105', 'Natación Formativa', 'Estilos crol, espalda y resistencia en piscina temperada semiolímpica.', 12, 'Viernes', '14:00:00', '16:00:00', 'Piscina Temperada Institucional', TRUE, NOW(), NOW())
ON CONFLICT (nombre) DO NOTHING;

-- Nota: Para poblar los usuarios, perfiles cifrados con las claves del entorno local (.env),
-- inscripciones y sesiones con asistencia y evaluaciones, ejecute:
--   python manage.py cargar_datos_demo

COMMIT;
