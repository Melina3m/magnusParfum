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
        try:
            return m["fecha"]
        except Exception:
            return ""
    
    movs.sort(key=_key, reverse=True)
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
    st.markdown("""
        <div style='margin-bottom: 2rem;'>
            <h2 style='margin: 0; color: #1a1a2e;'>Caja y Bancos</h2>
            <p style='margin: 0.5rem 0 0 0; color: #636e72;'>
                Control de efectivo y movimientos bancarios
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    # Calcular saldos
    saldo_caja, saldo_banco = cash_bank_balances(db)
    saldo_total = saldo_caja + saldo_banco
    
    # Métricas principales
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
            <div style='background: linear-gradient(135deg, #d4f1e8, #b8e6d5); 
                        padding: 1.5rem; border-radius: 12px; text-align: center;'>
                <div style='font-size: 0.875rem; color: #636e72; margin-bottom: 0.5rem;'>
                    Efectivo en Caja
                </div>
                <div style='font-size: 2rem; font-weight: 700; color: #1a1a2e;'>
                    {cop(saldo_caja)}
                </div>
                <div style='font-size: 0.75rem; color: #95a5a6; margin-top: 0.5rem;'>
                    Dinero físico disponible
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
            <div style='background: linear-gradient(135deg, #d9e8ff, #b3d4ff); 
                        padding: 1.5rem; border-radius: 12px; text-align: center;'>
                <div style='font-size: 0.875rem; color: #636e72; margin-bottom: 0.5rem;'>
                    Saldo en Banco
                </div>
                <div style='font-size: 2rem; font-weight: 700; color: #1a1a2e;'>
                    {cop(saldo_banco)}
                </div>
                <div style='font-size: 0.75rem; color: #95a5a6; margin-top: 0.5rem;'>
                    Saldo en cuentas bancarias
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
            <div style='background: linear-gradient(135deg, #fff4d9, #ffe9b3); 
                        padding: 1.5rem; border-radius: 12px; text-align: center;'>
                <div style='font-size: 0.875rem; color: #636e72; margin-bottom: 0.5rem;'>
                    Total Disponible
                </div>
                <div style='font-size: 2rem; font-weight: 700; color: #1a1a2e;'>
                    {cop(saldo_total)}
                </div>
                <div style='font-size: 0.75rem; color: #95a5a6; margin-top: 0.5rem;'>
                    Caja + Banco
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<hr style='margin: 2rem 0;'>", unsafe_allow_html=True)
    
    # Libro diario de movimientos
    st.markdown("### Libro Diario de Movimientos")
    
    ledger = _movements_ledger(db)
    
    if ledger:
        # Filtros de fecha
        col_filter1, col_filter2 = st.columns(2)
        
        with col_filter1:
            fecha_desde = st.date_input(
                "Desde",
                value=date.today().replace(day=1),
                key="fecha_desde_finance"
            )
        
        with col_filter2:
            fecha_hasta = st.date_input(
                "Hasta",
                value=date.today(),
                key="fecha_hasta_finance"
            )
        
        # Filtrar por fechas
        ledger_filtrado = [
            m for m in ledger 
            if fecha_desde.isoformat() <= m["fecha"] <= fecha_hasta.isoformat()
        ]
        
        if ledger_filtrado:
            # Preparar datos para visualización
            df_display = []
            for mov in ledger_filtrado:
                df_display.append({
                    "Fecha": mov["fecha"],
                    "Tipo": mov["tipo"],
                    "Medio": mov["medio"],
                    "Concepto": mov["concepto"],
                    "Detalle": mov["detalle"] or "N/A",
                    "Monto": cop(mov["monto"])
                })
            
            df_final = pd.DataFrame(df_display)
            
            # Mostrar tabla
            st.dataframe(df_final, use_container_width=True, hide_index=True)
            
            # Estadísticas del período filtrado
            st.markdown("<br>", unsafe_allow_html=True)
            
            total_entradas = sum(m["monto"] for m in ledger_filtrado if m["tipo"] == "Entrada")
            total_salidas = sum(m["monto"] for m in ledger_filtrado if m["tipo"] == "Salida")
            flujo_neto = total_entradas - total_salidas
            
            col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
            
            with col_stat1:
                st.metric("Entradas", cop(total_entradas))
            with col_stat2:
                st.metric("Salidas", cop(total_salidas))
            with col_stat3:
                st.metric("Flujo Neto", cop(flujo_neto))
            with col_stat4:
                st.metric("Movimientos", len(ledger_filtrado))
            
            # Descargar CSV
            csv = df_final.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Descargar movimientos en CSV",
                data=csv,
                file_name=f"movimientos_caja_banco_{fecha_desde}_{fecha_hasta}.csv",
                mime="text/csv"
            )
        else:
            st.info("No hay movimientos en el período seleccionado.")
    else:
        st.info("Aún no hay movimientos registrados en caja o banco.")
    
    st.markdown("<hr style='margin: 2rem 0;'>", unsafe_allow_html=True)
    
    # Desglose por medio de pago
    st.markdown("### Desglose por Medio de Pago")
    
    if ledger:
        # Calcular totales por medio
        caja_entradas = sum(m["monto"] for m in ledger if m["medio"] == "Caja" and m["tipo"] == "Entrada")
        caja_salidas = sum(m["monto"] for m in ledger if m["medio"] == "Caja" and m["tipo"] == "Salida")
        banco_entradas = sum(m["monto"] for m in ledger if m["medio"] == "Banco" and m["tipo"] == "Entrada")
        banco_salidas = sum(m["monto"] for m in ledger if m["medio"] == "Banco" and m["tipo"] == "Salida")
        
        col_desg1, col_desg2 = st.columns(2)
        
        with col_desg1:
            st.markdown("""
                <div style='background: #f8f9fa; padding: 1.5rem; border-radius: 10px;'>
                    <h4 style='margin: 0 0 1rem 0; color: #1a1a2e;'>Movimientos en Caja</h4>
                </div>
            """, unsafe_allow_html=True)
            
            st.markdown(f"""
                <div style='background: #f8f9fa; padding: 1rem; border-radius: 10px; margin-top: 0.5rem;'>
                    <div style='display: flex; justify-content: space-between; margin-bottom: 0.5rem;'>
                        <span>Entradas:</span>
                        <strong style='color: #06d6a0;'>{cop(caja_entradas)}</strong>
                    </div>
                    <div style='display: flex; justify-content: space-between; margin-bottom: 0.5rem;'>
                        <span>Salidas:</span>
                        <strong style='color: #ef476f;'>{cop(caja_salidas)}</strong>
                    </div>
                    <div style='display: flex; justify-content: space-between; padding-top: 0.5rem; 
                                border-top: 2px solid #dee2e6; font-size: 1.1rem;'>
                        <span><strong>Saldo:</strong></span>
                        <strong>{cop(saldo_caja)}</strong>
                    </div>
                </div>
            """, unsafe_allow_html=True)
        
        with col_desg2:
            st.markdown("""
                <div style='background: #f8f9fa; padding: 1.5rem; border-radius: 10px;'>
                    <h4 style='margin: 0 0 1rem 0; color: #1a1a2e;'>Movimientos en Banco</h4>
                </div>
            """, unsafe_allow_html=True)
            
            st.markdown(f"""
                <div style='background: #f8f9fa; padding: 1rem; border-radius: 10px; margin-top: 0.5rem;'>
                    <div style='display: flex; justify-content: space-between; margin-bottom: 0.5rem;'>
                        <span>Entradas:</span>
                        <strong style='color: #06d6a0;'>{cop(banco_entradas)}</strong>
                    </div>
                    <div style='display: flex; justify-content: space-between; margin-bottom: 0.5rem;'>
                        <span>Salidas:</span>
                        <strong style='color: #ef476f;'>{cop(banco_salidas)}</strong>
                    </div>
                    <div style='display: flex; justify-content: space-between; padding-top: 0.5rem; 
                                border-top: 2px solid #dee2e6; font-size: 1.1rem;'>
                        <span><strong>Saldo:</strong></span>
                        <strong>{cop(saldo_banco)}</strong>
                    </div>
                </div>
            """, unsafe_allow_html=True)