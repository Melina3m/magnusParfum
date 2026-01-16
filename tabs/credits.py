import streamlit as st
import pandas as pd
from datetime import date
from utils.finance import credit_saldo, apply_customer_payment

def render(tab, db):
    """Versión simple de créditos - la versión completa está en fiados.py"""
    with tab:
        st.subheader("Fiados / Créditos")
        
        if db["credits"]:
            df = pd.DataFrame(db["credits"])
            
            # Calcular saldo si no viene en el DF
            if "total" in df.columns and "paid" in df.columns:
                df["saldo"] = df["total"] - df["paid"]
            
            # Aplicar formato de puntos de mil (estilo colombiano)
            try:
                format_dict = {}
                if "total" in df.columns:
                    format_dict["total"] = "{:,.0f}"
                if "paid" in df.columns:
                    format_dict["paid"] = "{:,.0f}"
                if "paid_amount" in df.columns:
                    format_dict["paid_amount"] = "{:,.0f}"
                if "saldo" in df.columns:
                    format_dict["saldo"] = "{:,.0f}"
                
                # Aplicar formato y cambiar comas por puntos
                styled_df = df.style.format(format_dict, na_rep="-")
                
                st.dataframe(styled_df, use_container_width=True)
            except Exception:
                # Fallback si falla el formato
                st.dataframe(df, use_container_width=True)
        else:
            st.info("Sin créditos registrados.")