import streamlit as st
import pandas as pd
from utils import cash_bank_balances, _movements_ledger, cop

def render_cash_bank(db):
    st.subheader("Caja y Bancos")
    
    caja, banco = cash_bank_balances(db)

    c1, c2 = st.columns(2)
    c1.metric("Caja (efectivo) — actual", cop(caja))
    c2.metric("Banco — actual", cop(banco))
    st.caption("Calculado con ventas, abonos de clientes, compras al contado y pagos a proveedores.")

    st.markdown("### Libro diario de movimientos")
    movs = _movements_ledger(db)
    if movs:
        df_movs = pd.DataFrame(movs)
        df_movs = df_movs.sort_values("fecha", ascending=False)
        st.dataframe(df_movs, use_container_width=True)
    else:
        st.info("Aún no hay movimientos.")