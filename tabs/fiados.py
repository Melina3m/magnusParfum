import streamlit as st
import pandas as pd
from datetime import date
from collections import defaultdict
from utils import credit_saldo, apply_customer_payment, uid, build_receipt_pdf

def render_fiados(db):
    st.subheader("Créditos/Fiados")

    per_customer = defaultdict(lambda: {"total": 0.0, "paid": 0.0})
    for c in db["credits"]:
        cust = (c.get("customer") or "Cliente").strip()
        per_customer[cust]["total"] += float(c.get("total", 0))
        per_customer[cust]["paid"] += float(c.get("paid", 0))

    resumen = []
    for cust, vals in per_customer.items():
        saldo = vals["total"] - vals["paid"]
        if saldo > 0 or vals["total"] > 0:
            resumen.append({"cliente": cust, "total": vals["total"], "pagado": vals["paid"], "saldo": saldo})
    
    resumen.sort(key=lambda r: (-r["saldo"], r["cliente"].lower() if isinstance(r["cliente"], str) else ""))

    if resumen:
        st.markdown("### Resumen por cliente")
        df_resumen = pd.DataFrame(resumen)
        st.dataframe(
            df_resumen.style.format({
                "total": "{:,.0f}",
                "pagado": "{:,.0f}",
                "saldo": "{:,.0f}"
            }, thousands="."), 
            use_container_width=True
        )
    else:
        st.info("No hay créditos registrados.")

    st.markdown("---")
    
    # --- SECCIÓN DE REGISTRO (TU CÓDIGO ORIGINAL) ---
    st.markdown("### Registrar abono por cliente")
    
    if 'pdf_data' not in st.session_state:
        st.session_state.pdf_data = None
    if 'pdf_filename' not in st.session_state:
        st.session_state.pdf_filename = None

    if st.session_state.pdf_data:
        st.success("Abono aplicado. Puedes descargar el recibo.")
        st.download_button(
            "⬇️ Descargar recibo (PDF)",
            data=st.session_state.pdf_data,
            file_name=st.session_state.pdf_filename,
            mime="application/pdf"
        )
        if st.button("Limpiar descarga"):
            st.session_state.pdf_data = None
            st.session_state.pdf_filename = None
            st.rerun()

    clientes = sorted(list(per_customer.keys()))
    if clientes:
        with st.form("credit_payment_form", clear_on_submit=True):
            c1, c2, c3 = st.columns([2,1,1])
            sel_customer = c1.selectbox("Cliente", options=clientes, key="sel_cust_abono")
            abono = c2.number_input("Abono", min_value=0.0, step=1000.0, value=0.0, format="%.0f", key="abono_cust")
            fecha_abono = c3.date_input("Fecha", value=date.today(), key="fecha_abono_cust")
            c4, c5 = st.columns([1,2])
            medio_abono = c4.selectbox("Medio", options=["Efectivo", "Transferencia", "Tarjeta"], key="medio_abono_cust")
            notas_abono = c5.text_input("Notas", key="notas_abono_cust")
            ok = st.form_submit_button("Registrar abono")
        
        if ok:
            monto = float(abono or 0)
            if monto > 0:
                # Lógica de saldos y snapshot (Tal cual la tenías)
                before = sum(credit_saldo(c) for c in db["credits"] if (c.get("customer","").strip().lower() == sel_customer.strip().lower()))
                snapshot = [{"id": c["id"], "date": c.get("date",""), "saldo": credit_saldo(c)} for c in db["credits"] if (c.get("customer","").strip().lower() == sel_customer.strip().lower()) and credit_saldo(c) > 0]
                
                applied = apply_customer_payment(db, sel_customer, monto, fecha_abono.isoformat(), notas_abono, medio_abono)
                
                after = sum(credit_saldo(c) for c in db["credits"] if (c.get("customer","").strip().lower() == sel_customer.strip().lower()))
                
                breakdown = []
                for s in snapshot:
                    cnow = next((c for c in db["credits"] if c["id"] == s["id"]), None)
                    if cnow:
                        applied_s = max(0.0, float(s["saldo"]) - credit_saldo(cnow))
                        if applied_s > 0:
                            breakdown.append({"id": s["id"], "date": s.get("date",""), "applied": applied_s, "remaining": credit_saldo(cnow)})

                rid = "RC-" + uid()[-8:]
                pdf_bytes = build_receipt_pdf(
                    db, who_type="CLIENTE", who_name=sel_customer, receipt_id=rid,
                    date_str=fecha_abono.isoformat(), amount=applied,
                    balance_before=before, balance_after=after,
                    notes=notas_abono, breakdown=breakdown
                )
                st.session_state.pdf_data = pdf_bytes
                st.session_state.pdf_filename = f"recibo_{sel_customer}_{fecha_abono.isoformat()}.pdf"
                st.rerun()

    # --- NUEVA SECCIÓN: REIMPRESIÓN DE RECIBOS ---
    st.markdown("---")
    st.markdown("### 🔍 Historial y Reimpresión")
    
    pagos = db.get("credit_payments", [])
    if pagos:
        # Creamos una lista de textos para el selector
        # Los mostramos del más reciente al más antiguo
        opciones_pagos = sorted(pagos, key=lambda x: x.get('date', ''), reverse=True)
        
        with st.expander("Ver abonos anteriores"):
            for i, p in enumerate(opciones_pagos[:10]): # Mostramos los últimos 10
                col_info, col_btn = st.columns([3, 1])
                
                info_pago = f"📅 {p.get('date')} | 👤 {p.get('customer')} | 💰 ${float(p.get('amount',0)):,.0f}"
                col_info.write(info_pago)
                
                # Botón único para cada pago
                if col_btn.button("Generar PDF", key=f"reimprimir_{i}"):
                    # Aquí el truco: Regeneramos el PDF con los datos que ya están guardados
                    # Nota: balance_before y after deben estar en el dict del pago si quieres que salgan igual
                    pdf_re = build_receipt_pdf(
                        db, 
                        who_type="CLIENTE", 
                        who_name=p.get('customer'), 
                        receipt_id=f"RC-RE-{i}", 
                        date_str=p.get('date'), 
                        amount=p.get('amount'),
                        balance_before=p.get('balance_before', 0), # Ver nota abajo
                        balance_after=p.get('balance_after', 0),
                        notes=p.get('notes', ""),
                        breakdown=p.get('breakdown', [])
                    )
                    
                    st.download_button(
                        "⬇️ Descargar copia",
                        data=pdf_re,
                        file_name=f"recibo_COPIA_{p.get('customer')}.pdf",
                        mime="application/pdf",
                        key=f"dl_{i}"
                    )
    else:
        st.info("No hay historial de pagos todavía.")