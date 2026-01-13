import streamlit as st
import pandas as pd
from datetime import date

from utils.finance import credit_saldo, apply_customer_payment


def render(tab, db):
    with tab:
        st.subheader("Fiados / Créditos")

        if db["credits"]:
            st.dataframe(pd.DataFrame(db["credits"]), use_container_width=True)
        else:
            st.info("Sin créditos")
