import streamlit as st
from database import load_full_db
from utils import cop, cash_bank_balances, credit_saldo, supplier_credit_saldo
from tabs import (
    render_inventory, render_purchases, render_sales, render_fiados,
    render_investor, render_reports, render_suppliers, render_cash_bank, render_settings
)

# ==================== CONFIGURACIÓN ====================
st.set_page_config(page_title="Magnus Parfum — Gestión", page_icon="🛍️", layout="wide")

st.title(" Magnus Parfum ")
st.caption("Inventario • Ventas • Fiados • Proveedores • Inversionista — Datos en Supabase")

#  CARGAR DB SIEMPRE
db = load_full_db()

# Migración: asegurar campos nuevos
for p in db.get("inventory", []):
    if "inv" not in p:
        p["inv"] = True
for s in db.get("sales", []):
    if "inv" not in s:
        s["inv"] = None

# ==================== MÉTRICAS SUPERIORES ====================
caja, banco = cash_bank_balances(db)
stock_cost = sum((p.get("cost", 0) or 0) * (p.get("stock", 0) or 0) for p in db["inventory"])
total_cobrar = sum(credit_saldo(c) for c in db["credits"])
total_proveedores = sum(supplier_credit_saldo(c) for c in db["supplier_credits"])

# Layout de 4 columnas para balance total
col1, col2, col3, col4 = st.columns(4)

col1.metric("Stock (Costo)", cop(stock_cost))
col2.metric("Caja (Efectivo)", cop(caja))
col3.metric("Por Cobrar (Clientes)", cop(total_cobrar))
col4.metric("Por Pagar (Proveedor)", cop(total_proveedores))

# ==================== PESTAÑAS ====================
tabs = st.tabs([
    " Inventario", 
    " Compras", 
    " Ventas", 
    " Fiados", 
    " Inversionista",
    " Reportes", 
    " Proveedores", 
    " Caja y Bancos",
    " Ajustes"
])

with tabs[0]:
    render_inventory(db)
with tabs[1]:
    render_purchases(db)
with tabs[2]:
    render_sales(db)
with tabs[3]:
    render_fiados(db)
with tabs[4]:
    render_investor(db)
with tabs[5]:
    render_reports(db)
with tabs[6]:
    render_suppliers(db)
with tabs[7]:
    render_cash_bank(db)
with tabs[8]:
    render_settings(db)