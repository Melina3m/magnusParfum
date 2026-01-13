from datetime import date, datetime
from fpdf import FPDF
from io import BytesIO
import base64
import os

# =============== FUNCIONES BÁSICAS (Tal cual las tenías) ===============

def uid() -> str:
    """Genera ID único igual que tu función original"""
    return f"{datetime.utcnow().timestamp():.6f}".replace(".", "")

def cop(n: float) -> str:
    """Formatea moneda exactamente como lo hacías"""
    try:
        n = float(n)
    except Exception:
        return "-"
    return f"${int(round(n, 0)):,}".replace(",", ".")

def today_iso() -> str:
    return date.today().isoformat()

# =============== LÓGICA DE CRÉDITOS (Tu código exacto) ===============

def credit_saldo(c):
    """Calcula saldo de un crédito de cliente"""
    return float(c.get("total", 0)) - float(c.get("paid", 0))

def supplier_credit_saldo(c):
    """Calcula saldo de una deuda con proveedor"""
    return float(c.get("total", 0)) - float(c.get("paid", 0))

def apply_customer_payment(db, customer: str, amount: float, when: str, notes: str = "", method: str = ""):
    """
    TU LÓGICA EXACTA de aplicar abonos a clientes (FIFO).
    IMPORTANTE: En Supabase debes llamar update_record() para cada crédito modificado.
    """
    from database import insert_record, update_record
    
    if amount <= 0:
        return 0.0
    
    # Filtrar créditos abiertos del cliente
    open_credits = [c for c in db["credits"]
                    if (c.get("customer","").strip().lower() == customer.strip().lower()) 
                    and credit_saldo(c) > 0]
    open_credits.sort(key=lambda c: c.get("date",""))
    
    remaining = float(amount)
    for c in open_credits:
        if remaining <= 0:
            break
        s = credit_saldo(c)
        if s <= 0:
            continue
        pay = min(s, remaining)
        c["paid"] = float(c.get("paid", 0)) + pay
        
        # ACTUALIZAR EN SUPABASE
        update_record("credits", {"paid": c["paid"]}, c["id"])
        
        remaining -= pay
    
    # Registrar el pago
    payment_data = {
        "id": uid(), 
        "customer": customer, 
        "date": when, 
        "amount": float(amount),
        "notes": notes, 
        "method": method
    }
    insert_record("credit_payments", payment_data)
    db["credit_payments"].insert(0, payment_data)
    
    return float(amount) - remaining

def apply_supplier_payment(db, supplier: str, amount: float, when: str, notes: str = "", method: str = ""):
    """
    TU LÓGICA EXACTA de pagar a proveedores (FIFO).
    """
    from database import insert_record, update_record
    
    if amount <= 0:
        return 0.0
    
    open_credits = [c for c in db["supplier_credits"]
                    if (c.get("supplier","").strip().lower() == supplier.strip().lower()) 
                    and supplier_credit_saldo(c) > 0]
    open_credits.sort(key=lambda c: c.get("date",""))
    
    remaining = float(amount)
    for c in open_credits:
        if remaining <= 0:
            break
        s = supplier_credit_saldo(c)
        if s <= 0:
            continue
        pay = min(s, remaining)
        c["paid"] = float(c.get("paid", 0)) + pay
        
        # ACTUALIZAR EN SUPABASE
        update_record("supplier_credits", {"paid": c["paid"]}, c["id"])
        
        remaining -= pay
    
    # Registrar el pago
    payment_data = {
        "id": uid(), 
        "supplier": supplier, 
        "date": when, 
        "amount": float(amount),
        "notes": notes, 
        "method": method
    }
    insert_record("supplier_payments", payment_data)
    db["supplier_payments"].insert(0, payment_data)
    
    return float(amount) - remaining

# =============== LIBRO DE CAJA/BANCO (Tu código exacto) ===============

def _movements_ledger(db):
    """
    Construye el libro de movimientos TAL CUAL lo tenías.
    """
    movs = []

    # Ventas
    for s in db.get("sales", []):
        amt = float(s.get("quantity", 0) or 0) * float(s.get("unit_price", 0) or 0)
        meth = (s.get("payment") or "").strip().title()
        if meth in ("Efectivo", "Transferencia", "Tarjeta"):
            movs.append({
                "fecha": s.get("date", ""),
                "tipo": "Entrada",
                "medio": "Caja" if meth == "Efectivo" else "Banco",
                "concepto": f"Venta — {meth}",
                "detalle": s.get("customer", "") or "",
                "monto": amt
            })

    # Abonos clientes (fiados)
    for p in db.get("credit_payments", []):
        amt = float(p.get("amount", 0) or 0)
        meth = (p.get("method") or "").strip().title()
        medio = "Caja" if meth == "Efectivo" else "Banco"
        movs.append({
            "fecha": p.get("date", ""),
            "tipo": "Entrada",
            "medio": medio,
            "concepto": f"Abono cliente — {meth}",
            "detalle": p.get("customer", ""),
            "monto": amt
        })

    # Compras al contado
    for pu in db.get("purchases", []):
        meth = (pu.get("cash_method") or "").strip().title()
        if meth:
            q = int(pu.get("quantity", 1) or 1)
            uc = float(pu.get("unit_cost", 0) or 0)
            amt = q * uc
            medio = "Caja" if meth == "Efectivo" else "Banco"
            concepto = "Compra inventario" if pu.get("item_id") else "Gasto operativo"
            movs.append({
                "fecha": pu.get("date", ""),
                "tipo": "Salida",
                "medio": medio,
                "concepto": f"{concepto} — {meth}",
                "detalle": pu.get("supplier", "") or "",
                "monto": amt
            })

    # Pagos a proveedores
    for sp in db.get("supplier_payments", []):
        amt = float(sp.get("amount", 0) or 0)
        meth = (sp.get("method") or "").strip().title()
        medio = "Caja" if meth == "Efectivo" else "Banco"
        movs.append({
            "fecha": sp.get("date", ""),
            "tipo": "Salida",
            "medio": medio,
            "concepto": f"Pago a proveedor — {meth}",
            "detalle": sp.get("supplier", "") or "",
            "monto": amt
        })

    # Ordenar por fecha
    def _key(m):
        try:
            return m["fecha"]
        except Exception:
            return ""
    movs.sort(key=_key)
    return movs

def cash_bank_balances(db):
    """
    Calcula saldos de Caja y Banco TAL CUAL tu código original.
    """
    caja = 0.0
    banco = 0.0
    for m in _movements_ledger(db):
        sign = 1 if m["tipo"] == "Entrada" else -1
        if m["medio"] == "Caja":
            caja += sign * float(m["monto"] or 0)
        else:
            banco += sign * float(m["monto"] or 0)
    return caja, banco

# =============== GENERACIÓN DE PDFs (Tu código exacto) ===============

def _get_logo_temp_path(db) -> str | None:
    """Obtiene el logo desde settings (si existe)"""
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
    """
    TU FUNCIÓN EXACTA de generar recibos PDF con breakdown.
    """
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

    out = BytesIO()
    pdf.output(out)
    try:
        if logo_path and os.path.exists(logo_path):
            os.remove(logo_path)
    except Exception:
        pass
    return out.getvalue()