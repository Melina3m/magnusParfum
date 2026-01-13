import streamlit as st
import pandas as pd
from datetime import date
from database import insert_record
from utils import uid

def render_investor(db):
    st.subheader("Inversionista")
    
    with st.form("inv_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        idate = c1.date_input("Fecha", value=date.today(), key="idate")
        itype = c2.selectbox("Tipo", options=["Aporte", "Retiro", "Utilidad"], key="itype")
        amount = c3.number_input("Monto", min_value=0.0, step=1000.0, value=0.0, format="%.0f", key="iamount")
        notes = st.text_input("Notas", key="inotes")
        ok = st.form_submit_button("Registrar")
        
        if ok:
            insert_record("investor", {
                "id": uid(), 
                "date": idate.isoformat(), 
                "type": itype,
                "amount": float(amount or 0), 
                "notes": notes
            })
            st.success("Movimiento guardado.")
            st.rerun()
    
    if db["investor"]:
        st.dataframe(pd.DataFrame(db["investor"]), use_container_width=True)
    else:
        st.info("Sin movimientos.")