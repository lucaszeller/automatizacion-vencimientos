"""Generacion del Excel mensual de control."""

from datetime import date
from pathlib import Path

import pandas as pd
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.utils import MONTH_NAMES


REPORT_COLUMNS = [
    ("Fecha", "fecha_service_actual"),
    ("Nº Soporte", "soporte_actual"),
    ("HORAS ", "horas_actuales"),
    ("TIPO DE SERV.", "tipo_service_actual"),
    ("Cliente", "cliente"),
    ("Serializado", "serial"),
    ("Lugar", "lugar"),
    ("FECHA ANTE ULTIMO SERV.", "fecha_service_anterior"),
    ("Nº SOPORTE", "soporte_anterior"),
    ("HORAS", "horas_anteriores"),
    ("TIPO DE SERV.", "tipo_service_anterior"),
    ("PROMEDIO HS DE USO.", "promedio_horas_dia"),
    ("FECHA ESTIMADA PROXIMO SERVI.", "fecha_estimada_proximo_service"),
    ("ESTADO", "estado"),
]


def generate_report(df: pd.DataFrame, output_dir: Path, run_date: date | None = None, period_label: str | None = None) -> Path:
    run_date = run_date or date.today()
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = period_label or run_date.isoformat()
    output_path = output_dir / f"services_control_{suffix}.xlsx"
    export = pd.concat([df.get(column) for _, column in REPORT_COLUMNS], axis=1)
    export.columns = [title for title, _ in REPORT_COLUMNS]

    sheet_name = MONTH_NAMES[run_date.month]
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        export.to_excel(writer, index=False, sheet_name=sheet_name, startrow=2)
        ws = writer.book[sheet_name]
        _style_sheet(ws)
    return output_path


def _style_sheet(ws) -> None:
    max_col = ws.max_column
    current_fill = PatternFill("solid", fgColor="C6E0B4")
    previous_fill = PatternFill("solid", fgColor="F8CBAD")
    next_fill = PatternFill("solid", fgColor="70AD47")
    status_fill = PatternFill("solid", fgColor="A9D18E")
    alert_fill = PatternFill("solid", fgColor="F4CCCC")
    warning_fill = PatternFill("solid", fgColor="FFF2CC")
    missing_fill = PatternFill("solid", fgColor="D9EAF7")
    error_fill = PatternFill("solid", fgColor="EADCF8")
    thin = Side(style="thin", color="000000")
    medium = Side(style="medium", color="7F7F7F")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    section_border = Border(left=medium, right=medium, top=medium, bottom=medium)

    sections = {
        "SERVICIO ACTUAL": (1, 7, current_fill),
        "SERVICIO ANTERIOR": (8, 12, previous_fill),
    }
    for title, (start, end, fill) in sections.items():
        cell = ws.cell(row=2, column=start, value=title)
        cell.font = Font(bold=True, size=14)
        cell.alignment = Alignment(horizontal="centerContinuous")
        cell.fill = fill
        cell.border = section_border
        for col in range(start, end + 1):
            ws.cell(row=2, column=col).fill = fill
            ws.cell(row=2, column=col).border = section_border
            ws.cell(row=2, column=col).alignment = Alignment(horizontal="centerContinuous")

    ws.cell(row=2, column=13, value="PROXIMO SERVICIO")
    ws.cell(row=2, column=13).font = Font(bold=True, size=14)
    ws.cell(row=2, column=13).alignment = Alignment(horizontal="center")
    ws.cell(row=2, column=13).fill = next_fill
    ws.cell(row=2, column=13).border = section_border
    ws.cell(row=2, column=14).fill = status_fill
    ws.cell(row=2, column=14).border = section_border

    for cell in ws[3]:
        cell.font = Font(bold=True, size=11)
        if 1 <= cell.column <= 7:
            cell.fill = current_fill
        elif 8 <= cell.column <= 12:
            cell.fill = previous_fill
        elif cell.column == 13:
            cell.fill = next_fill
        elif cell.column == 14:
            cell.fill = status_fill
        cell.alignment = Alignment(horizontal="center", wrap_text=True)
        cell.border = border

    for row in range(4, ws.max_row + 1):
        state = ws.cell(row=row, column=14).value
        for col in range(1, max_col + 1):
            cell = ws.cell(row=row, column=col)
            cell.border = border
            if 1 <= col <= 7:
                cell.fill = current_fill
            elif 8 <= col <= 12:
                cell.fill = previous_fill
            elif col == 13:
                cell.fill = next_fill
                cell.font = Font(bold=True, size=12)
            elif col == 14:
                if state in {"PROXIMO_A_VENCER", "VENCE_HOY", "VENCIDO"}:
                    cell.fill = alert_fill
                elif state in {"SIN_DATOS", "SIN_MAIL"}:
                    cell.fill = warning_fill
                elif state == "ERROR_CALCULO":
                    cell.fill = error_fill
                else:
                    cell.fill = status_fill

        if state in {"PROXIMO_A_VENCER", "VENCE_HOY", "VENCIDO"}:
            ws.cell(row=row, column=14).font = Font(bold=True, color="9C0006")
        elif state in {"SIN_DATOS", "SIN_MAIL"}:
            ws.cell(row=row, column=14).font = Font(bold=True, color="7F6000")
        elif state == "ERROR_CALCULO":
            ws.cell(row=row, column=14).font = Font(bold=True, color="7030A0")

    widths = {
        1: 13,
        2: 9.5,
        3: 7,
        4: 12,
        5: 28,
        6: 23,
        7: 8,
        8: 13,
        9: 13,
        10: 13,
        11: 13,
        12: 13,
        13: 21,
        14: 18,
    }
    for col in range(1, max_col + 1):
        ws.column_dimensions[get_column_letter(col)].width = widths.get(col, 16)

    for row in range(4, ws.max_row + 1):
        for col in (1, 8, 13):
            ws.cell(row=row, column=col).number_format = "dd/mm/yyyy"
        ws.cell(row=row, column=12).number_format = "0.00"
        ws.row_dimensions[row].height = 34

    for row in ws.iter_rows():
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    for row in (2, 3):
        ws.row_dimensions[row].height = 28
    for row in range(1, ws.max_row + 1):
        for col in range(1, max_col + 1):
            ws.cell(row=row, column=col).border = border
    ws.auto_filter.ref = f"A3:{get_column_letter(max_col)}{ws.max_row}"
    ws.freeze_panes = None
