import streamlit as st
import pandas as pd
from datetime import date
from utils.finance import credit_saldo, apply_customer_payment

def render(tab, db):
    with tab:
        st.subheader("Fiados / Créditos")
        if db["credits"]:
            df = pd.DataFrame(db["credits"])
            
            # Calculamos el saldo visualmente si no viene en el DF
            if "total" in df.columns and "paid" in df.columns:
                df["saldo"] = df["total"] - df["paid"]
            
            # Aplicamos el formato de puntos de mil
            st.dataframe(
                df.style.format({
                    "total": "{:,.0f}",
                    "paid": "{:,.0f}",
                    "paid_amount": "{:,.0f}",
                    "saldo": "{:,.0f}"
                }, na_rep="-").replace(",", "."), 
                use_container_width=True
            )
        else:
            st.info("Sin créditos")