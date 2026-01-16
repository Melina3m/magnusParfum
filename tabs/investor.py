import streamlit as st
import pandas as pd
from datetime import date
from database import insert_record
from utils import uid, cop

def render_investor(db):
    # Agregar estilos CSS inline
    st.markdown("""
        <style>
        .card-metric {
            background: linear-gradient(135deg, #e8f4f8, #d4e9f5);
            padding: 1.25rem;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }
        .card-title {
            font-size: 0.875rem;
            color: #636e72;
            margin-bottom: 0.5rem;
            font-weight: 500;
        }
        .card-value {
            font-size: 1.75rem;
            font-weight: 700;
            color: #1a1a2e;
            margin-bottom: 0.25rem;
        }
        .card-note {
            font-size: 0.75rem;
            color: #95a5a6;
            margin-top: 0.25rem;
        }
        </style>
    """, unsafe_allow_html=True)
    
    st.markdown("""
        <div style='margin-bottom: 2rem;'>
            <h2 style='margin: 0; color: #1a1a2e;'>Cuenta del Inversionista</h2>
            <p style='margin: 0.5rem 0 0 0; color: #636e72;'>
                Registro de aportes, retiros y cálculo de utilidades
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    # Calcular métricas del inversionista
    aportes = sum(float(x.get("amount",0)) for x in db["investor"] if x.get("type") == "Aporte")
    retiros = sum(float(x.get("amount",0)) for x in db["investor"] if x.get("type") == "Retiro")
    utilidades_reg = sum(float(x.get("amount",0)) for x in db["investor"] if x.get("type") == "Utilidad")
    capital_neto = aportes - retiros
    
    # Mostrar métricas
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
            <div class="card-metric" style="background: linear-gradient(135deg, #d4f1e8, #b8e6d5);">
                <div class="card-title">Aportes</div>
                <div class="card-value">{cop(aportes)}</div>
                <div class="card-note">Capital invertido</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
            <div class="card-metric" style="background: linear-gradient(135deg, #ffd9e0, #ffb3c1);">
                <div class="card-title">Retiros</div>
                <div class="card-value">{cop(retiros)}</div>
                <div class="card-note">Capital retirado</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
            <div class="card-metric" style="background: linear-gradient(135deg, #d9e8ff, #b3d4ff);">
                <div class="card-title">Capital Neto</div>
                <div class="card-value">{cop(capital_neto)}</div>
                <div class="card-note">Inversión actual</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
            <div class="card-metric" style="background: linear-gradient(135deg, #fff4d9, #ffe9b3);">
                <div class="card-title">Utilidades</div>
                <div class="card-value">{cop(utilidades_reg)}</div>
                <div class="card-note">Registradas históricamente</div>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<hr style='margin: 2rem 0;'>", unsafe_allow_html=True)
    
    # Formulario de nuevo movimiento
    st.markdown("### Registrar Movimiento")
    
    with st.form("inv_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            idate = st.date_input(
                "Fecha", 
                value=date.today(), 
                key="idate",
                help="Fecha del movimiento"
            )
        
        with col2:
            itype = st.selectbox(
                "Tipo de movimiento", 
                options=["Aporte", "Retiro", "Utilidad"], 
                key="itype",
                help="Tipo de transacción del inversionista"
            )
        
        with col3:
            amount = st.number_input(
                "Monto", 
                min_value=0.0, 
                step=1000.0, 
                value=0.0, 
                format="%.0f", 
                key="iamount",
                help="Cantidad de dinero del movimiento"
            )
        
        notes = st.text_area(
            "Notas adicionales", 
            key="inotes",
            placeholder="Descripción del movimiento, referencia, etc.",
            height=80
        )
        
        # Resumen del movimiento
        if amount > 0:
            color_map = {
                "Aporte": "#06d6a0",
                "Retiro": "#ef476f",
                "Utilidad": "#ffd166"
            }
            bg_map = {
                "Aporte": "linear-gradient(135deg, #d4f1e8, #b8e6d5)",
                "Retiro": "linear-gradient(135deg, #ffd9e0, #ffb3c1)",
                "Utilidad": "linear-gradient(135deg, #fff4d9, #ffe9b3)"
            }
            
            nuevo_capital = capital_neto
            if itype == "Aporte":
                nuevo_capital += amount
            elif itype == "Retiro":
                nuevo_capital -= amount
            
            st.markdown(f"""
                <div style='background: {bg_map[itype]}; 
                            padding: 1.25rem; border-radius: 10px; margin-top: 1rem;'>
                    <div style='font-size: 0.875rem; color: #2d3436; margin-bottom: 0.5rem;'>
                        <strong>RESUMEN DEL MOVIMIENTO</strong>
                    </div>
                    <div style='display: flex; justify-content: space-between;'>
                        <span>Tipo:</span>
                        <strong>{itype}</strong>
                    </div>
                    <div style='display: flex; justify-content: space-between;'>
                        <span>Monto:</span>
                        <strong>{cop(amount)}</strong>
                    </div>
                    {"" if itype == "Utilidad" else f'''
                    <div style='display: flex; justify-content: space-between; margin-top: 0.5rem; 
                                padding-top: 0.5rem; border-top: 2px solid {color_map[itype]};'>
                        <span>Nuevo capital neto:</span>
                        <strong>{cop(nuevo_capital)}</strong>
                    </div>
                    '''}
                </div>
            """, unsafe_allow_html=True)
        
        ok = st.form_submit_button("Registrar Movimiento", use_container_width=True, type="primary")
        
        if ok:
            if amount <= 0:
                st.error("El monto debe ser mayor a cero.")
            else:
                insert_record("investor", {
                    "id": uid(), 
                    "date": idate.isoformat(), 
                    "type": itype,
                    "amount": float(amount or 0), 
                    "notes": notes
                })
                st.success(f"{itype} de {cop(amount)} registrado exitosamente.")
                st.rerun()
    
    st.markdown("<hr style='margin: 2rem 0;'>", unsafe_allow_html=True)
    
    # Historial de movimientos
    st.markdown("### Historial de Movimientos")
    
    if db["investor"]:
        df_investor = pd.DataFrame(db["investor"])
        
        # Preparar datos para visualización
        df_display = []
        for _, mov in df_investor.iterrows():
            tipo = mov.get("type", "N/A")
            monto = mov.get("amount", 0)
            
            df_display.append({
                "Fecha": mov.get("date", ""),
                "Tipo": tipo,
                "Monto": cop(monto),
                "Notas": mov.get("notes", "") or "Sin notas"
            })
        
        df_final = pd.DataFrame(df_display)
        
        # Ordenar por fecha descendente
        if not df_final.empty and "Fecha" in df_final.columns:
            df_final = df_final.sort_values("Fecha", ascending=False)
        
        st.dataframe(df_final, use_container_width=True, hide_index=True)
        
        # Estadísticas adicionales
        st.markdown("<br>", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        
        num_aportes = len([x for x in db["investor"] if x.get("type") == "Aporte"])
        num_retiros = len([x for x in db["investor"] if x.get("type") == "Retiro"])
        num_utilidades = len([x for x in db["investor"] if x.get("type") == "Utilidad"])
        
        with col1:
            st.metric("Total de Aportes", num_aportes)
        with col2:
            st.metric("Total de Retiros", num_retiros)
        with col3:
            st.metric("Registros de Utilidades", num_utilidades)
        
        # Descargar CSV
        csv = df_final.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Descargar historial en CSV",
            data=csv,
            file_name="historial_inversionista.csv",
            mime="text/csv"
        )
    else:
        st.info("Aún no hay movimientos del inversionista registrados.")
    
    st.markdown("<hr style='margin: 2rem 0;'>", unsafe_allow_html=True)
    
    # Información sobre utilidades
    st.markdown("### Cálculo de Utilidades")
    st.markdown(f"""
        <div style='background: #f8f9fa; padding: 1.5rem; border-radius: 10px; border-left: 4px solid #0f3460;'>
            <p style='margin: 0; color: #2d3436;'>
                El porcentaje de participación del inversionista se configura en la pestaña 
                <strong>Configuración</strong>. Actualmente está establecido en 
                <strong>{db["settings"].get("investor_share", 50)}%</strong>.
            </p>
            <p style='margin: 0.5rem 0 0 0; color: #636e72; font-size: 0.875rem;'>
                Las utilidades se calculan únicamente sobre las ventas de productos marcados 
                como "INV" (Inversionista) en el inventario y en cada venta.
            </p>
        </div>
    """, unsafe_allow_html=True)