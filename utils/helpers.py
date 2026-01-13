from datetime import date, datetime

# =============== FUNCIONES BÁSICAS ===============

def uid() -> str:
    """Genera ID único"""
    return f"{datetime.utcnow().timestamp():.6f}".replace(".", "")

def cop(n: float) -> str:
    """Formatea moneda COP"""
    try:
        n = float(n)
    except Exception:
        return "-"
    return f"${int(round(n, 0)):,}".replace(",", ".")

def today_iso() -> str:
    return date.today().isoformat()

# =============== LÓGICA DE CRÉDITOS ===============

def credit_saldo(c):
    """Calcula saldo de un crédito de cliente"""
    return float(c.get("total", 0)) - float(c.get("paid", 0))

def supplier_credit_saldo(c):
    """Calcula saldo de una deuda con proveedor"""
    return float(c.get("total", 0)) - float(c.get("paid", 0))

def apply_customer_payment(db, customer: str, amount: float, when: str, notes: str = "", method: str = ""):
    """Aplica abonos a clientes (FIFO)"""
    from database import insert_record, update_record
    
    if amount <= 0:
        return 0.0
    
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
        update_record("credits", {"paid": c["paid"]}, c["id"])
        remaining -= pay
    
    payment_data = {
        "id": uid(), "customer": customer, "date": when, "amount": float(amount),
        "notes": notes, "method": method
    }
    insert_record("credit_payments", payment_data)
    db["credit_payments"].insert(0, payment_data)
    
    return float(amount) - remaining

def apply_supplier_payment(db, supplier: str, amount: float, when: str, notes: str = "", method: str = ""):
    """Aplica pagos a proveedores (FIFO)"""
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
        update_record("supplier_credits", {"paid": c["paid"]}, c["id"])
        remaining -= pay
    
    payment_data = {
        "id": uid(), "supplier": supplier, "date": when, "amount": float(amount),
        "notes": notes, "method": method
    }
    insert_record("supplier_payments", payment_data)
    db["supplier_payments"].insert(0, payment_data)
    
    return float(amount) - remaining