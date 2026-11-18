"""
Servicios de calculo de reportes, proteccion contra inyeccion de formulas en CSV
y generacion de documentos PDF institucionales (Seccion 4.5 y 6).
"""
import csv
import io
from datetime import date
from typing import Any
from django.db.models import Avg, Max, Min
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from apps.cuentas.models import Usuario
from apps.deportes.models import Disciplina, Inscripcion
from apps.seguimiento.models import Asistencia, Evaluacion


PREFIJOS_PELIGROSOS_CSV = ("=", "+", "-", "@", "\t", "\r")


def sanitizar_celda_csv(valor: Any) -> str:
    """
    Previene la inyeccion de formulas en hojas de calculo (CSV Formula Injection)
    prefijando con una comilla simple (') cualquier celda cuyo texto comience con
    '=', '+', '-', '@', tabulador o retorno de carro (Seccion 4.5).
    """
    if valor is None:
        return ""
    texto = str(valor)
    texto_sin_espacios_izq = texto.lstrip(" ")
    if texto.startswith(PREFIJOS_PELIGROSOS_CSV) or texto_sin_espacios_izq.startswith(
        PREFIJOS_PELIGROSOS_CSV
    ):
        return f"'{texto}"
    return texto


def calcular_tendencia_evaluaciones(notas_ordenadas_cronologicamente: list[float]) -> str:
    """
    Calcula la tendencia de rendimiento comparando la primera mitad con la segunda mitad
    de las evaluaciones cronologicas: 'En alza', 'En baja', 'Estable' o 'Sin datos'.
    """
    n = len(notas_ordenadas_cronologicamente)
    if n == 0:
        return "Sin evaluaciones"
    if n == 1:
        return "Estable"
    mitad = n // 2
    prom_inicial = sum(notas_ordenadas_cronologicamente[:mitad]) / mitad
    prom_reciente = sum(notas_ordenadas_cronologicamente[mitad:]) / (n - mitad)
    diferencia = prom_reciente - prom_inicial
    if diferencia >= 0.2:
        return "En alza"
    if diferencia <= -0.2:
        return "En baja"
    return "Estable"


def construir_datos_reporte(
    *,
    usuario_solicitante: Usuario,
    disciplina_id: str = "",
    entrenador_id: str = "",
    estudiante_id: str = "",
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
) -> dict[str, Any]:
    """
    Construye las metricas y tablas del reporte aplicando aislamiento estricto por rol:
    - Coordinador: alcance completo sobre todas las disciplinas, entrenadores y estudiantes.
    - Entrenador: alcance restringido exclusivamente a sus disciplinas asignadas.
    - Estudiante: alcance restringido exclusivamente a su propio perfil.
    """
    disciplinas_qs = Disciplina.objects.all()
    inscripciones_qs = Inscripcion.objects.select_related(
        "estudiante", "disciplina"
    ).all()
    asistencias_qs = Asistencia.objects.select_related(
        "sesion", "sesion__disciplina", "estudiante"
    ).all()
    evaluaciones_qs = Evaluacion.objects.select_related(
        "sesion", "sesion__disciplina", "estudiante"
    ).all()

    # 1. Restriccion obligatoria de alcance segun el rol en el servidor
    if usuario_solicitante.es_entrenador:
        perfil_ent = getattr(usuario_solicitante, "perfil_entrenador", None)
        disciplinas_qs = disciplinas_qs.filter(
            asignaciones_entrenador__entrenador=perfil_ent
        ).distinct()
        inscripciones_qs = inscripciones_qs.filter(disciplina__in=disciplinas_qs)
        asistencias_qs = asistencias_qs.filter(sesion__disciplina__in=disciplinas_qs)
        evaluaciones_qs = evaluaciones_qs.filter(sesion__disciplina__in=disciplinas_qs)

    elif usuario_solicitante.es_estudiante:
        perfil_est = getattr(usuario_solicitante, "perfil_estudiante", None)
        estudiante_id = str(perfil_est.id) if perfil_est else ""
        disciplinas_qs = disciplinas_qs.filter(
            inscripciones__estudiante=perfil_est
        ).distinct()
        inscripciones_qs = inscripciones_qs.filter(estudiante=perfil_est)
        asistencias_qs = asistencias_qs.filter(estudiante=perfil_est)
        evaluaciones_qs = evaluaciones_qs.filter(estudiante=perfil_est)

    # 2. Aplicacion de filtros seleccionados por el usuario (dentro de su alcance)
    if entrenador_id and usuario_solicitante.es_coordinador:
        disciplinas_qs = disciplinas_qs.filter(
            asignaciones_entrenador__entrenador_id=entrenador_id
        ).distinct()
        inscripciones_qs = inscripciones_qs.filter(disciplina__in=disciplinas_qs)
        asistencias_qs = asistencias_qs.filter(sesion__disciplina__in=disciplinas_qs)
        evaluaciones_qs = evaluaciones_qs.filter(sesion__disciplina__in=disciplinas_qs)

    if disciplina_id:
        disciplinas_qs = disciplinas_qs.filter(id=disciplina_id)
        inscripciones_qs = inscripciones_qs.filter(disciplina_id=disciplina_id)
        asistencias_qs = asistencias_qs.filter(sesion__disciplina_id=disciplina_id)
        evaluaciones_qs = evaluaciones_qs.filter(sesion__disciplina_id=disciplina_id)

    if estudiante_id and not usuario_solicitante.es_estudiante:
        inscripciones_qs = inscripciones_qs.filter(estudiante_id=estudiante_id)
        asistencias_qs = asistencias_qs.filter(estudiante_id=estudiante_id)
        evaluaciones_qs = evaluaciones_qs.filter(estudiante_id=estudiante_id)

    if fecha_desde:
        asistencias_qs = asistencias_qs.filter(sesion__fecha__gte=fecha_desde)
        evaluaciones_qs = evaluaciones_qs.filter(sesion__fecha__gte=fecha_desde)

    if fecha_hasta:
        asistencias_qs = asistencias_qs.filter(sesion__fecha__lte=fecha_hasta)
        evaluaciones_qs = evaluaciones_qs.filter(sesion__fecha__lte=fecha_hasta)

    # 3. Calculos de asistencia
    total_asistencias = asistencias_qs.count()
    presentes = asistencias_qs.filter(estado=Asistencia.ESTADO_PRESENTE).count()
    justificados = asistencias_qs.filter(estado=Asistencia.ESTADO_JUSTIFICADO).count()
    ausentes = asistencias_qs.filter(estado=Asistencia.ESTADO_AUSENTE).count()
    porcentaje_asistencia = (
        round(((presentes + justificados) / total_asistencias) * 100.0, 1)
        if total_asistencias > 0
        else 0.0
    )

    # 4. Calculos de rendimiento (promedio, minimo, maximo, tendencia)
    agregados_eval = evaluaciones_qs.aggregate(
        promedio=Avg("puntaje"),
        minimo=Min("puntaje"),
        maximo=Max("puntaje"),
    )
    notas_cronologicas = [
        float(n)
        for n in evaluaciones_qs.order_by("sesion__fecha", "creado_en").values_list(
            "puntaje", flat=True
        )
    ]
    tendencia = calcular_tendencia_evaluaciones(notas_cronologicas)

    # 5. Ocupacion de cupos e inscripciones
    resumen_disciplinas = []
    for disc in disciplinas_qs.order_by("nombre"):
        activas_disc = disc.inscripciones.filter(
            estado=Inscripcion.ESTADO_ACTIVA, estudiante__activo=True
        ).count()
        bajas_disc = disc.inscripciones.filter(estado=Inscripcion.ESTADO_BAJA).count()
        ocupacion_pct = (
            round((activas_disc / disc.cupo_maximo) * 100.0, 1)
            if disc.cupo_maximo > 0
            else 0.0
        )
        resumen_disciplinas.append(
            {
                "disciplina": disc,
                "inscripciones_activas": activas_disc,
                "inscripciones_baja": bajas_disc,
                "cupo_maximo": disc.cupo_maximo,
                "porcentaje_ocupacion": ocupacion_pct,
            }
        )

    # 6. Detalle combinado por sesion y estudiante para tablas y exportacion
    mapa_eval = {
        (e.sesion_id, e.estudiante_id): e
        for e in evaluaciones_qs
    }
    filas_detalle = []
    for asist in asistencias_qs.order_by("-sesion__fecha", "estudiante__apellidos"):
        ev = mapa_eval.get((asist.sesion_id, asist.estudiante_id))
        filas_detalle.append(
            {
                "fecha": asist.sesion.fecha,
                "disciplina": asist.sesion.disciplina.nombre,
                "estudiante": asist.estudiante.nombre_completo,
                "rut": asist.estudiante.rut_formateado,
                "curso_o_carrera": asist.estudiante.curso_o_carrera,
                "estado_asistencia": asist.get_estado_display(),
                "puntaje": f"{ev.puntaje:.1f}".replace(".", ",") if ev else "—",
                "observacion": (ev.observacion if ev and ev.observacion else asist.observacion) or "—",
            }
        )

    return {
        "total_asistencias": total_asistencias,
        "presentes": presentes,
        "justificados": justificados,
        "ausentes": ausentes,
        "porcentaje_asistencia": porcentaje_asistencia,
        "promedio_rendimiento": (
            round(float(agregados_eval["promedio"]), 1)
            if agregados_eval["promedio"] is not None
            else None
        ),
        "minimo_rendimiento": (
            round(float(agregados_eval["minimo"]), 1)
            if agregados_eval["minimo"] is not None
            else None
        ),
        "maximo_rendimiento": (
            round(float(agregados_eval["maximo"]), 1)
            if agregados_eval["maximo"] is not None
            else None
        ),
        "tendencia_rendimiento": tendencia,
        "total_inscripciones_activas": inscripciones_qs.filter(
            estado=Inscripcion.ESTADO_ACTIVA
        ).count(),
        "resumen_disciplinas": resumen_disciplinas,
        "filas_detalle": filas_detalle,
    }


def generar_csv_reporte(datos_reporte: dict[str, Any]) -> str:
    """
    Genera el contenido CSV del reporte sanitizando cada celda contra inyeccion de formulas.
    Incluye BOM UTF-8 para correcta lectura de tildes y enes en Excel.
    """
    buffer = io.StringIO()
    buffer.write("\ufeff")
    escritor = csv.writer(buffer, delimiter=";")

    escritor.writerow(
        [
            "Fecha",
            "Disciplina",
            "Estudiante",
            "RUT",
            "Curso o Carrera",
            "Estado de Asistencia",
            "Puntaje (Escala 1,0 a 7,0)",
            "Observación",
        ]
    )

    for fila in datos_reporte["filas_detalle"]:
        escritor.writerow(
            [
                sanitizar_celda_csv(fila["fecha"].strftime("%d/%m/%Y")),
                sanitizar_celda_csv(fila["disciplina"]),
                sanitizar_celda_csv(fila["estudiante"]),
                sanitizar_celda_csv(fila["rut"]),
                sanitizar_celda_csv(fila["curso_o_carrera"]),
                sanitizar_celda_csv(fila["estado_asistencia"]),
                sanitizar_celda_csv(fila["puntaje"]),
                sanitizar_celda_csv(fila["observacion"]),
            ]
        )
    return buffer.getvalue()


def generar_pdf_reporte(
    datos_reporte: dict[str, Any], usuario_solicitante: Usuario
) -> bytes:
    """Genera un documento PDF institucional con el resumen y detalle del reporte."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
        title="Reporte Deportivo PALESTRA",
    )
    estilos = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle(
        "TituloPalestra",
        parent=estilos["Heading1"],
        fontSize=16,
        textColor=colors.HexColor("#0B2545"),
        spaceAfter=6,
    )
    estilo_subtitulo = ParagraphStyle(
        "SubtituloPalestra",
        parent=estilos["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#5B6776"),
        spaceAfter=14,
    )

    elementos = [
        Paragraph(
            "PALESTRA — Reporte de Gestión Deportiva Estudiantil", estilo_titulo
        ),
        Paragraph(
            f"Generado por: {usuario_solicitante.nombre_completo} ({usuario_solicitante.get_rol_display()})",
            estilo_subtitulo,
        ),
    ]

    prom_str = (
        f"{datos_reporte['promedio_rendimiento']:.1f}".replace(".", ",")
        if datos_reporte["promedio_rendimiento"] is not None
        else "Sin datos"
    )
    min_str = (
        f"{datos_reporte['minimo_rendimiento']:.1f}".replace(".", ",")
        if datos_reporte["minimo_rendimiento"] is not None
        else "—"
    )
    max_str = (
        f"{datos_reporte['maximo_rendimiento']:.1f}".replace(".", ",")
        if datos_reporte["maximo_rendimiento"] is not None
        else "—"
    )

    tabla_resumen_datos = [
        ["Indicador", "Valor"],
        [
            "Asistencia Cumplida",
            f"{datos_reporte['porcentaje_asistencia']:.1f} % ({datos_reporte['presentes']} presentes, {datos_reporte['justificados']} justificados, {datos_reporte['ausentes']} ausentes)",
        ],
        [
            "Rendimiento (Promedio / Mín / Máx)",
            f"{prom_str} (Mín.: {min_str} / Máx.: {max_str})",
        ],
        ["Tendencia de Rendimiento", datos_reporte["tendencia_rendimiento"]],
        [
            "Inscripciones Activas en el Alcance",
            str(datos_reporte["total_inscripciones_activas"]),
        ],
    ]

    tabla_resumen = Table(tabla_resumen_datos, colWidths=[190, 330])
    tabla_resumen.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B2545")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9DFE7")),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elementos.append(tabla_resumen)
    elementos.append(Spacer(1, 16))

    encabezados_detalle = [
        ["Fecha", "Disciplina", "Estudiante", "Asistencia", "Nota"]
    ]
    filas_pdf = [
        [
            f["fecha"].strftime("%d/%m/%Y"),
            f["disciplina"][:26],
            f["estudiante"][:28],
            f["estado_asistencia"],
            f["puntaje"],
        ]
        for f in datos_reporte["filas_detalle"][:80]
    ]
    if not filas_pdf:
        filas_pdf = [["Sin registros", "—", "—", "—", "—"]]

    tabla_detalle = Table(
        encabezados_detalle + filas_pdf, colWidths=[65, 145, 155, 85, 70]
    )
    tabla_detalle.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1D4E89")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9DFE7")),
                ("PADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    elementos.append(tabla_detalle)

    doc.build(elementos)
    return buffer.getvalue()
