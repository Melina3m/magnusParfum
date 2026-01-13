import streamlit as st
import base64
from database import update_settings

def render_settings(db):
    st.subheader("Ajustes de la app")
    
    with st.form("settings_form"):
        currency = st.text_input(
            "Símbolo de moneda", 
            db["settings"].get("currency", "COP"), 
            key="curr_set"
        )
        investor_share = int(st.number_input(
            "% de utilidad para inversionista",
            min_value=0,
            max_value=100,
            step=5,
            value=int(db["settings"].get("investor_share", 50)),
            key="inv_share_set"
        ))

        logo_file = st.file_uploader(
            "Subir logo para recibos (PNG, JPG)", 
            type=["png", "jpg"], 
            key="logo_set"
        )
        
        col1, col2 = st.columns(2)
        delete_logo_button = col1.form_submit_button("Quitar logo actual")
        save_button = col2.form_submit_button("Guardar ajustes")

        if delete_logo_button:
            update_settings({"logo_b64": None})
            st.success("Logo eliminado.")
            st.rerun()
        
        if save_button:
            update_data = {
                "currency": currency,
                "investor_share": investor_share
            }
            if logo_file:
                update_data["logo_b64"] = base64.b64encode(logo_file.getvalue()).decode("utf-8")
            update_settings(update_data)
            st.success("Ajustes guardados.")
            st.rerun()