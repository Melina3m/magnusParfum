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
            }).replace(",", "."), 
            use_container_width=True
        )
    else:
        st.info("No hay créditos registrados.")

    st.markdown("---")
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
        st.session_state.pdf_data = None
        st.session_state.pdf_filename = None

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
                before = sum(credit_saldo(c) for c in db["credits"]
                            if (c.get("customer","").strip().lower() == sel_customer.strip().lower()))
                snapshot = [
                    {"id": c["id"], "date": c.get("date",""), "saldo": credit_saldo(c)}
                    for c in db["credits"]
                    if (c.get("customer","").strip().lower() == sel_customer.strip().lower()) and credit_saldo(c) > 0
                ]
                applied = apply_customer_payment(db, sel_customer, monto, fecha_abono.isoformat(), notas_abono, medio_abono)
                after = sum(credit_saldo(c) for c in db["credits"]
                           if (c.get("customer","").strip().lower() == sel_customer.strip().lower()))

                breakdown = []
                for s in snapshot:
                    cnow = next((c for c in db["credits"] if c["id"] == s["id"]), None)
                    if cnow:
                        before_s = float(s["saldo"])
                        after_s = credit_saldo(cnow)
                        applied_s = max(0.0, before_s - after_s)
                        if applied_s > 0:
                            breakdown.append({
                                "id": s["id"], "date": s.get("date",""),
                                "applied": applied_s, "remaining": after_s
                            })

                rid = "RC-" + uid()[-8:]
                pdf_bytes = build_receipt_pdf(
                    db, who_type="CLIENTE", who_name=sel_customer, receipt_id=rid,
                    date_str=fecha_abono.isoformat(), amount=applied,
                    balance_before=before, balance_after=after,
                    notes=notas_abono, breakdown=breakdown
                )
                
                st.session_state.pdf_data = pdf_bytes
                st.session_state.pdf_filename = f"recibo_abono_cliente_{sel_customer}_{fecha_abono.isoformat()}.pdf"
                st.rerun()
            else:
                st.warning("No se aplicó el abono.")