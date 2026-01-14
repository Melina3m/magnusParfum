import streamlit as st
import pandas as pd
from datetime import date
from utils import cop

# =============== LÓGICA INTERNA ===============

def _movements_ledger(db):
    """Construye el libro de movimientos de caja/banco"""
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

    # Abonos clientes
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

    def _key(m):
        try: return m["fecha"]
        except: return ""
            
    movs.sort(key=_key, reverse=True) # Ordenados por fecha (más recientes primero)
    return movs

def cash_bank_balances(db):
    """Calcula saldos netos de Caja y Banco"""
    caja = 0.0
    banco = 0.0
    for m in _movements_ledger(db):
        sign = 1 if m["tipo"] == "Entrada" else -1
        if m["medio"] == "Caja":
            caja += sign * float(m["monto"] or 0)
        else:
            banco += sign * float(m["monto"] or 0)
    return caja, banco

# =============== VISUALIZACIÓN (STREAMLIT) ===============

def render_cash_and_bank(db):
    st.subheader("🏦 Caja y Bancos")

    # 1. Mostrar métricas superiores
    saldo_caja, saldo_banco = cash_bank_balances(db)
    c1, c2 = st.columns(2)
    c1.metric("Efectivo en Caja", cop(saldo_caja))
    c2.metric("Saldo en Banco", cop(saldo_banco))

    st.markdown("---")
    st.markdown("### Libro Diario de Movimientos")

    # 2. Generar el libro y mostrarlo con formato de miles
    ledger = _movements_ledger(db)

    if ledger:
        df_ledger = pd.DataFrame(ledger)
        
        # --- AQUÍ SE ACTIVAN LOS MILES CON PUNTOS ---
        st.dataframe(
            df_ledger.style.format({
                "monto": "{:,.0f}"
            }).replace(",", "."), 
            use_container_width=True
        )
    else:
        st.info("No hay movimientos registrados.")