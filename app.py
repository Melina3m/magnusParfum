import streamlit as st
from database import load_full_db
from utils import cop, cash_bank_balances, credit_saldo
from tabs import (
    render_inventory, render_purchases, render_sales, render_fiados,
    render_investor, render_reports, render_suppliers, render_cash_bank, render_settings
)

# Cargar CSS personalizado
def local_css(file_name):
    try:
        with open(file_name, encoding='utf-8') as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except Exception as e:
        st.warning(f"No se pudo cargar el archivo CSS: {e}")

local_css("style.css")

# ==================== CONFIGURACIÓN ====================
st.set_page_config(
    page_title="Magnus Parfum", 
    page_icon="", 
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': "Magnus Parfum - Sistema de Gestión v2.0"
    }
)

# Header principal con diseño profesional (compatible móvil)
st.markdown("""
    <div style='text-align: center; padding: 1.5rem 0 1rem 0;'>
        <h1 style='margin: 0; font-size: 2.25rem; font-weight: 700; color: #1a1a2e;'>
            Magnus Parfum
        </h1>
        <p style='margin: 0.5rem 0 0 0; color: #636e72; font-size: 0.95rem; font-weight: 500;'>
            Sistema Integral de Gestión Empresarial
        </p>
    </div>
""", unsafe_allow_html=True)

st.markdown("---")

# Cargar DB
try:
    db = load_full_db()
except Exception as e:
    st.error(f"Error al cargar la base de datos: {e}")
    st.stop()

# Migración: asegurar campos nuevos
for p in db.get("inventory", []):
    if "inv" not in p:
        p["inv"] = True

for s in db.get("sales", []):
    if "inv" not in s:
        s["inv"] = None

# ==================== MÉTRICAS SUPERIORES ====================
try:
    caja, banco = cash_bank_balances(db)
    stock_cost = sum((p.get("cost", 0) or 0) * (p.get("stock", 0) or 0) for p in db["inventory"])
    total_cobrar = sum(credit_saldo(c) for c in db["credits"])

    # Mostrar métricas en tarjetas
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Inventario",
            value=cop(stock_cost),
            delta="Costo total" if stock_cost > 0 else None,
            help="Valor total del inventario"
        )

    with col2:
        st.metric(
            label="Caja",
            value=cop(caja),
            delta="Disponible" if caja > 0 else None,
            help="Efectivo disponible"
        )

    with col3:
        st.metric(
            label="Banco",
            value=cop(banco),
            delta="En cuenta" if banco > 0 else None,
            help="Saldo bancario"
        )

    with col4:
        clientes_con_deuda = len([c for c in db['credits'] if credit_saldo(c) > 0])
        st.metric(
            label="Por Cobrar",
            value=cop(total_cobrar),
            delta=f"{clientes_con_deuda} clientes" if clientes_con_deuda > 0 else None,
            help="Cuentas pendientes"
        )
except Exception as e:
    st.warning(f"Error al calcular métricas: {e}")

st.markdown("---")

# ==================== PESTAÑAS ====================
tabs = st.tabs([
    "Inventario", 
    "Compras", 
    "Ventas", 
    "Créditos", 
    "Inversionista",
    "Reportes", 
    "Proveedores", 
    "Caja y Banco",
    "Configuración"
])

try:
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
except Exception as e:
    st.error(f"Error al cargar pestaña: {e}")
    st.exception(e)