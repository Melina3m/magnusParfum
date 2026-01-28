import streamlit as st
import pandas as pd
from datetime import date
from collections import defaultdict
from utils import credit_saldo, apply_customer_payment, uid, build_receipt_pdf, cop

def render_fiados(db):
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
            <h2 style='margin: 0; color: #1a1a2e;'>Créditos a Clientes</h2>
            <p style='margin: 0.5rem 0 0 0; color: #636e72;'>
                Gestión de cuentas por cobrar y abonos de clientes
            </p>
        </div>
    """, unsafe_allow_html=True)

    # Calcular resumen por cliente
    per_customer = defaultdict(lambda: {"total": 0.0, "paid": 0.0})
    for c in db["credits"]:
        cust = (c.get("customer") or "Cliente").strip()
        per_customer[cust]["total"] += float(c.get("total", 0))
        per_customer[cust]["paid"] += float(c.get("paid", 0))

    resumen = []
    for cust, vals in per_customer.items():
        saldo = vals["total"] - vals["paid"]
        if saldo > 0 or vals["total"] > 0:
            resumen.append({
                "cliente": cust, 
                "total": vals["total"], 
                "pagado": vals["paid"], 
                "saldo": saldo
            })
    resumen.sort(key=lambda r: (-r["saldo"], r["cliente"].lower() if isinstance(r["cliente"], str) else ""))

    # Mostrar resumen
    if resumen:
        st.markdown("### Resumen por Cliente")
        
        total_credito = sum(r["total"] for r in resumen)
        total_pagado = sum(r["pagado"] for r in resumen)
        total_pendiente = sum(r["saldo"] for r in resumen)
        clientes_con_deuda = sum(1 for r in resumen if r["saldo"] > 0)
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
                <div class="card-metric">
                    <div class="card-title">Crédito Total</div>
                    <div class="card-value">{cop(total_credito)}</div>
                    <div class="card-note">Suma de todas las ventas a crédito</div>
                </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
                <div class="card-metric" style="background: linear-gradient(135deg, #d4f1e8, #b8e6d5);">
                    <div class="card-title">Pagado</div>
                    <div class="card-value">{cop(total_pagado)}</div>
                    <div class="card-note">Total de abonos recibidos</div>
                </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
                <div class="card-metric" style="background: linear-gradient(135deg, #fff4d9, #ffe9b3);">
                    <div class="card-title">Pendiente</div>
                    <div class="card-value">{cop(total_pendiente)}</div>
                    <div class="card-note">Saldo por cobrar</div>
                </div>
            """, unsafe_allow_html=True)
        
        with col4:
            st.markdown(f"""
                <div class="card-metric" style="background: linear-gradient(135deg, #ffd9e0, #ffb3c1);">
                    <div class="card-title">Clientes</div>
                    <div class="card-value">{clientes_con_deuda}</div>
                    <div class="card-note">Con saldo pendiente</div>
                </div>
            """, unsafe_allow_html=True)
        
        df_resumen = pd.DataFrame(resumen)
        df_resumen["total"] = df_resumen["total"].apply(cop)
        df_resumen["pagado"] = df_resumen["pagado"].apply(cop)
        df_resumen["saldo"] = df_resumen["saldo"].apply(cop)
        df_resumen.columns = ["Cliente", "Total Crédito", "Total Pagado", "Saldo Pendiente"]
        st.dataframe(df_resumen, use_container_width=True, hide_index=True)
    else:
        st.info("No hay créditos registrados.")

    st.markdown("<hr>", unsafe_allow_html=True)

    # ------------------ REIMPRIMIR RECIBOS ------------------
    st.markdown("### Reimprimir Recibos Anteriores")
    st.caption("Genera nuevamente el recibo de cualquier abono pasado")
    
    if db.get("credit_payments"):
        abonos_por_cliente = defaultdict(list)
        for payment in db["credit_payments"]:
            cliente = payment.get("customer", "Cliente").strip()
            abonos_por_cliente[cliente].append(payment)
        
        clientes_con_abonos = sorted(list(abonos_por_cliente.keys()))
        
        if clientes_con_abonos:
            col_reimp1, col_reimp2 = st.columns([2, 1])
            
            with col_reimp1:
                cliente_reimprimir = st.selectbox(
                    "Cliente",
                    options=clientes_con_abonos,
                    key="cliente_reimprimir"
                )
            
            abonos_cliente = sorted(
                abonos_por_cliente[cliente_reimprimir],
                key=lambda x: x.get("date", ""),
                reverse=True
            )
            
            with col_reimp2:
                opciones_abonos = []
                for abono in abonos_cliente:
                    fecha = abono.get("date", "")[:10]
                    monto = cop(abono.get("amount", 0))
                    medio = abono.get("method", "N/A")
                    opciones_abonos.append(f"{fecha} - {monto} ({medio})")
                
                abono_seleccionado_idx = st.selectbox(
                    "Abono",
                    options=range(len(opciones_abonos)),
                    format_func=lambda i: opciones_abonos[i],
                    key="abono_reimprimir"
                )
            
            if st.button("Generar Recibo", use_container_width=True, key="btn_reimprimir"):
                abono_seleccionado = abonos_cliente[abono_seleccionado_idx]

                monto_abono = float(abono_seleccionado.get("amount", 0))
                fecha_objetivo = abono_seleccionado.get("date", "")

                saldo_actual = sum(
                    credit_saldo(c) for c in db["credits"]
                    if c.get("customer","").strip().lower() == cliente_reimprimir.strip().lower()
                )

                abonos_posteriores = sum(
                    float(p.get("amount", 0))
                    for p in db["credit_payments"]
                    if (p.get("customer","").strip().lower() == cliente_reimprimir.strip().lower())
                    and p.get("date","") > fecha_objetivo
                )

                saldo_despues = saldo_actual + abonos_posteriores
                saldo_antes = saldo_despues + monto_abono

                snapshot = [
                    {"id": c["id"], "date": c.get("date",""), 
                     "applied": min(credit_saldo(c), monto_abono),
                     "remaining": credit_saldo(c)}
                    for c in db["credits"]
                    if (c.get("customer","").strip().lower() == cliente_reimprimir.strip().lower())
                    and credit_saldo(c) > 0
                ]

                rid = "RC-" + abono_seleccionado.get("id", uid())[-8:]
                pdf_bytes = build_receipt_pdf(
                    db, 
                    who_type="CLIENTE", 
                    who_name=cliente_reimprimir, 
                    receipt_id=rid,
                    date_str=abono_seleccionado.get("date", ""),
                    amount=monto_abono,
                    balance_before=saldo_antes,
                    balance_after=saldo_despues,
                    notes=abono_seleccionado.get("notes", ""),
                    breakdown=snapshot
                )
                
                st.download_button(
                    "⬇️ Descargar Recibo Reimpreso",
                    data=pdf_bytes,
                    file_name=f"recibo_reimpreso_{cliente_reimprimir}_{fecha_objetivo}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
        else:
            st.info("No hay abonos registrados.")
    else:
        st.info("No hay abonos registrados.")

    st.markdown("<hr>", unsafe_allow_html=True)

    # ------------------ REGISTRAR ABONO ------------------
    st.markdown("### Registrar Abono de Cliente")

    clientes = sorted(list(per_customer.keys()))
    if clientes:
        sel_customer = st.selectbox("Selecciona el cliente", clientes)
        saldo_actual = per_customer[sel_customer]["total"] - per_customer[sel_customer]["paid"]
        st.write("Saldo actual:", cop(saldo_actual))

        with st.form("form_abono_cliente"):
            abono = st.number_input("Monto del abono", min_value=0.0, step=1000.0, format="%.0f")
            fecha_abono = st.date_input("Fecha", value=date.today())
            medio_abono = st.selectbox("Forma de pago", ["Efectivo", "Transferencia", "Tarjeta"])
            notas_abono = st.text_input("Notas")

            ok = st.form_submit_button("Registrar Abono")

        if ok and abono > 0:
            before = sum(credit_saldo(c) for c in db["credits"]
                         if c.get("customer","").strip().lower() == sel_customer.strip().lower())

            snapshot = [
                {"id": c["id"], "date": c.get("date",""), "saldo": credit_saldo(c)}
                for c in db["credits"]
                if (c.get("customer","").strip().lower() == sel_customer.strip().lower()) 
                and credit_saldo(c) > 0
            ]

            applied = apply_customer_payment(
                db, sel_customer, abono, fecha_abono.isoformat(), notas_abono, medio_abono
            )

            after = sum(credit_saldo(c) for c in db["credits"]
                        if c.get("customer","").strip().lower() == sel_customer.strip().lower())

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

            st.download_button(
                "Descargar recibo",
                data=pdf_bytes,
                file_name=f"recibo_abono_cliente_{sel_customer}_{fecha_abono.isoformat()}.pdf",
                mime="application/pdf"
            )
