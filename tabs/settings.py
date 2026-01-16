import streamlit as st
import base64
from database import update_settings

def render_settings(db):
    st.markdown("""
        <div style='margin-bottom: 2rem;'>
            <h2 style='margin: 0; color: #1a1a2e;'>Configuración del Sistema</h2>
            <p style='margin: 0.5rem 0 0 0; color: #636e72;'>
                Personaliza parámetros generales de la aplicación
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    # Vista previa del logo actual
    current_logo = db["settings"].get("logo_b64")
    if current_logo:
        st.markdown("### Logo Actual")
        try:
            logo_data = base64.b64decode(current_logo)
            st.image(logo_data, width=200, caption="Logo en recibos PDF")
        except Exception:
            st.warning("No se pudo cargar el logo actual.")
        st.markdown("<br>", unsafe_allow_html=True)
    
    # Formulario de configuración
    st.markdown("### Parámetros Generales")
    
    with st.form("settings_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Configuración de Moneda")
            currency = st.text_input(
                "Símbolo de moneda", 
                db["settings"].get("currency", "COP"), 
                key="curr_set",
                help="Código de la moneda utilizada (ej: COP, USD, EUR)",
                placeholder="COP"
            )
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("#### Logo para Recibos")
            logo_file = st.file_uploader(
                "Subir logo (PNG, JPG)", 
                type=["png", "jpg", "jpeg"], 
                key="logo_set",
                help="Imagen que aparecerá en los recibos PDF generados"
            )
            
            if logo_file:
                st.image(logo_file, width=200, caption="Vista previa del nuevo logo")
        
        with col2:
            st.markdown("#### Participación del Inversionista")
            investor_share = int(st.number_input(
                "Porcentaje de utilidad para inversionista",
                min_value=0,
                max_value=100,
                step=5,
                value=int(db["settings"].get("investor_share", 50)),
                key="inv_share_set",
                help="Porcentaje de las utilidades que corresponde al inversionista"
            ))
            
            st.markdown(f"""
                <div style='background: linear-gradient(135deg, #d9e8ff, #b3d4ff); 
                            padding: 1rem; border-radius: 10px; margin-top: 1rem;'>
                    <div style='font-size: 0.875rem; color: #0c4a9e; margin-bottom: 0.5rem;'>
                        <strong>DISTRIBUCIÓN DE UTILIDADES</strong>
                    </div>
                    <div style='display: flex; justify-content: space-between; margin-bottom: 0.25rem;'>
                        <span>Inversionista:</span>
                        <strong>{investor_share}%</strong>
                    </div>
                    <div style='display: flex; justify-content: space-between;'>
                        <span>Socio operativo:</span>
                        <strong>{100 - investor_share}%</strong>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("""
                <div style='background: #f8f9fa; padding: 1rem; border-radius: 10px; 
                            border-left: 4px solid #0f3460; font-size: 0.875rem;'>
                    <strong>Nota:</strong> Este porcentaje se aplica únicamente a las ventas 
                    de productos marcados como "INV" (Inversionista) en el inventario.
                </div>
            """, unsafe_allow_html=True)
        
        st.markdown("<hr style='margin: 2rem 0;'>", unsafe_allow_html=True)
        
        # Botones de acción
        col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 1])
        
        with col_btn2:
            delete_logo_button = st.form_submit_button(
                "Eliminar Logo", 
                use_container_width=True,
                help="Quita el logo actual de los recibos"
            )
        
        with col_btn3:
            save_button = st.form_submit_button(
                "Guardar Cambios", 
                use_container_width=True,
                type="primary"
            )

        if delete_logo_button:
            update_settings({"logo_b64": None})
            st.success("Logo eliminado correctamente.")
            st.rerun()
        
        if save_button:
            update_data = {
                "currency": currency,
                "investor_share": investor_share
            }
            
            # Procesar logo si se subió uno nuevo
            if logo_file:
                try:
                    logo_bytes = logo_file.getvalue()
                    logo_b64 = base64.b64encode(logo_bytes).decode("utf-8")
                    update_data["logo_b64"] = logo_b64
                    st.success("Nuevo logo cargado correctamente.")
                except Exception as e:
                    st.error(f"Error al procesar el logo: {e}")
            
            # Guardar configuración
            update_settings(update_data)
            st.success("Configuración guardada exitosamente.")
            st.rerun()
    
    st.markdown("<hr style='margin: 2rem 0;'>", unsafe_allow_html=True)
    
    # Información del sistema
    st.markdown("### Información del Sistema")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
            <div style='background: #f8f9fa; padding: 1.5rem; border-radius: 10px;'>
                <h4 style='margin: 0 0 1rem 0; color: #1a1a2e;'>Magnus Parfum</h4>
                <p style='margin: 0; color: #636e72; font-size: 0.875rem;'>
                    Sistema Integral de Gestión Empresarial
                </p>
                <p style='margin: 0.5rem 0 0 0; color: #636e72; font-size: 0.875rem;'>
                    Versión 2.0
                </p>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        # Estadísticas del sistema
        num_products = len(db.get("inventory", []))
        num_sales = len(db.get("sales", []))
        num_purchases = len(db.get("purchases", []))
        num_credits = len(db.get("credits", []))
        
        st.markdown(f"""
            <div style='background: linear-gradient(135deg, #d9e8ff, #b3d4ff); 
                        padding: 1.5rem; border-radius: 10px;'>
                <h4 style='margin: 0 0 1rem 0; color: #0c4a9e;'>Estadísticas Generales</h4>
                <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; 
                            font-size: 0.875rem; color: #0c4a9e;'>
                    <div><strong>Productos:</strong></div>
                    <div style='text-align: right;'>{num_products}</div>
                    <div><strong>Ventas:</strong></div>
                    <div style='text-align: right;'>{num_sales}</div>
                    <div><strong>Compras:</strong></div>
                    <div style='text-align: right;'>{num_purchases}</div>
                    <div><strong>Créditos:</strong></div>
                    <div style='text-align: right;'>{num_credits}</div>
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Advertencias y recomendaciones
    st.markdown("### Recomendaciones")
    st.markdown("""
        <div style='background: #fff4d9; padding: 1rem; border-radius: 10px; 
                    border-left: 4px solid #ffd166;'>
            <ul style='margin: 0; padding-left: 1.5rem; color: #996c00;'>
                <li>Realiza copias de seguridad periódicas de tu base de datos</li>
                <li>Verifica regularmente los saldos de caja y banco</li>
                <li>Revisa los créditos pendientes frecuentemente</li>
                <li>Mantén actualizado el inventario después de cada operación</li>
                <li>Usa el sistema de reportes para análisis periódico</li>
            </ul>
        </div>
    """, unsafe_allow_html=True)