"""
reportes.py
-----------
Genera un reporte PDF con las estadísticas ambientales del hospital,
agrupadas por turno (6am-2pm, 2pm-10pm, 10pm-6am), a partir de los
datos guardados en SQLite.

Uso:
    python reportes.py                  # reporte del día de hoy
    python reportes.py 2026-07-19       # reporte de una fecha específica
"""

import sys
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)

import database as db

AZUL_OSCURO = colors.HexColor("#0d1b3e")
AMARILLO = colors.HexColor("#f2b705")


def generar_reporte_pdf(fecha_iso: str, ruta_salida: str = None):
    if ruta_salida is None:
        ruta_salida = f"reporte_{fecha_iso}.pdf"

    resumen = db.estadisticas_por_turno(fecha_iso)

    doc = SimpleDocTemplate(ruta_salida, pagesize=letter,
                             topMargin=2 * cm, bottomMargin=2 * cm)
    estilos = getSampleStyleSheet()

    titulo_estilo = ParagraphStyle(
        "Titulo", parent=estilos["Title"], textColor=AZUL_OSCURO, fontSize=20
    )
    subtitulo_estilo = ParagraphStyle(
        "Subtitulo", parent=estilos["Heading2"], textColor=AZUL_OSCURO
    )
    turno_estilo = ParagraphStyle(
        "Turno", parent=estilos["Heading3"], textColor=colors.white,
        backColor=AZUL_OSCURO, spaceBefore=10, spaceAfter=6,
        leftIndent=6, borderPadding=6
    )

    elementos = []
    elementos.append(Paragraph("Monitoreo Ambiental Hospitalario", titulo_estilo))
    elementos.append(Paragraph(f"Reporte de estadísticas — {fecha_iso}", subtitulo_estilo))
    elementos.append(Spacer(1, 0.5 * cm))

    total_alertas = sum(
        (r["alertas"] if r else 0) for r in resumen.values()
    )
    elementos.append(Paragraph(
        f"Total de alertas registradas en el día: <b>{total_alertas}</b>",
        estilos["Normal"]
    ))
    elementos.append(Spacer(1, 0.4 * cm))

    for nombre_turno, datos in resumen.items():
        elementos.append(Paragraph(nombre_turno, turno_estilo))

        if datos is None:
            elementos.append(Paragraph("Sin lecturas registradas en este turno.", estilos["Normal"]))
            elementos.append(Spacer(1, 0.3 * cm))
            continue

        tabla_datos = [
            ["Variable", "Mínimo", "Máximo", "Promedio"],
            ["Temperatura (°C)", datos["temp_min"], datos["temp_max"], datos["temp_prom"]],
            ["Humedad (%)", datos["humedad_min"], datos["humedad_max"], datos["humedad_prom"]],
            ["CO2 / Aire (ppm)", datos["co2_min"], datos["co2_max"], datos["co2_prom"]],
        ]
        tabla = Table(tabla_datos, colWidths=[5 * cm, 3 * cm, 3 * cm, 3 * cm])
        tabla.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), AMARILLO),
            ("TEXTCOLOR", (0, 0), (-1, 0), AZUL_OSCURO),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.whitesmoke]),
        ]))
        elementos.append(tabla)

        elementos.append(Spacer(1, 0.2 * cm))
        elementos.append(Paragraph(
            f"Lecturas registradas: {datos['n_lecturas']} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"Alertas (buzzer activo): <b>{datos['alertas']}</b>",
            estilos["Normal"]
        ))
        elementos.append(Spacer(1, 0.4 * cm))

    elementos.append(Spacer(1, 0.6 * cm))
    elementos.append(Paragraph(
        "Instituto Tecnológico de Tijuana — Sistema de Monitoreo Ambiental Hospitalario",
        estilos["Italic"]
    ))

    doc.build(elementos)
    print(f"Reporte generado: {ruta_salida}")
    return ruta_salida


if __name__ == "__main__":
    fecha = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    generar_reporte_pdf(fecha)
