import streamlit as st
import pandas as pd
from datetime import date
from utils import cop

def render_reports(db):
    st.markdown("""
        <div style='margin-bottom: 2rem;'>
            <h2 style='margin: 0; color: #1a1a2e;'>Reportes de Utilidades y Resultados</h2>
            <p style='margin: 0.5rem 0 0 0; color: #636e72;'>
                Análisis de ventas, utilidades y participación del inversionista
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    # Filtros de Fecha
    st.markdown("### Período de Análisis")
    c1, c2 = st.columns(2)
    ffrom = c1.date_input("Desde", value=date.today().replace(day=1), key="ffrom")
    fto = c2.date_input("Hasta", value=date.today(), key="fto")

    # Filtrado de ventas por rango
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

    # Cálculos Globales
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

    # Datos del Inversionista
    aportes = sum(float(x.get("amount",0)) for x in db["investor"] if x.get("type") == "Aporte")
    retiros = sum(float(x.get("amount",0)) for x in db["investor"] if x.get("type") == "Retiro")
    capital_neto = aportes - retiros
    
    investor_pct = db["settings"].get("investor_share", 50) / 100.0
    investor_cut = profit_inv * investor_pct

    st.markdown("<hr style='margin: 2rem 0;'>", unsafe_allow_html=True)
    
    # Visualización - Métricas Principales
    st.markdown("### Resumen Operativo del Período")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
            <div style='background: linear-gradient(135deg, #d9e8ff, #b3d4ff); 
                        padding: 1.5rem; border-radius: 12px; text-align: center;'>
                <div style='font-size: 0.875rem; color: #636e72; margin-bottom: 0.5rem;'>
                    Ventas Totales
                </div>
                <div style='font-size: 2rem; font-weight: 700; color: #1a1a2e;'>
                    {cop(sales_total)}
                </div>
                <div style='font-size: 0.75rem; color: #95a5a6; margin-top: 0.5rem;'>
                    {len(fsales)} ventas realizadas
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        margin_pct = (profit_total / sales_total * 100) if sales_total > 0 else 0
        st.markdown(f"""
            <div style='background: linear-gradient(135deg, #d4f1e8, #b8e6d5); 
                        padding: 1.5rem; border-radius: 12px; text-align: center;'>
                <div style='font-size: 0.875rem; color: #636e72; margin-bottom: 0.5rem;'>
                    Utilidad Bruta Total
                </div>
                <div style='font-size: 2rem; font-weight: 700; color: #1a1a2e;'>
                    {cop(profit_total)}
                </div>
                <div style='font-size: 0.75rem; color: #95a5a6; margin-top: 0.5rem;'>
                    Margen: {margin_pct:.1f}%
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
            <div style='background: linear-gradient(135deg, #fff4d9, #ffe9b3); 
                        padding: 1.5rem; border-radius: 12px; text-align: center;'>
                <div style='font-size: 0.875rem; color: #636e72; margin-bottom: 0.5rem;'>
                    Capital Neto Invertido
                </div>
                <div style='font-size: 2rem; font-weight: 700; color: #1a1a2e;'>
                    {cop(capital_neto)}
                </div>
                <div style='font-size: 0.75rem; color: #95a5a6; margin-top: 0.5rem;'>
                    Aportes - Retiros
                </div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<hr style='margin: 2rem 0;'>", unsafe_allow_html=True)
    
    # Parte del Inversionista
    st.markdown("### Participación del Inversionista")
    
    i1, i2, i3 = st.columns(3)
    
    with i1:
        st.markdown(f"""
            <div style='background: linear-gradient(135deg, #e8d4f1, #d5b8e6); 
                        padding: 1.5rem; border-radius: 12px; text-align: center;'>
                <div style='font-size: 0.875rem; color: #636e72; margin-bottom: 0.5rem;'>
                    Ventas INV
                </div>
                <div style='font-size: 2rem; font-weight: 700; color: #1a1a2e;'>
                    {cop(sales_inv)}
                </div>
                <div style='font-size: 0.75rem; color: #95a5a6; margin-top: 0.5rem;'>
                    Solo productos marcados INV
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    with i2:
        st.markdown(f"""
            <div style='background: linear-gradient(135deg, #d4e8f1, #b8d5e6); 
                        padding: 1.5rem; border-radius: 12px; text-align: center;'>
                <div style='font-size: 0.875rem; color: #636e72; margin-bottom: 0.5rem;'>
                    Utilidad INV
                </div>
                <div style='font-size: 2rem; font-weight: 700; color: #1a1a2e;'>
                    {cop(profit_inv)}
                </div>
                <div style='font-size: 0.75rem; color: #95a5a6; margin-top: 0.5rem;'>
                    Ganancia en productos INV
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    with i3:
        st.markdown(f"""
            <div style='background: linear-gradient(135deg, #ffd9e0, #ffb3c1); 
                        padding: 1.5rem; border-radius: 12px; text-align: center;'>
                <div style='font-size: 0.875rem; color: #636e72; margin-bottom: 0.5rem;'>
                    A Pagar ({int(investor_pct*100)}%)
                </div>
                <div style='font-size: 2rem; font-weight: 700; color: #c4183c;'>
                    {cop(investor_cut)}
                </div>
                <div style='font-size: 0.75rem; color: #95a5a6; margin-top: 0.5rem;'>
                    Parte del inversionista
                </div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<hr style='margin: 2rem 0;'>", unsafe_allow_html=True)

    # Desglose adicional
    st.markdown("### Análisis Detallado")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Ventas por Tipo")
        ventas_inv_count = sum(1 for s in fsales if get_sale_data(s)[2])
        ventas_no_inv_count = len(fsales) - ventas_inv_count
        sales_no_inv = sales_total - sales_inv
        
        st.markdown(f"""
            <div style='background: #f8f9fa; padding: 1rem; border-radius: 8px;'>
                <div style='margin-bottom: 0.5rem;'>
                    <strong>Productos INV:</strong> {ventas_inv_count} ventas - {cop(sales_inv)}
                </div>
                <div>
                    <strong>Productos NO INV:</strong> {ventas_no_inv_count} ventas - {cop(sales_no_inv)}
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("#### Utilidades por Tipo")
        profit_no_inv = profit_total - profit_inv
        owner_cut = profit_total - investor_cut
        
        st.markdown(f"""
            <div style='background: #f8f9fa; padding: 1rem; border-radius: 8px;'>
                <div style='margin-bottom: 0.5rem;'>
                    <strong>Utilidad INV:</strong> {cop(profit_inv)}
                </div>
                <div style='margin-bottom: 0.5rem;'>
                    <strong>Utilidad NO INV:</strong> {cop(profit_no_inv)}
                </div>
                <div style='padding-top: 0.5rem; border-top: 1px solid #dee2e6;'>
                    <strong>Para propietario:</strong> {cop(owner_cut)}
                </div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<hr style='margin: 2rem 0;'>", unsafe_allow_html=True)

    # Tabla de detalle
    st.markdown("### Detalle de Ventas del Período")
    
    with st.expander("Ver todas las ventas en detalle", expanded=False):
        if fsales:
            df_display = []
            for sale in fsales:
                prod = next((p for p in db["inventory"] if p["id"] == sale.get("item_id")), None)
                v_total, c_total, is_inv = get_sale_data(sale)
                utilidad = v_total - c_total
                
                df_display.append({
                    "Fecha": sale.get("date", ""),
                    "Cliente": sale.get("customer", "N/A"),
                    "Producto": prod.get("name", "N/A") if prod else "N/A",
                    "Cantidad": sale.get("quantity", 0),
                    "Precio Unit.": cop(sale.get("unit_price", 0)),
                    "Total Venta": cop(v_total),
                    "Costo": cop(c_total),
                    "Utilidad": cop(utilidad),
                    "INV": "Sí" if is_inv else "No",
                    "Pago": sale.get("payment", "N/A")
                })
            
            df_final = pd.DataFrame(df_display)
            
            # Ordenar por fecha descendente
            if not df_final.empty and "Fecha" in df_final.columns:
                df_final = df_final.sort_values("Fecha", ascending=False)
            
            st.dataframe(df_final, use_container_width=True, hide_index=True)
            
            # Descargar CSV
            csv = df_final.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Descargar reporte en CSV",
                data=csv,
                file_name=f"reporte_ventas_{ffrom}_{fto}.csv",
                mime="text/csv"
            )
        else:
            st.info("No hay ventas registradas en este período.")
    
    st.markdown("<hr style='margin: 2rem 0;'>", unsafe_allow_html=True)
    
    # Notas informativas
    st.markdown("### Información del Reporte")
    st.markdown(f"""
        <div style='background: #f8f9fa; padding: 1.5rem; border-radius: 10px; border-left: 4px solid #0f3460;'>
            <p style='margin: 0; color: #2d3436;'>
                <strong>Período analizado:</strong> {ffrom.strftime('%d/%m/%Y')} - {fto.strftime('%d/%m/%Y')}
            </p>
            <p style='margin: 0.5rem 0 0 0; color: #636e72; font-size: 0.875rem;'>
                El porcentaje de participación del inversionista ({int(investor_pct*100)}%) se aplica 
                únicamente sobre las utilidades de productos marcados como "INV" en el inventario.
            </p>
        </div>
    """, unsafe_allow_html=True)