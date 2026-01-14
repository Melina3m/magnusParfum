import streamlit as st
import pandas as pd
from datetime import date
from utils import cop

def render_reports(db):
    st.subheader("📊 Reportes de Utilidades y Resultados")
    
    # 1. Filtros de Fecha
    c1, c2 = st.columns(2)
    ffrom = c1.date_input("Desde", value=date.today().replace(day=1), key="ffrom")
    fto = c2.date_input("Hasta", value=date.today(), key="fto")
    
    # 2. Filtrado de ventas por rango
    fsales = [s for s in db["sales"] if ffrom.isoformat() <= s["date"] <= fto.isoformat()]
    
    # Lógica interna para determinar si una venta es de "Inversionista"
    def get_sale_data(sale):
        prod = next((p for p in db["inventory"] if p["id"] == sale.get("item_id")), None)
        cost_unit = float(sale.get("cost_at_sale") or (prod["cost"] if prod else 0))
        
        is_inv = sale.get("inv")
        if is_inv is None:
            is_inv = bool(prod.get("inv")) if prod else False
                
        total_venta = float(sale["quantity"] * sale["unit_price"])
        total_costo = float(sale["quantity"] * cost_unit)
        return total_venta, total_costo, is_inv

    # 3. Cálculos Globales
    sales_total = 0.0
    profit_total = 0.0
    sales_inv = 0.0
    profit_inv = 0.0
    for s in fsales:
        v_total, c_total, is_inv = get_sale_data(s)
        sales_total += v_total
        profit_total += (v_total - c_total)
        
        if is_inv:
            sales_inv += v_total
            profit_inv += (v_total - c_total)

    # 4. Datos del Inversionista
    aportes = sum(float(x.get("amount",0)) for x in db["investor"] if x.get("type") == "Aporte")
    retiros = sum(float(x.get("amount",0)) for x in db["investor"] if x.get("type") == "Retiro")
    capital_neto = aportes - retiros
    
    investor_pct = db["settings"].get("investor_share", 50) / 100.0
    investor_cut = profit_inv * investor_pct

    # 5. Visualización (Métricas Principales)
    st.markdown("### Resumen Operativo")
    m1, m2, m3 = st.columns(3)
    m1.metric("Ventas Totales", cop(sales_total))
    m2.metric("Utilidad Bruta Total", cop(profit_total))
    m3.metric("Capital Neto Invertido", cop(capital_neto))
    
    st.markdown("---")
    st.markdown("### Parte del Inversionista")
    i1, i2, i3 = st.columns(3)
    i1.metric("Ventas (Solo INV)", cop(sales_inv))
    i2.metric("Utilidad (Solo INV)", cop(profit_inv))
    i3.metric(f"A pagar ({int(investor_pct*100)}%)", cop(investor_cut), delta_color="normal")

    # 6. Tabla de detalle
    with st.expander("Ver detalle de ventas en el periodo"):
        if fsales:
            df_display = pd.DataFrame(fsales)
            cols = ["date", "customer", "quantity", "unit_price", "payment", "inv"]
            
            # --- CAMBIO AQUÍ: Formato de miles para la tabla de reportes ---
            if all(c in df_display for c in cols):
                df_to_show = df_display[cols]
            else:
                df_to_show = df_display
                
            st.dataframe(
                df_to_show.style.format({
                    "unit_price": "{:,.0f}",
                    "quantity": "{:,.0f}"
                }).replace(",", "."), 
                use_container_width=True
            )
            # -------------------------------------------------------------
        else:
            st.info("No hay ventas registradas en este periodo.")