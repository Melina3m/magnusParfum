import streamlit as st
from st_supabase_connection import SupabaseConnection

def init_connection():
    """Establece la conexión buscando llaves en Hugging Face o en local."""
    try:
        # 1. Intentar leer desde los Secretos de Hugging Face (Prioridad)
        url = st.secrets.get("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_KEY")

        # 2. Si no existen (porque estás en tu PC), buscarlos en la estructura local
        if not url:
            try:
                url = st.secrets["connections"]["supabase"]["url"]
                key = st.secrets["connections"]["supabase"]["key"]
            except:
                st.error("❌ No se encontraron las llaves de Supabase. Configura los 'Secrets' en Hugging Face.")
                st.stop()

        return st.connection(
            "supabase",
            type=SupabaseConnection,
            url=url,
            key=key
        )
    except Exception as e:
        st.error(f"Error de configuración: {e}")
        st.stop()

def load_full_db():
    """Carga COMPLETA de la base de datos"""
    conn = init_connection()
    
    db = {
        "settings": {
            "currency": "COP",
            "investor_share": 50,
            "logo_b64": None,
            "gsheets_sheet_id": "",
            "gsheets_sync": False
        },
        "inventory": [], "purchases": [], "sales": [],
        "credits": [], "investor": [], "credit_payments": [],
        "supplier_credits": [], "supplier_payments": []
    }
    
    try:
        # Carga de tablas
        db["settings_data"] = conn.table("settings").select("*").eq("id", "main").limit(1).execute().data
        if db["settings_data"]:
            db["settings"].update(db["settings_data"][0])
            
        db["inventory"] = conn.table("inventory").select("*").order("name").execute().data or []
        db["purchases"] = conn.table("purchases").select("*").order("date", desc=True).execute().data or []
        db["sales"] = conn.table("sales").select("*").order("date", desc=True).execute().data or []
        db["credits"] = conn.table("credits").select("*").order("date", desc=True).execute().data or []
        db["investor"] = conn.table("investor").select("*").order("date", desc=True).execute().data or []
        db["credit_payments"] = conn.table("credit_payments").select("*").order("date", desc=True).execute().data or []
        db["supplier_credits"] = conn.table("supplier_credits").select("*").order("date", desc=True).execute().data or []
        db["supplier_payments"] = conn.table("supplier_payments").select("*").order("date", desc=True).execute().data or []
        
    except Exception as e:
        st.error(f"Error cargando tablas: {e}")
    
    return db

def insert_record(table, data):
    try:
        conn = init_connection()
        return conn.table(table).insert(data).execute()
    except Exception as e:
        st.error(f"Error al insertar en {table}: {e}")

def update_record(table, data, record_id):
    try:
        conn = init_connection()
        return conn.table(table).update(data).eq("id", record_id).execute()
    except Exception as e:
        st.error(f"Error al actualizar {table}: {e}")

def delete_record(table, record_id):
    try:
        conn = init_connection()
        return conn.table(table).delete().eq("id", record_id).execute()
    except Exception as e:
        st.error(f"Error al eliminar de {table}: {e}")

def update_settings(data):
    try:
        conn = init_connection()
        return conn.table("settings").update(data).eq("id", "main").execute()
    except Exception as e:
        st.error(f"Error al actualizar settings: {e}")

def save_db_sync(db):
    pass