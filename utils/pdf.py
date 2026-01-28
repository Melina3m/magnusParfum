from fpdf import FPDF
import base64
import os
from utils import cop

def _get_logo_temp_path(db):
    """Obtiene el logo desde settings y lo guarda temporalmente"""
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

def _pdf_header(pdf: FPDF, title: str, logo_path):
    """Genera el encabezado del PDF con logo y título"""
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
    """Genera una fila clave-valor en el PDF"""
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(50, 6, label + ":", border=0)
    pdf.set_font("Helvetica", "", 11)
    if not value:
        value = "-"
    pdf.cell(0, 6, value, border=0, ln=1)

def build_receipt_pdf(db, *, who_type: str, who_name: str, receipt_id: str,
                      date_str: str, amount: float,
                      balance_before: float, balance_after: float,
                      notes: str = "", breakdown: list = None):
    """
    Genera un recibo PDF con breakdown del abono actual + historial
    
    Args:
        db: Base de datos
        who_type: "CLIENTE" o "PROVEEDOR"
        who_name: Nombre del cliente o proveedor
        receipt_id: ID del recibo
        date_str: Fecha del pago (formato ISO)
        amount: Monto del abono
        balance_before: Saldo antes del abono
        balance_after: Saldo después del abono
        notes: Notas adicionales
        breakdown: Lista de dict con aplicación del abono
    
    Returns:
        bytes: PDF generado
    """
    logo_path = _get_logo_temp_path(db)
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Encabezado
    _pdf_header(pdf, f"RECIBO DE ABONO - {who_type}", logo_path)

    # Información principal del recibo
    rid_display = receipt_id[-8:] if len(receipt_id) > 10 else receipt_id
    _pdf_kv(pdf, "Recibo", rid_display)
    _pdf_kv(pdf, "Fecha", date_str)
    _pdf_kv(pdf, who_type.title(), who_name or ("Cliente" if who_type == "CLIENTE" else "Proveedor"))
    _pdf_kv(pdf, "Monto abonado", cop(amount))
    _pdf_kv(pdf, "Saldo ANTES", cop(balance_before))
    _pdf_kv(pdf, "Saldo DESPUÉS", cop(balance_after))
    
    if notes:
        _pdf_kv(pdf, "Notas", notes)

    # Desglose de aplicación CON HISTORIAL
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Desglose de aplicación", ln=1)
    pdf.set_font("Helvetica", "", 10)
    
    if breakdown and len(breakdown) > 0:
        # Encabezados de la tabla
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(50, 7, "ID Ref.", border=1, align="C", fill=True)
        pdf.cell(40, 7, "Fecha", border=1, align="C", fill=True)
        pdf.cell(40, 7, "Monto", border=1, align="C", fill=True)
        pdf.cell(40, 7, "Saldo después", border=1, align="C", fill=True)
        pdf.ln(7)
        
        # PRIMERO: El abono de HOY (destacado)
        for row in breakdown:
            full_id = str(row.get("id", ""))
            short_id = full_id[-8:] if len(full_id) > 8 else full_id
            
            # Resaltar el abono de hoy
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(50, 7, short_id, border=1)
            pdf.cell(40, 7, date_str[:10], border=1, align="C")
            pdf.cell(40, 7, cop(row.get("applied", 0)), border=1, align="R")
            pdf.cell(40, 7, cop(balance_after), border=1, align="R")
            pdf.ln(7)
        
        # SEGUNDO: Historial de abonos anteriores
        payment_history = []
        current_receipt_id = receipt_id[-8:] if len(receipt_id) > 10 else receipt_id
        
        if who_type == "CLIENTE":
            for payment in db.get("credit_payments", []):
                if payment.get("customer", "").strip().lower() == who_name.strip().lower():
                    payment_id = payment.get("id", "")
                    payment_id_short = payment_id[-8:] if len(payment_id) > 8 else payment_id
                    # Excluir el recibo actual
                    if payment_id_short != current_receipt_id:
                        payment_history.append(payment)
        else:  # PROVEEDOR
            for payment in db.get("supplier_payments", []):
                if payment.get("supplier", "").strip().lower() == who_name.strip().lower():
                    payment_id = payment.get("id", "")
                    payment_id_short = payment_id[-8:] if len(payment_id) > 8 else payment_id
                    if payment_id_short != current_receipt_id:
                        payment_history.append(payment)
        
        # Ordenar del más reciente al más antiguo
        payment_history.sort(key=lambda x: x.get("date", ""), reverse=True)
        
        # Calcular saldo acumulado hacia atrás
        running_balance = balance_after
        
        # Mostrar hasta 9 abonos anteriores
        if payment_history:
            for payment in payment_history[:9]:
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(100, 100, 100)
                
                # Ir sumando los montos hacia atrás en el tiempo
                running_balance += float(payment.get("amount", 0))
                
                ref_id = payment.get("id", "")[-8:]
                pdf.cell(50, 7, ref_id, border=1)
                pdf.cell(40, 7, payment.get("date", "")[:10], border=1, align="C")
                pdf.cell(40, 7, cop(payment.get("amount", 0)), border=1, align="R")
                pdf.cell(40, 7, cop(running_balance), border=1, align="R")
                pdf.ln(7)
                
                pdf.set_text_color(0, 0, 0)
            
            # Nota si hay más de 10 abonos
            total_abonos = len(payment_history) + len(breakdown)
            if total_abonos > 10:
                pdf.ln(2)
                pdf.set_font("Helvetica", "I", 8)
                pdf.set_text_color(100, 100, 100)
                pdf.cell(0, 5, f"(Mostrando 10 de {total_abonos} abonos totales)", ln=1)
                pdf.set_text_color(0, 0, 0)
    else:
        pdf.multi_cell(0, 6, "El abono se aplicó a deudas abiertas según antigüedad (FIFO).")

    # Footer
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