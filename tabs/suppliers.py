import streamlit as st
import pandas as pd
from datetime import date
from collections import defaultdict
from utils import supplier_credit_saldo, apply_supplier_payment, uid, build_receipt_pdf, cop

def render_suppliers(db):
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
            <h2 style='margin: 0; color: #1a1a2e;'>Cuentas por Pagar</h2>
            <p style='margin: 0.5rem 0 0 0; color: #636e72;'>
                Gestión de deudas con proveedores y pagos
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    # Calcular resumen por proveedor
    per_supplier = defaultdict(lambda: {"total": 0.0, "paid": 0.0})
    for c in db.get("supplier_credits", []):
        sup = (c.get("supplier") or "Proveedor").strip()
        per_supplier[sup]["total"] += float(c.get("total", 0))
        per_supplier[sup]["paid"] += float(c.get("paid", 0))

    resumen = []
    for sup, vals in per_supplier.items():
        saldo = vals["total"] - vals["paid"]
        if saldo > 0 or vals["total"] > 0:
            resumen.append({
                "proveedor": sup, 
                "total": vals["total"], 
                "pagado": vals["paid"], 
                "saldo": saldo
            })
    resumen.sort(key=lambda r: (-r["saldo"], r["proveedor"].lower() if isinstance(r["proveedor"], str) else ""))

    # Mostrar resumen
    if resumen:
        st.markdown("### Resumen por Proveedor")
        
        # Métricas generales
        total_deuda = sum(r["total"] for r in resumen)
        total_pagado = sum(r["pagado"] for r in resumen)
        total_pendiente = sum(r["saldo"] for r in resumen)
        proveedores_con_deuda = sum(1 for r in resumen if r["saldo"] > 0)
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
                <div class="card-metric" style="background: linear-gradient(135deg, #ffd9e0, #ffb3c1);">
                    <div class="card-title">Deuda Total</div>
                    <div class="card-value">{cop(total_deuda)}</div>
                    <div class="card-note">Suma de todas las compras a crédito</div>
                </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
                <div class="card-metric" style="background: linear-gradient(135deg, #d4f1e8, #b8e6d5);">
                    <div class="card-title">Pagado</div>
                    <div class="card-value">{cop(total_pagado)}</div>
                    <div class="card-note">Total de pagos realizados</div>
                </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
                <div class="card-metric" style="background: linear-gradient(135deg, #fff4d9, #ffe9b3);">
                    <div class="card-title">Por Pagar</div>
                    <div class="card-value">{cop(total_pendiente)}</div>
                    <div class="card-note">Saldo pendiente</div>
                </div>
            """, unsafe_allow_html=True)
        
        with col4:
            st.markdown(f"""
                <div class="card-metric">
                    <div class="card-title">Proveedores</div>
                    <div class="card-value">{proveedores_con_deuda}</div>
                    <div class="card-note">Con saldo pendiente</div>
                </div>
            """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Tabla de resumen
        df_resumen = pd.DataFrame(resumen)
        df_resumen["total"] = df_resumen["total"].apply(cop)
        df_resumen["pagado"] = df_resumen["pagado"].apply(cop)
        df_resumen["saldo"] = df_resumen["saldo"].apply(cop)
        df_resumen.columns = ["Proveedor", "Total Adeudado", "Total Pagado", "Saldo Pendiente"]
        
        st.dataframe(df_resumen, use_container_width=True, hide_index=True)
    else:
        st.info("No hay deudas con proveedores. Las compras a crédito aparecerán aquí.")

    st.markdown("<hr style='margin: 2rem 0;'>", unsafe_allow_html=True)

    # Reimprimir comprobantes anteriores
    st.markdown("### Reimprimir Comprobantes Anteriores")
    st.caption("Genera nuevamente el comprobante de cualquier pago pasado")
    
    if db.get("supplier_payments"):
        pagos_por_proveedor = defaultdict(list)
        for payment in db["supplier_payments"]:
            proveedor = payment.get("supplier", "Proveedor").strip()
            pagos_por_proveedor[proveedor].append(payment)
        
        proveedores_con_pagos = sorted(list(pagos_por_proveedor.keys()))
        
        if proveedores_con_pagos:
            col_reimp1, col_reimp2 = st.columns([2, 1])
            
            with col_reimp1:
                proveedor_reimprimir = st.selectbox(
                    "Proveedor",
                    options=proveedores_con_pagos,
                    key="proveedor_reimprimir"
                )
            
            pagos_proveedor = sorted(
                pagos_por_proveedor[proveedor_reimprimir],
                key=lambda x: x.get("date", ""),
                reverse=True
            )
            
            with col_reimp2:
                opciones_pagos = []
                for pago in pagos_proveedor:
                    fecha = pago.get("date", "")[:10]
                    monto = cop(pago.get("amount", 0))
                    medio = pago.get("method", "N/A")
                    opciones_pagos.append(f"{fecha} - {monto} ({medio})")
                
                pago_seleccionado_idx = st.selectbox(
                    "Pago",
                    options=range(len(opciones_pagos)),
                    format_func=lambda i: opciones_pagos[i],
                    key="pago_reimprimir"
                )
            
            if st.button("Generar Comprobante", use_container_width=True, key="btn_reimprimir_prov"):
                pago_seleccionado = pagos_proveedor[pago_seleccionado_idx]
                
                saldo_despues = sum(supplier_credit_saldo(c) for c in db["supplier_credits"]
                                   if c.get("supplier","").strip().lower() == proveedor_reimprimir.strip().lower())
                
                monto_pago = float(pago_seleccionado.get("amount", 0))
                saldo_antes = saldo_despues + monto_pago
                
                snapshot = [
                    {"id": c["id"], "date": c.get("date",""), 
                     "applied": min(supplier_credit_saldo(c), monto_pago),
                     "remaining": supplier_credit_saldo(c)}
                    for c in db["supplier_credits"]
                    if (c.get("supplier","").strip().lower() == proveedor_reimprimir.strip().lower())
                    and supplier_credit_saldo(c) > 0
                ]
                
                rid = "RP-" + pago_seleccionado.get("id", uid())[-8:]
                pdf_bytes = build_receipt_pdf(
                    db, 
                    who_type="PROVEEDOR", 
                    who_name=proveedor_reimprimir, 
                    receipt_id=rid,
                    date_str=pago_seleccionado.get("date", ""),
                    amount=monto_pago,
                    balance_before=saldo_antes,
                    balance_after=saldo_despues,
                    notes=pago_seleccionado.get("notes", ""),
                    breakdown=snapshot
                )
                
                st.download_button(
                    "Descargar Comprobante Reimpreso",
                    data=pdf_bytes,
                    file_name=f"comprobante_reimpreso_{proveedor_reimprimir}_{pago_seleccionado.get('date', '')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
        else:
            st.info("No hay pagos registrados para reimprimir.")
    else:
        st.info("No hay pagos registrados para reimprimir.")

    st.markdown("<hr style='margin: 2rem 0;'>", unsafe_allow_html=True)
    
    # Registrar pago
    st.markdown("### Registrar Pago a Proveedor")
    st.caption("Aplica pagos a las cuentas pendientes con proveedores")
    
    if 'pdf_data_sup' not in st.session_state:
        st.session_state.pdf_data_sup = None
    if 'pdf_filename_sup' not in st.session_state:
        st.session_state.pdf_filename_sup = None

    if st.session_state.pdf_data_sup:
        st.success("Pago aplicado exitosamente. Descarga el comprobante.")
        
        st.download_button(
            "Descargar comprobante (PDF)",
            data=st.session_state.pdf_data_sup,
            file_name=st.session_state.pdf_filename_sup,
            mime="application/pdf",
            use_container_width=True
        )
        
        if st.button("Cerrar y continuar", use_container_width=True):
            st.session_state.pdf_data_sup = None
            st.session_state.pdf_filename_sup = None
            st.rerun()
        
        return

    suppliers = sorted(list(per_supplier.keys()))
    
    if suppliers:
        sel_supplier = st.selectbox(
            "Selecciona el proveedor", 
            options=suppliers, 
            key="selector_proveedor_pago",
            help="Proveedor al que se realizará el pago"
        )
        
        saldo_actual = per_supplier[sel_supplier]["total"] - per_supplier[sel_supplier]["paid"]
        st.markdown(f"""
            <div style='background: linear-gradient(135deg, #ffd9e0, #ffb3c1); 
                        padding: 1rem; border-radius: 10px; margin-top: 0.5rem; margin-bottom: 1rem;'>
                Deuda pendiente con <strong>{sel_supplier}</strong>: 
                <strong style='font-size: 1.2rem;'>{cop(saldo_actual)}</strong>
            </div>
        """, unsafe_allow_html=True)
        
        with st.form("form_pago_proveedor", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                abono = st.number_input(
                    "Monto del pago", 
                    min_value=0.0, 
                    step=1000.0, 
                    value=0.0, 
                    format="%.0f", 
                    key="input_pago_proveedor",
                    help="Cantidad que se pagará al proveedor"
                )
            
            with col2:
                fecha_abono = st.date_input(
                    "Fecha del pago", 
                    key="input_fecha_pago_proveedor", 
                    value=date.today(),
                    help="Fecha en que se realiza el pago"
                )
            
            col3, col4 = st.columns(2)
            
            with col3:
                medio_pago_sup = st.selectbox(
                    "Forma de pago", 
                    options=["Efectivo", "Transferencia", "Tarjeta"], 
                    key="input_medio_pago_proveedor",
                    help="Método de pago utilizado"
                )
            
            with col4:
                notas_abono = st.text_input(
                    "Notas (opcional)", 
                    key="input_notas_pago_proveedor",
                    placeholder="Observaciones sobre el pago"
                )
            
            if abono > 0:
                nuevo_saldo = max(0, saldo_actual - abono)
                st.markdown(f"""
                    <div style='background: linear-gradient(135deg, #d4f1e8, #b8e6d5); 
                                padding: 1.25rem; border-radius: 10px; margin-top: 1rem;'>
                        <div style='font-size: 0.875rem; color: #037856; margin-bottom: 0.5rem;'>
                            <strong>RESUMEN DEL PAGO</strong>
                        </div>
                        <div style='display: flex; justify-content: space-between;'>
                            <span>Deuda actual:</span>
                            <strong>{cop(saldo_actual)}</strong>
                        </div>
                        <div style='display: flex; justify-content: space-between;'>
                            <span>Pago a aplicar:</span>
                            <strong style='color: #037856;'>- {cop(abono)}</strong>
                        </div>
                        <div style='display: flex; justify-content: space-between; margin-top: 0.5rem; 
                                    padding-top: 0.5rem; border-top: 2px solid #06d6a0; font-size: 1.1rem;'>
                            <span>Nueva deuda:</span>
                            <strong style='color: #037856;'>{cop(nuevo_saldo)}</strong>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
            
            ok = st.form_submit_button("Registrar Pago", use_container_width=True, type="primary")
            
        if ok:
            monto = float(abono or 0)
            if monto > 0:
                before = sum(supplier_credit_saldo(c) for c in db["supplier_credits"]
                            if (c.get("supplier","").strip().lower() == sel_supplier.strip().lower()))

                snapshot = [
                    {"id": c["id"], "date": c.get("date",""), "saldo": supplier_credit_saldo(c)}
                    for c in db["supplier_credits"]
                    if (c.get("supplier","").strip().lower() == sel_supplier.strip().lower()) 
                    and supplier_credit_saldo(c) > 0
                ]
                
                applied = apply_supplier_payment(db, sel_supplier, monto, fecha_abono.isoformat(), 
                                                notas_abono, medio_pago_sup)
                
                after = sum(supplier_credit_saldo(c) for c in db["supplier_credits"]
                           if (c.get("supplier","").strip().lower() == sel_supplier.strip().lower()))

                breakdown = []
                for s in snapshot:
                    cnow = next((c for c in db["supplier_credits"] if c["id"] == s["id"]), None)
                    if cnow:
                        before_s = float(s["saldo"])
                        after_s = supplier_credit_saldo(cnow)
                        applied_s = max(0.0, before_s - after_s)
                        if applied_s > 0:
                            breakdown.append({
                                "id": s["id"], "date": s.get("date",""),
                                "applied": applied_s, "remaining": after_s
                            })

                rid = "RP-" + uid()[-8:]
                pdf_bytes = build_receipt_pdf(
                    db, who_type="PROVEEDOR", who_name=sel_supplier, receipt_id=rid,
                    date_str=fecha_abono.isoformat(), amount=applied,
                    balance_before=before, balance_after=after,
                    notes=notas_abono, breakdown=breakdown
                )
                
                st.session_state.pdf_data_sup = pdf_bytes
                st.session_state.pdf_filename_sup = f"recibo_pago_proveedor_{sel_supplier}_{fecha_abono.isoformat()}.pdf"
                st.rerun()
            else:
                st.warning("El monto del pago debe ser mayor a cero.")
    else:
        st.info("No hay proveedores con deudas pendientes para registrar pagos.")

    st.markdown("<hr style='margin: 2rem 0;'>", unsafe_allow_html=True)

    # Detalle de créditos con proveedores
    st.markdown("### Detalle de Deudas")
    
    with st.expander("Ver todas las compras a crédito", expanded=False):
        if db.get("supplier_credits"):
            df_credits = []
            for c in db["supplier_credits"]:
                saldo = supplier_credit_saldo(c)
                estado = "Pagado" if saldo <= 0 else "Pendiente"
                
                df_credits.append({
                    "Fecha": c.get("date", ""),
                    "Proveedor": c.get("supplier", "N/A"),
                    "Total": cop(c.get("total", 0)),
                    "Pagado": cop(c.get("paid", 0)),
                    "Saldo": cop(saldo),
                    "Estado": estado,
                    "Vencimiento": c.get("due_date", "N/A") or "N/A",
                    "Factura": c.get("invoice", "N/A") or "N/A"
                })
            
            df_final = pd.DataFrame(df_credits)
            
            if not df_final.empty and "Fecha" in df_final.columns:
                df_final = df_final.sort_values("Fecha", ascending=False)
            
            st.dataframe(df_final, use_container_width=True, hide_index=True)
            
            csv = df_final.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Descargar detalle en CSV",
                data=csv,
                file_name="detalle_proveedores.csv",
                mime="text/csv"
            )
        else:
            st.info("No hay deudas con proveedores registradas.")