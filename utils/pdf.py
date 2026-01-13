from fpdf import FPDF
import base64
import os
from .helpers import cop

def _get_logo_temp_path(db) -> str | None:
    """Obtiene el logo desde settings"""
    try:
        b64 = db["settings"].get("logo_b64")
        if not b64:
            return None
        raw = base64.b64decode(b64)
        temp_path = "magnus_logo_tmp.png"
        with open(temp_path, "wb") as f:
            f.write(raw)
        return temp_path
    except Exception:
        return None

def _pdf_header(pdf: FPDF, title: str, logo_path: str | None):
    if logo_path:
        try:
            pdf.image(logo_path, x=10, y=8, w=25)
        except Exception:
            pass
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "MAGNUS PARFUM", ln=1, align="R")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 6, title, ln=1, align="R")
    pdf.ln(6)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

def _pdf_kv(pdf: FPDF, label: str, value: str):
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(50, 6, label + ":", border=0)
    pdf.set_font("Helvetica", "", 11)
    if not value:
        value = "-"
    pdf.cell(0, 6, value, border=0, ln=1)

def build_receipt_pdf(db, *, who_type: str, who_name: str, receipt_id: str,
                      date_str: str, amount: float,
                      balance_before: float, balance_after: float,
                      notes: str = "", breakdown: list[dict] | None = None) -> bytes:
    """Genera recibo PDF con breakdown"""
    logo_path = _get_logo_temp_path(db)
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    _pdf_header(pdf, f"RECIBO DE ABONO - {who_type}", logo_path)

    _pdf_kv(pdf, "Recibo", receipt_id)
    _pdf_kv(pdf, "Fecha", date_str)
    _pdf_kv(pdf, who_type.title(), who_name or ("Cliente" if who_type=="CLIENTE" else "Proveedor"))
    _pdf_kv(pdf, "Monto abonado", cop(amount))
    _pdf_kv(pdf, "Saldo ANTES", cop(balance_before))
    _pdf_kv(pdf, "Saldo DESPUÉS", cop(balance_after))
    if notes:
        _pdf_kv(pdf, "Notas", notes)

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Desglose de aplicación", ln=1)
    pdf.set_font("Helvetica", "", 10)
    if breakdown:
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(50, 7, "ID deuda", border=1, align="C", fill=True)
        pdf.cell(40, 7, "Fecha", border=1, align="C", fill=True)
        pdf.cell(40, 7, "Aplicado", border=1, align="C", fill=True)
        pdf.cell(40, 7, "Saldo restante", border=1, align="C", fill=True)
        pdf.ln(7)
        for row in breakdown:
            pdf.cell(50, 7, str(row.get("id","")), border=1)
            pdf.cell(40, 7, str(row.get("date",""))[:10], border=1)
            pdf.cell(40, 7, cop(row.get("applied", 0)), border=1, align="R")
            pdf.cell(40, 7, cop(row.get("remaining", 0)), border=1, align="R")
            pdf.ln(7)
    else:
        pdf.multi_cell(0, 6, "El abono se aplicó a deudas abiertas según antigüedad (FIFO).")

    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(0, 5, "Este recibo ha sido generado automáticamente por el sistema de gestión de Magnus Parfum.")

    # Generar PDF en memoria
    pdf_bytes = pdf.output(dest='S').encode('latin-1')
    
    # Limpiar archivo temporal del logo
    try:
        if logo_path and os.path.exists(logo_path):
            os.remove(logo_path)
    except Exception:
        pass
    
    return pdf_bytes