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
                st.error("❌ No se encontraron las llaves de Supabase. Configura los 'Secrets' en Hugging Face o el archivo secrets.toml local.")
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
        "inventory": [],
        "purchases": [],
        "sales": [],
        "credits": [],
        "investor": [],
        "credit_payments": [],
        "supplier_credits": [],
        "supplier_payments": []
    }
    
    try:
        # Settings
        try:
            settings_data = conn.table("settings").select("*").eq("id", "main").limit(1).execute().data
            if settings_data and len(settings_data) > 0:
                db["settings"].update(settings_data[0])
        except Exception as e:
            st.warning(f"⚠️ Tabla 'settings' no encontrada. Error: {e}")
        
        # Inventario - ordenado por nombre para Hugging Face, o por created_at si existe
        try:
            db["inventory"] = conn.table("inventory").select("*").order("created_at", desc=True).execute().data or []
        except:
            # Fallback si no existe created_at
            db["inventory"] = conn.table("inventory").select("*").order("name").execute().data or []
        
        # Compras
        db["purchases"] = conn.table("purchases").select("*").order("date", desc=True).execute().data or []
        
        # Ventas
        db["sales"] = conn.table("sales").select("*").order("date", desc=True).execute().data or []
        
        # Créditos (fiados de clientes)
        db["credits"] = conn.table("credits").select("*").order("date", desc=True).execute().data or []
        
        # Movimientos del inversionista
        db["investor"] = conn.table("investor").select("*").order("date", desc=True).execute().data or []
        
        # Abonos de clientes
        db["credit_payments"] = conn.table("credit_payments").select("*").order("date", desc=True).execute().data or []
        
        # Deudas con proveedores
        db["supplier_credits"] = conn.table("supplier_credits").select("*").order("date", desc=True).execute().data or []
        
        # Pagos a proveedores
        db["supplier_payments"] = conn.table("supplier_payments").select("*").order("date", desc=True).execute().data or []
        
    except Exception as e:
        st.error(f"❌ Error crítico al cargar datos: {e}")
        st.info("Verifica que todas las tablas estén creadas con el esquema SQL proporcionado.")
    
    return db

def insert_record(table, data):
    """Inserta un nuevo registro en la tabla especificada."""
    try:
        conn = init_connection()
        result = conn.table(table).insert(data).execute()
        return result
    except Exception as e:
        st.error(f"Error al insertar en {table}: {e}")
        return None

def update_record(table, data, record_id):
    """Actualiza un registro existente buscando por su ID."""
    try:
        conn = init_connection()
        result = conn.table(table).update(data).eq("id", record_id).execute()
        return result
    except Exception as e:
        st.error(f"Error al actualizar {table}: {e}")
        return None

def delete_record(table, record_id):
    """Elimina un registro por su ID."""
    try:
        conn = init_connection()
        result = conn.table(table).delete().eq("id", record_id).execute()
        return result
    except Exception as e:
        st.error(f"Error al eliminar de {table}: {e}")
        return None

def update_settings(data):
    """Actualiza la configuración (settings)"""
    try:
        conn = init_connection()
        result = conn.table("settings").update(data).eq("id", "main").execute()
        return result
    except Exception as e:
        st.error(f"Error al actualizar settings: {e}")
        return None

def save_db_sync(db):
    """
    Esta función NO hace nada porque Supabase guarda automáticamente.
    La incluyo para mantener compatibilidad con tu código original.
    """
    pass