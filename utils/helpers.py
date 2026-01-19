from datetime import date, datetime

# =============== FUNCIONES BÁSICAS ===============

def uid() -> str:
    """Genera ID único basado en timestamp"""
    return f"{datetime.utcnow().timestamp():.6f}".replace(".", "")

def cop(n: float) -> str:
    """Formatea números como moneda COP con separador de miles (punto)"""
    try:
        n = float(n)
    except Exception:
        return "$0"
    return f"${int(round(n, 0)):,}".replace(",", ".")

def today_iso() -> str:
    """Retorna la fecha actual en formato ISO"""
    return date.today().isoformat()

# =============== LÓGICA DE CRÉDITOS ===============

def credit_saldo(c):
    """Calcula el saldo pendiente de un crédito de cliente"""
    return float(c.get("total", 0)) - float(c.get("paid", 0))

def supplier_credit_saldo(c):
    """Calcula el saldo pendiente de una deuda con proveedor"""
    return float(c.get("total", 0)) - float(c.get("paid", 0))

# =============== GESTIÓN DE PAGOS (CLIENTES) ===============

def apply_customer_payment(db, customer: str, amount: float, when: str, notes: str = "", method: str = "",
                           balance_before: float = 0.0, balance_after: float = 0.0, breakdown: list = None):
    """
    Aplica un pago de cliente a sus créditos pendientes (método FIFO)
    
    Args:
        db: Base de datos
        customer: Nombre del cliente
        amount: Monto del pago
        when: Fecha del pago (ISO format)
        notes: Notas adicionales
        method: Método de pago (Efectivo, Transferencia, Tarjeta)
        balance_before: Saldo antes del pago (opcional, para recibo)
        balance_after: Saldo después del pago (opcional, para recibo)
        breakdown: Desglose de aplicación (opcional, para recibo)
    
    Returns:
        float: Monto aplicado exitosamente
    """
    from database import insert_record, update_record
    
    if amount <= 0:
        return 0.0
    
    # Obtener créditos pendientes del cliente
    open_credits = [c for c in db["credits"]
                    if (c.get("customer","").strip().lower() == customer.strip().lower()) 
                    and credit_saldo(c) > 0]
    open_credits.sort(key=lambda c: c.get("date",""))
    
    # Aplicar pago (FIFO)
    remaining = float(amount)
    for c in open_credits:
        if remaining <= 0:
            break
        s = credit_saldo(c)
        if s <= 0:
            continue
        pay = min(s, remaining)
        c["paid"] = float(c.get("paid", 0)) + pay
        update_record("credits", {"paid": c["paid"]}, c["id"])
        remaining -= pay
    
    # Registrar el pago en Supabase
    payment_data = {
        "id": uid(), 
        "customer": customer, 
        "date": when, 
        "amount": float(amount),
        "notes": notes, 
        "method": method
    }
    insert_record("credit_payments", payment_data)
    
    return float(amount) - remaining

# =============== GESTIÓN DE PAGOS (PROVEEDORES) ===============

def apply_supplier_payment(db, supplier: str, amount: float, when: str, notes: str = "", method: str = ""):
    """
    Aplica un pago a proveedor a sus créditos pendientes (método FIFO)
    
    Args:
        db: Base de datos
        supplier: Nombre del proveedor
        amount: Monto del pago
        when: Fecha del pago (ISO format)
        notes: Notas adicionales
        method: Método de pago (Efectivo, Transferencia, Tarjeta)
    
    Returns:
        float: Monto aplicado exitosamente
    """
    from database import insert_record, update_record
    
    if amount <= 0:
        return 0.0
    
    # Obtener créditos pendientes con el proveedor
    open_credits = [c for c in db.get("supplier_credits", [])
                    if (c.get("supplier","").strip().lower() == supplier.strip().lower()) 
                    and supplier_credit_saldo(c) > 0]
    open_credits.sort(key=lambda c: c.get("date",""))
    
    # Aplicar pago (FIFO)
    remaining = float(amount)
    for c in open_credits:
        if remaining <= 0:
            break
        s = supplier_credit_saldo(c)
        if s <= 0:
            continue
        pay = min(s, remaining)
        c["paid"] = float(c.get("paid", 0)) + pay
        update_record("supplier_credits", {"paid": c["paid"]}, c["id"])
        remaining -= pay
    
    # Registrar el pago en Supabase
    payment_data = {
        "id": uid(), 
        "supplier": supplier, 
        "date": when, 
        "amount": float(amount),
        "notes": notes, 
        "method": method
    }
    insert_record("supplier_payments", payment_data)
    
    return float(amount) - remaining

# =============== GENERACIÓN DE RECIBOS PDF ===============

def build_receipt_pdf(db, who_type: str, who_name: str, receipt_id: str, date_str: str,
                     amount: float, balance_before: float, balance_after: float,
                     notes: str = "", breakdown: list = None):
    """
    Genera un recibo PDF para pagos de clientes o proveedores
    
    Args:
        db: Base de datos
        who_type: "CLIENTE" o "PROVEEDOR"
        who_name: Nombre del cliente o proveedor
        receipt_id: ID del recibo
        date_str: Fecha del pago
        amount: Monto del pago
        balance_before: Saldo antes del pago
        balance_after: Saldo después del pago
        notes: Notas adicionales
        breakdown: Desglose de aplicación del pago
    
    Returns:
        bytes: PDF generado en formato bytes
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from io import BytesIO
    import base64
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    # Estilo personalizado para el título
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a1a2e'),
        alignment=TA_CENTER,
        spaceAfter=30
    )
    
    # Logo (si existe)
    logo_b64 = db["settings"].get("logo_b64")
    if logo_b64:
        try:
            logo_data = base64.b64decode(logo_b64)
            logo_buffer = BytesIO(logo_data)
            img = Image(logo_buffer, width=1.5*inch, height=1.5*inch)
            img.hAlign = 'CENTER'
            elements.append(img)
            elements.append(Spacer(1, 0.3*inch))
        except Exception:
            pass
    
    # Título
    elements.append(Paragraph("COMPROBANTE DE PAGO", title_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Información del recibo
    info_data = [
        ["Recibo N°:", receipt_id],
        ["Fecha:", date_str],
        [f"{who_type}:", who_name],
        ["Monto Pagado:", cop(amount)],
        ["Saldo Anterior:", cop(balance_before)],
        ["Saldo Actual:", cop(balance_after)]
    ]
    
    if notes:
        info_data.append(["Notas:", notes])
    
    info_table = Table(info_data, colWidths=[2*inch, 4*inch])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1a1a2e')),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
    ]))
    
    elements.append(info_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Desglose (si existe)
    if breakdown and len(breakdown) > 0:
        elements.append(Paragraph("<b>Desglose de Aplicación:</b>", styles['Heading3']))
        elements.append(Spacer(1, 0.1*inch))
        
        breakdown_data = [["Fecha Crédito", "Monto Aplicado", "Saldo Restante"]]
        for item in breakdown:
            breakdown_data.append([
                item.get("date", ""),
                cop(item.get("applied", 0)),
                cop(item.get("remaining", 0))
            ])
        
        breakdown_table = Table(breakdown_data, colWidths=[2*inch, 2*inch, 2*inch])
        breakdown_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d9e8ff')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        
        elements.append(breakdown_table)
    
    # Pie de página
    elements.append(Spacer(1, 0.5*inch))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=TA_CENTER
    )
    elements.append(Paragraph("Magnus Parfum - Sistema de Gestión", footer_style))
    elements.append(Paragraph(f"Generado el {today_iso()}", footer_style))
    
    # Construir PDF
    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes