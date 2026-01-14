import streamlit as st
import pandas as pd
from datetime import date
from collections import defaultdict
from utils import supplier_credit_saldo, apply_supplier_payment, uid, build_receipt_pdf

def render_suppliers(db):
    st.subheader("Deudas con proveedores")

    per_supplier = defaultdict(lambda: {"total": 0.0, "paid": 0.0})
    for c in db.get("supplier_credits", []):
        sup = (c.get("supplier") or "Proveedor").strip()
        per_supplier[sup]["total"] += float(c.get("total", 0))
        per_supplier[sup]["paid"] += float(c.get("paid", 0))

    resumen = []
    for sup, vals in per_supplier.items():
        saldo = vals["total"] - vals["paid"]
        if saldo > 0 or vals["total"] > 0:
            resumen.append({"proveedor": sup, "total": vals["total"], "pagado": vals["paid"], "saldo": saldo})
    
    resumen.sort(key=lambda r: (-r["saldo"], r["proveedor"].lower() if isinstance(r["proveedor"], str) else ""))

    if resumen:
        st.markdown("### Resumen por proveedor")
        df_resumen = pd.DataFrame(resumen)
        
        # --- CORRECCIÓN AQUÍ: Usamos thousands="." y quitamos .replace() ---
        st.dataframe(
            df_resumen.style.format({
                "total": "{:,.0f}",
                "pagado": "{:,.0f}",
                "saldo": "{:,.0f}"
            }, thousands="."), 
            use_container_width=True
        )
    else:
        st.info("No hay deudas con proveedores.")

    st.markdown("---")
    st.markdown("### Registrar pago a proveedor")
    
    if 'pdf_data_sup' not in st.session_state:
        st.session_state.pdf_data_sup = None
    if 'pdf_filename_sup' not in st.session_state:
        st.session_state.pdf_filename_sup = None

    if st.session_state.pdf_data_sup:
        st.success("Abono aplicado. Puedes descargar el recibo.")
        st.download_button(
            "⬇ Descargar recibo (PDF)",
            data=st.session_state.pdf_data_sup,
            file_name=st.session_state.pdf_filename_sup,
            mime="application/pdf"
        )
        st.session_state.pdf_data_sup = None
        st.session_state.pdf_filename_sup = None

    suppliers = sorted(list(per_supplier.keys()))
    if suppliers:
        with st.form("supplier_payment_form", clear_on_submit=True):
            c1, c2, c3 = st.columns([2,1,1])
            sel_supplier = c1.selectbox("Proveedor", options=suppliers, key="sel_prov")
            abono = c2.number_input("Abono", min_value=0.0, step=1000.0, value=0.0, format="%.0f", key="abono_prov")
            fecha_abono = c3.date_input("Fecha", key="fecha_prov", value=date.today())
            
            c4, c5 = st.columns([1,2])
            medio_pago_sup = c4.selectbox("Medio del pago", options=["Efectivo", "Transferencia", "Tarjeta"], key="medio_prov")
            notas_abono = c5.text_input("Notas", key="notas_prov")
            ok = st.form_submit_button("Registrar pago")
            
            if ok:
                monto = float(abono or 0)
                if monto > 0:
                    before = sum(supplier_credit_saldo(c) for c in db["supplier_credits"]
                                if (c.get("supplier","").strip().lower() == sel_supplier.strip().lower()))
                    
                    applied = apply_supplier_payment(db, sel_supplier, monto, fecha_abono.isoformat(), notas_abono, medio_pago_sup)
                    
                    after = sum(supplier_credit_saldo(c) for c in db["supplier_credits"]
                               if (c.get("supplier","").strip().lower() == sel_supplier.strip().lower()))
                    
                    rid = "RP-" + uid()[-8:]
                    # Nota: Aquí se asume que tienes build_receipt_pdf configurado
                    pdf_bytes = build_receipt_pdf(
                        db, who_type="PROVEEDOR", who_name=sel_supplier, receipt_id=rid,
                        date_str=fecha_abono.isoformat(), amount=applied,
                        balance_before=before, balance_after=after,
                        notes=notas_abono, breakdown=[]
                    )
                    
                    st.session_state.pdf_data_sup = pdf_bytes
                    st.session_state.pdf_filename_sup = f"recibo_pago_proveedor_{sel_supplier}_{fecha_abono.isoformat()}.pdf"
                    st.rerun()