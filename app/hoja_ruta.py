"""Generacion del PDF de la hoja de ruta.

Toma una Ruta ya optimizada y produce un PDF imprimible para el mecanico:
encabezado, resumen del recorrido, y una ficha por parada con espacio para
anotar horimetro, tareas realizadas y firma.

Requiere:
    pip install reportlab
"""

from __future__ import annotations

import re
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path

from app.config import Settings
from app.ruteador import Parada, Ruta, formato_duracion, link_google_maps
from app.utils import clean_text


# Paleta (gris/verde sobrio, imprime bien en blanco y negro)
COLOR_TITULO = "#1B4332"
COLOR_ACENTO = "#2D6A4F"
COLOR_SUAVE = "#D8F3DC"
COLOR_BORDE = "#95A5A6"
COLOR_TEXTO = "#212529"

DIAS_ES = [
    "LUNES", "MARTES", "MIERCOLES", "JUEVES",
    "VIERNES", "SABADO", "DOMINGO",
]


def fecha_larga(dia: date) -> str:
    """28/07/2026 -> 'MARTES 28/07/2026'"""
    return f"{DIAS_ES[dia.weekday()]} {dia:%d/%m/%Y}"


class PdfNoDisponible(RuntimeError):
    """Falta la libreria reportlab."""


def _importar_reportlab():
    """Verifica que reportlab este disponible y sea usable.

    Distingue tres casos para no dar mensajes enganosos:
      - reportlab no instalado
      - instalado pero corriendo en otro interprete (tipico con el EXE)
      - instalado pero falla un submodulo (version incompatible)
    """
    try:
        import reportlab
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise PdfNoDisponible(
            "reportlab no esta instalado en este Python.\n\n"
            f"Interprete en uso:\n  {sys.executable}\n\n"
            "Instalalo con:\n  python -m pip install reportlab\n\n"
            "Si estas corriendo el EXE, hay que regenerarlo con 'Crear EXE.bat' "
            "despues de instalar la libreria."
        ) from exc

    try:
        from reportlab.lib import colors  # noqa: F401
        from reportlab.lib.pagesizes import A4  # noqa: F401
        from reportlab.lib.styles import getSampleStyleSheet  # noqa: F401
        from reportlab.lib.units import mm  # noqa: F401
        from reportlab.platypus import (  # noqa: F401
            HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate,
            Spacer, Table, TableStyle,
        )
    except Exception as exc:  # noqa: BLE001
        version = getattr(reportlab, "Version", "?")
        raise PdfNoDisponible(
            f"reportlab {version} esta instalado pero no se pudo usar.\n\n"
            f"{type(exc).__name__}: {exc}\n\n"
            f"Interprete: {sys.executable}\n\n"
            "Probá con una version conocida:\n"
            "  python -m pip install \"reportlab>=4,<5\""
        ) from exc


def _slug(texto: str) -> str:
    """Convierte un texto en algo apto para nombre de archivo."""
    texto = unicodedata.normalize("NFKD", clean_text(texto))
    texto = texto.encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^A-Za-z0-9]+", "_", texto).strip("_")
    return texto[:40] or "sin_nombre"


def nombre_archivo(mecanico: str, dia: date) -> str:
    return f"HR_{dia:%Y-%m-%d}_{_slug(mecanico)}.pdf"


def generar_pdf(
    settings: Settings,
    ruta: Ruta,
    mecanico: str,
    dia: date,
    trabajos_taller: list[Parada] | None = None,
    destino: Path | None = None,
) -> Path:
    """Genera el PDF de la hoja de ruta y devuelve la ruta del archivo."""
    _importar_reportlab()

    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        HRFlowable,
        KeepTogether,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    trabajos_taller = trabajos_taller or []

    if destino is None:
        settings.hojas_ruta_dir.mkdir(parents=True, exist_ok=True)
        destino = settings.hojas_ruta_dir / nombre_archivo(mecanico, dia)
    destino.parent.mkdir(parents=True, exist_ok=True)

    base = getSampleStyleSheet()
    st_titulo = ParagraphStyle(
        "TituloHR", parent=base["Title"], fontSize=17, leading=20,
        textColor=colors.HexColor(COLOR_TITULO), spaceAfter=2,
    )
    st_sub = ParagraphStyle(
        "SubHR", parent=base["Normal"], fontSize=10, leading=13,
        textColor=colors.HexColor(COLOR_ACENTO), alignment=TA_CENTER, spaceAfter=8,
    )
    st_seccion = ParagraphStyle(
        "SeccionHR", parent=base["Heading2"], fontSize=11.5, leading=14,
        textColor=colors.HexColor(COLOR_TITULO), spaceBefore=10, spaceAfter=4,
    )
    st_normal = ParagraphStyle(
        "NormalHR", parent=base["Normal"], fontSize=9, leading=11.5,
        textColor=colors.HexColor(COLOR_TEXTO),
    )
    st_chico = ParagraphStyle(
        "ChicoHR", parent=st_normal, fontSize=7.5, leading=9.5,
        textColor=colors.HexColor("#5A6268"),
    )
    st_parada = ParagraphStyle(
        "ParadaHR", parent=st_normal, fontSize=11, leading=13,
        textColor=colors.HexColor(COLOR_TITULO),
    )

    def parrafo(texto, estilo=st_normal):
        return Paragraph(clean_text(texto).replace("\n", "<br/>"), estilo)

    doc = SimpleDocTemplate(
        str(destino),
        pagesize=A4,
        leftMargin=14 * mm, rightMargin=14 * mm,
        topMargin=13 * mm, bottomMargin=13 * mm,
        title=f"Hoja de ruta {mecanico} {dia:%d/%m/%Y}",
        author="Porta - Servicio Tecnico",
    )

    historia = []

    # ---------------------------------------------------------- encabezado
    historia.append(parrafo("HOJA DE RUTA", st_titulo))
    encabezado_sub = f"{(mecanico or 'Sin asignar').upper()}   -   {fecha_larga(dia)}"
    historia.append(parrafo(encabezado_sub, st_sub))

    total_min = ruta.min_conduccion
    resumen = [
        ["Paradas", "Km totales", "Tiempo de viaje", "Trabajos en taller"],
        [
            str(ruta.cantidad),
            f"{ruta.km_total:,.0f}".replace(",", "."),
            formato_duracion(total_min),
            str(len(trabajos_taller)),
        ],
    ]
    tabla_resumen = Table(resumen, colWidths=[45 * mm, 45 * mm, 45 * mm, 47 * mm])
    tabla_resumen.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(COLOR_TITULO)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor(COLOR_SUAVE)),
            ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 1), (-1, 1), 13),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(COLOR_BORDE)),
        ])
    )
    historia.append(tabla_resumen)

    if ruta.modo != "ors":
        historia.append(Spacer(1, 3 * mm))
        historia.append(
            parrafo(
                "Distancias y tiempos estimados en linea recta (sin datos de ruta real).",
                st_chico,
            )
        )

    enlace = link_google_maps(ruta)
    if enlace:
        historia.append(Spacer(1, 2 * mm))
        historia.append(
            Paragraph(
                f'<link href="{enlace}" color="#2D6A4F"><b>Abrir recorrido completo en Google Maps</b></link>',
                st_chico,
            )
        )

    # ------------------------------------------------------------- paradas
    if ruta.paradas:
        historia.append(parrafo("RECORRIDO", st_seccion))
        historia.append(
            HRFlowable(width="100%", thickness=1, color=colors.HexColor(COLOR_ACENTO), spaceAfter=4)
        )

        for parada in ruta.paradas:
            historia.append(_bloque_parada(parada, parrafo, st_parada, st_normal, st_chico))

        historia.append(Spacer(1, 3 * mm))
        historia.append(
            parrafo(
                f"Regreso al taller: {ruta.km_regreso:.0f} km  -  "
                f"{formato_duracion(ruta.min_regreso)}",
                st_chico,
            )
        )

    # ------------------------------------------------------ taller
    if trabajos_taller:
        historia.append(parrafo("TRABAJOS EN TALLER (sin desplazamiento)", st_seccion))
        historia.append(
            HRFlowable(width="100%", thickness=1, color=colors.HexColor(COLOR_ACENTO), spaceAfter=4)
        )
        filas = [["Soporte", "Cliente", "Equipo", "Tarea"]]
        for t in trabajos_taller:
            filas.append([
                Paragraph(clean_text(t.referencia), st_normal),
                Paragraph(clean_text(t.cliente), st_normal),
                Paragraph(clean_text(t.equipo), st_normal),
                Paragraph(clean_text(t.detalle), st_normal),
            ])
        tabla = Table(filas, colWidths=[18 * mm, 42 * mm, 34 * mm, 88 * mm], repeatRows=1)
        tabla.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(COLOR_TITULO)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor(COLOR_BORDE)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F3F5")]),
            ])
        )
        historia.append(tabla)

    # -------------------------------------------------------------- firma
    historia.append(Spacer(1, 8 * mm))
    firma = Table(
        [["Firma del mecanico", "Km inicial", "Km final", "Hora salida", "Hora regreso"],
         ["", "", "", "", ""]],
        colWidths=[62 * mm, 30 * mm, 30 * mm, 30 * mm, 30 * mm],
        rowHeights=[6 * mm, 14 * mm],
    )
    firma.setStyle(
        TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 7),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#5A6268")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor(COLOR_BORDE)),
        ])
    )
    historia.append(firma)

    historia.append(Spacer(1, 3 * mm))
    historia.append(
        parrafo(
            f"Generado {datetime.now():%d/%m/%Y %H:%M} - Sistema de Hojas de Ruta",
            st_chico,
        )
    )

    doc.build(historia)
    return destino


def _bloque_parada(parada: Parada, parrafo, st_parada, st_normal, st_chico):
    """Ficha de una parada: cabecera + datos + espacio para anotaciones."""
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table, TableStyle

    viaje = (
        f"{parada.km_desde_anterior:.0f} km  -  "
        f"{formato_duracion(parada.min_desde_anterior)} de viaje"
    )

    cabecera = Table(
        [[
            Paragraph(f"<b>{parada.orden}</b>", st_parada),
            Paragraph(
                f"<b>{clean_text(parada.cliente)}</b><br/>"
                f"<font size=8 color='#5A6268'>{clean_text(parada.lugar)}</font>",
                st_normal,
            ),
            Paragraph(f"<font size=7.5 color='#5A6268'>{viaje}</font>", st_chico),
        ]],
        colWidths=[10 * mm, 122 * mm, 50 * mm],
    )
    cabecera.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), colors.HexColor(COLOR_ACENTO)),
            ("TEXTCOLOR", (0, 0), (0, 0), colors.white),
            ("ALIGN", (0, 0), (0, 0), "CENTER"),
            ("ALIGN", (2, 0), (2, 0), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BACKGROUND", (1, 0), (-1, 0), colors.HexColor(COLOR_SUAVE)),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (1, 0), (1, 0), 6),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(COLOR_BORDE)),
        ])
    )

    datos = [
        ["Soporte", clean_text(parada.referencia) or "-",
         "Contacto", clean_text(parada.contacto) or "-"],
        ["Equipo", clean_text(parada.equipo) or "-",
         "Extras", clean_text(parada.extras) or "-"],
    ]
    tabla_datos = Table(
        [[Paragraph(f"<b>{c}</b>" if i % 2 == 0 else clean_text(c), st_normal)
          for i, c in enumerate(fila)] for fila in datos],
        colWidths=[20 * mm, 66 * mm, 20 * mm, 76 * mm],
    )
    tabla_datos.setStyle(
        TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.HexColor("#DEE2E6")),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor(COLOR_BORDE)),
        ])
    )

    tarea = Table(
        [[Paragraph("<b>Tarea a realizar</b>", st_normal)],
         [Paragraph(clean_text(parada.detalle) or "-", st_normal)]],
        colWidths=[182 * mm],
    )
    tarea.setStyle(
        TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#F1F3F5")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor(COLOR_BORDE)),
            ("LINEBELOW", (0, 0), (0, 0), 0.4, colors.HexColor(COLOR_BORDE)),
        ])
    )

    anotaciones = Table(
        [["Horimetro", "Hs trabajadas", "Repuestos usados", "Realizado"],
         ["", "", "", ""]],
        colWidths=[30 * mm, 30 * mm, 92 * mm, 30 * mm],
        rowHeights=[5 * mm, 11 * mm],
    )
    anotaciones.setStyle(
        TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 6.5),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#5A6268")),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor(COLOR_BORDE)),
        ])
    )

    return KeepTogether([
        cabecera, tabla_datos, tarea, anotaciones, Spacer(1, 5 * mm),
    ])
