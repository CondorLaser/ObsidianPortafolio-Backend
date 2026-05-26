"""Genera 2 PDFs sintéticos con la misma estructura que los certificados
Fintual reales, usando data EXACTA extraída de los PDFs del usuario.

Salida:
    /tmp/cert_stocks.pdf  (stocks/ETFs + dividendos)
    /tmp/cert_funds.pdf   (fondos mutuos)

Estos PDFs son procesables por pdfplumber con processing_pdf.extract_*,
permitiendo testear end-to-end la cadena pdfplumber → repo → DB sin
necesitar los PDFs originales del usuario en disco.

Uso:
    ./venv/bin/python -m scripts.generate_test_pdfs
"""
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)

from scripts.test_real_fintual_data import PURCHASE_SALES, DIVIDENDS, MUTUAL_FUNDS


OUT_STOCKS = Path("/tmp/cert_stocks.pdf")
OUT_FUNDS = Path("/tmp/cert_funds.pdf")


def _table_style() -> TableStyle:
    """Bordes finos + header gris — clave para que pdfplumber detecte la tabla."""
    return TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
    ])


def _fmt_us(amount: float) -> str:
    """Formato 'US $\\nX,XX' con coma decimal — matcheable por us_a_num."""
    if amount == 0:
        return ""
    s = f"{amount:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")
    return f"US $\n{s}"


def _fmt_qty(q: float) -> str:
    if q == 0:
        return ""
    s = f"{q:.9f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def _fmt_pesos(amount: float) -> str:
    """'$1.000.000' con punto como separador de miles."""
    if amount == 0:
        return "0"
    s = f"{amount:,.0f}".replace(",", ".")
    return f"${s}"


def _fmt_cuotas(q: float) -> str:
    if q == 0:
        return "0"
    s = f"{q:.4f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def build_stocks_etfs_pdf():
    """Estructura: 2 tablas (compraventa + dividendos) con headers que matchean
    lo que detecta extract_stocks_etf_1."""
    doc = SimpleDocTemplate(
        str(OUT_STOCKS), pagesize=landscape(A4),
        leftMargin=1*cm, rightMargin=1*cm,
        topMargin=1*cm, bottomMargin=1*cm,
    )
    styles = getSampleStyleSheet()
    elems = [
        Paragraph("CERTIFICADO DE TRANSACCIONES EN ACCIONES Y ETFs (TEST SYNTHETIC)", styles["Title"]),
        Spacer(1, 0.5*cm),
        Paragraph("Compra y venta de activos", styles["Heading2"]),
        Spacer(1, 0.3*cm),
    ]

    # Tabla compraventa: 8 columnas, header matcheando lo que cleanup espera
    compraventa_data = [
        ["Fecha", "Nombre Activo", "Símbolo\nActivo", "Categoría\nActivo",
         "Aporte\nde\ndólares", "Acciones\ncompradas",
         "Rescate\nde\ndólares", "Acciones\nvendidas"],
    ]
    for row in PURCHASE_SALES:
        fecha, nombre, simbolo, categoria, aporte, acc_compradas, rescate, acc_vendidas = row
        compraventa_data.append([
            fecha, nombre, simbolo, categoria,
            _fmt_us(aporte), _fmt_qty(acc_compradas),
            _fmt_us(rescate), _fmt_qty(acc_vendidas),
        ])

    col_widths = [1.8*cm, 5*cm, 1.8*cm, 2*cm, 1.8*cm, 2.5*cm, 1.8*cm, 2.5*cm]
    tbl1 = Table(compraventa_data, colWidths=col_widths, repeatRows=1)
    tbl1.setStyle(_table_style())
    elems.append(tbl1)
    elems.append(Spacer(1, 1*cm))

    elems.append(Paragraph("Dividendos recibidos", styles["Heading2"]))
    elems.append(Spacer(1, 0.3*cm))

    # Tabla dividendos: 7 columnas
    # Header debe tener col[6] = "Monto\nneto" para que el detector funcione
    div_data = [
        ["Fecha", "Nombre Activo", "Símbolo\nActivo", "Categoría\nActivo",
         "Monto\nbruto", "Monto\nimpuestos", "Monto\nneto"],
    ]
    for row in DIVIDENDS:
        fecha, nombre, simbolo, categoria, bruto, impuestos, neto = row
        div_data.append([
            fecha, nombre, simbolo, categoria,
            _fmt_us(bruto), _fmt_us(impuestos), _fmt_us(neto),
        ])

    div_col_widths = [1.8*cm, 6*cm, 2*cm, 2.2*cm, 1.8*cm, 2*cm, 1.8*cm]
    tbl2 = Table(div_data, colWidths=div_col_widths, repeatRows=1)
    tbl2.setStyle(_table_style())
    elems.append(tbl2)

    doc.build(elems)
    print(f"✅ {OUT_STOCKS} ({OUT_STOCKS.stat().st_size:,} bytes) — "
          f"{len(PURCHASE_SALES)} compraventas + {len(DIVIDENDS)} dividendos")


def build_funds_pdf():
    """Estructura: 1 tabla de 12 columnas matcheando lo que detecta extract_mutual_funds."""
    doc = SimpleDocTemplate(
        str(OUT_FUNDS), pagesize=landscape(A4),
        leftMargin=0.5*cm, rightMargin=0.5*cm,
        topMargin=1*cm, bottomMargin=1*cm,
    )
    styles = getSampleStyleSheet()
    elems = [
        Paragraph("CERTIFICADO DE TRANSACCIONES (FONDOS MUTUOS) — TEST SYNTHETIC", styles["Title"]),
        Spacer(1, 0.3*cm),
    ]

    data = [
        ["Fecha", "Nombre Inversión", "Nombre Fondo", "Serie\nFondo",
         "Aporte\nCuotas", "Rescate\nCuotas", "Valor\nCuota",
         "Saldo\nCuotas\nFinal\nDia",
         "Aporte\nPesos\nChilenos", "Rescate\nPesos\nChilenos",
         "Medio", "Saldo\nPesos\nChilenos\nFinal Dia"],
    ]
    for row in MUTUAL_FUNDS:
        fecha, inv, fondo, serie, ap_c, rs_c, ap_p, rs_p = row
        data.append([
            fecha, inv, fondo, serie,
            _fmt_cuotas(ap_c), _fmt_cuotas(rs_c),
            "0,0000",  # valor_cuota (no se usa)
            "0,0000",  # saldo_cuotas (no se usa)
            _fmt_pesos(ap_p), _fmt_pesos(rs_p),
            "Transferencia\nelectronica",
            "$0",  # saldo final (no se usa)
        ])

    col_widths = [1.5*cm, 2.5*cm, 2.5*cm, 1*cm, 1.4*cm, 1.4*cm, 1.2*cm,
                  1.4*cm, 1.7*cm, 1.7*cm, 1.8*cm, 1.7*cm]
    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(_table_style())
    elems.append(tbl)

    doc.build(elems)
    print(f"✅ {OUT_FUNDS} ({OUT_FUNDS.stat().st_size:,} bytes) — "
          f"{len(MUTUAL_FUNDS)} movimientos")


if __name__ == "__main__":
    build_stocks_etfs_pdf()
    build_funds_pdf()
