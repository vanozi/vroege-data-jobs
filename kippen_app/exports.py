"""Export helpers for the kippen registration app."""

from csv import writer
from io import BytesIO, StringIO
from typing import Optional

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table
from reportlab.platypus import TableStyle


WEEK_HEADERS = [
    "Dag",
    "Datum",
    "1e soort",
    "2e soort",
    "Dagtotaal",
    "Dode hennen",
    "Buitennest",
    "Water",
    "Voer",
    "Opmerkingen",
]


def weekly_calendar_xlsx(
    *,
    year: int,
    week: int,
    rows: list[dict[str, object]],
    totals: dict[str, float],
) -> BytesIO:
    """Build an Excel workbook for one weekly laying calendar."""
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = f"Week {week}"
    worksheet.append([f"Legkalender week {week} {year}"])
    worksheet.append([])
    worksheet.append(WEEK_HEADERS)

    for row in rows:
        worksheet.append(_week_export_row(row))

    worksheet.append(
        [
            "Week totaal",
            "",
            totals["first_quality_eggs"],
            totals["second_quality_eggs"],
            totals["total_eggs"],
            totals["dead_hens_count"],
            totals["outside_nest_egg_count"],
            round(totals["water_liters"], 2),
            round(totals["feed_kg"], 2),
            "",
        ]
    )

    worksheet["A1"].font = Font(bold=True, size=14)
    header_fill = PatternFill("solid", fgColor="D9EAF7")
    for cell in worksheet[3]:
        cell.font = Font(bold=True)
        cell.fill = header_fill
    for cell in worksheet[worksheet.max_row]:
        cell.font = Font(bold=True)

    for column_cells in worksheet.columns:
        max_length = max(len(str(cell.value or "")) for cell in column_cells)
        worksheet.column_dimensions[column_cells[0].column_letter].width = min(
            max_length + 2, 40
        )

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def weekly_calendar_pdf(
    *,
    year: int,
    week: int,
    rows: list[dict[str, object]],
    totals: dict[str, float],
) -> BytesIO:
    """Build a PDF for one weekly laying calendar."""
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        leftMargin=24,
        rightMargin=24,
        topMargin=24,
        bottomMargin=24,
    )
    styles = getSampleStyleSheet()
    data = [WEEK_HEADERS]
    data.extend(_week_export_row(row) for row in rows)
    data.append(
        [
            "Week totaal",
            "",
            totals["first_quality_eggs"],
            totals["second_quality_eggs"],
            totals["total_eggs"],
            totals["dead_hens_count"],
            totals["outside_nest_egg_count"],
            f"{totals['water_liters']:.2f}",
            f"{totals['feed_kg']:.2f}",
            "",
        ]
    )
    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightblue),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("ALIGN", (2, 1), (8, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
            ]
        )
    )
    document.build(
        [
            Paragraph(f"Legkalender week {week} {year}", styles["Title"]),
            Spacer(1, 12),
            table,
        ]
    )
    output.seek(0)
    return output


def records_csv(headers: list[str], rows: list[list[object]]) -> BytesIO:
    """Build a UTF-8 CSV file for raw records."""
    output = StringIO()
    csv_writer = writer(output)
    csv_writer.writerow(headers)
    csv_writer.writerows(rows)
    return BytesIO(output.getvalue().encode("utf-8-sig"))


def _week_export_row(row: dict[str, object]) -> list[object]:
    registration = row["registration"]
    if registration is None:
        return [
            row["weekday"],
            row["date"].isoformat(),
            "",
            "",
            "",
            row["dead_hens_count"],
            row["outside_nest_egg_count"],
            "",
            "",
            "",
        ]

    return [
        row["weekday"],
        row["date"].isoformat(),
        registration.first_quality_eggs,
        registration.second_quality_eggs,
        registration.total_eggs,
        row["dead_hens_count"],
        row["outside_nest_egg_count"],
        _format_optional_float(registration.water_liters),
        _format_optional_float(registration.feed_kg),
        registration.notes or "",
    ]


def _format_optional_float(value: Optional[float]) -> str:
    if value is None:
        return ""

    return f"{value:.2f}"
