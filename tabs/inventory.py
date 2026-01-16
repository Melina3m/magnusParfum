import streamlit as st
import pandas as pd
from database import insert_record, update_record, delete_record
from utils import uid, cop

def render_inventory(db):
    st.markdown("""
        <div style='margin-bottom: 2rem;'>
            <h2 style='margin: 0; color: #1a1a2e;'> Gestión de Inventario</h2>
            <p style='margin: 0.5rem 0 0 0; color: #636e72;'>
                Administra tus productos, stock y precios
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    # Formulario con diseño mejorado
    with st.expander("➕ Agregar o actualizar producto", expanded=False):
        with st.form("add_item", clear_on_submit=True):
            st.markdown("#### Información del producto")
            c1, c2, c3, c4 = st.columns([2,1,1,1])
            name = c1.text_input("Nombre del perfume *", placeholder="Ej: Black Afgano")
            brand = c2.text_input("Marca", placeholder="Nasomatto")
            size_ml = c3.number_input("Tamaño (ml)", min_value=0, step=1, value=0)
            stock = c4.number_input("Stock inicial", min_value=0, step=1, value=0)
            
            st.markdown("#### Costos y precios")
            c5, c6 = st.columns(2)
            cost = c5.number_input(" Costo unitario", min_value=0.0, step=1000.0, value=0.0, format="%.0f")
            price = c6.number_input(" Precio de venta", min_value=0.0, step=1000.0, value=0.0, format="%.0f")
            
            # Mostrar margen si hay datos
            if cost > 0 and price > 0:
                margin = ((price - cost) / cost) * 100
                margin_color = "#06d6a0" if margin > 50 else "#ffd93d" if margin > 30 else "#ff6b6b"
                st.markdown(f"""
                    <div style='background: linear-gradient(135deg, #e8f5e9, #c8e6c9); 
                                padding: 1rem; border-radius: 8px; margin: 0.5rem 0;'>
                        <strong style='color: {margin_color};'>📊 Margen de ganancia: {margin:.1f}%</strong>
                        <span style='color: #636e72;'> ({cop(price - cost)} por unidad)</span>
                    </div>
                """, unsafe_allow_html=True)
            
            inv_flag = st.checkbox(" Contar este perfume para inversionista", value=True)
            notes = st.text_area(" Notas (opcional)", placeholder="Información adicional del producto...")
            
            submitted = st.form_submit_button("💾 Guardar producto", use_container_width=True, type="primary")
            
            if submitted:
                if not name.strip():
                    st.error("⚠️ El nombre es obligatorio.")
                else:
                    found = None
                    for p in db["inventory"]:
                        if (p.get("name","").strip().lower() == name.strip().lower()
                            and p.get("brand","").strip().lower() == brand.strip().lower()
                            and int(p.get("size_ml") or 0) == int(size_ml or 0)):
                            found = p
                            break
                    
                    if found:
                        update_record("inventory", {
                            "cost": float(cost), "price": float(price), 
                            "stock": int(stock), "notes": notes, "inv": bool(inv_flag)
                        }, found["id"])
                        st.success("✅ Producto actualizado exitosamente.")
                    else:
                        new_prod = {
                            "id": uid(), "name": name.strip(), "brand": brand.strip(),
                            "size_ml": int(size_ml or 0), "cost": float(cost or 0),
                            "price": float(price or 0), "stock": int(stock or 0),
                            "notes": notes.strip(), "inv": bool(inv_flag)
                        }
                        insert_record("inventory", new_prod)
                        st.success("✅ Producto agregado exitosamente.")
                    
                    st.rerun()

    st.markdown("<hr style='margin: 2rem 0;'>", unsafe_allow_html=True)
    
    # Búsqueda mejorada con métricas
    col_search, col_metrics = st.columns([2,2])
    
    with col_search:
        q = st.text_input(" Buscar productos", "", placeholder="Buscar por nombre o marca...")
    
    with col_metrics:
        total_products = len(db["inventory"])
        total_stock = sum(p.get("stock", 0) for p in db["inventory"])
        total_value = sum(p.get("cost", 0) * p.get("stock", 0) for p in db["inventory"])
        
        mcol1, mcol2 = st.columns(2)
        mcol1.metric("Productos", total_products)
        mcol2.metric("Stock total", total_stock)
    
    # Mostrar valor del inventario
    if db["inventory"]:
        st.markdown(f"""
            <div style='background: linear-gradient(135deg, #fff9e6, #fff3cc); 
                        padding: 1rem; border-radius: 10px; margin: 1rem 0;'>
                <strong> Valor total del inventario:</strong> 
                <span style='font-size: 1.3rem; color: #1a1a2e;'>{cop(total_value)}</span>
            </div>
        """, unsafe_allow_html=True)
    
    # Tabla de inventario
    df_inv = pd.DataFrame(db["inventory"])
    if not df_inv.empty:
        if q:
            mask = df_inv.apply(lambda r: q.lower() in f"{r.get('name','')} {r.get('brand','')}".lower(), axis=1)
            df_inv = df_inv[mask]
        
        if not df_inv.empty:
            # Calcular columnas adicionales
            df_inv['valor_stock'] = df_inv.apply(lambda r: r.get('cost', 0) * r.get('stock', 0), axis=1)
            
            # Formatear para visualización
            df_display = df_inv.copy()
            df_display['Nombre'] = df_display['name']
            df_display['Marca'] = df_display['brand']
            df_display['Tamaño (ml)'] = df_display['size_ml']
            df_display['Stock'] = df_display['stock']
            df_display['Costo'] = df_display['cost'].apply(cop)
            df_display['Precio'] = df_display['price'].apply(cop)
            df_display['Valor Stock'] = df_display['valor_stock'].apply(cop)
            df_display['Inv.'] = df_display['inv'].apply(lambda x: '✅' if x else '❌')
            
            display_cols = ['Nombre', 'Marca', 'Tamaño (ml)', 'Stock', 'Costo', 'Precio', 'Valor Stock', 'Inv.']
            st.dataframe(
                df_display[display_cols].sort_values('Stock', ascending=False), 
                use_container_width=True,
                hide_index=True
            )
            
            # Botón de descarga CSV
            csv = df_inv.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Descargar inventario en CSV",
                data=csv,
                file_name="inventario_magnus.csv",
                mime="text/csv"
            )
        else:
            st.info("No se encontraron productos que coincidan con la búsqueda.")
    else:
        st.info("No hay productos en el inventario. ¡Agrega el primero usando el formulario de arriba!")

    # Ajustes rápidos de stock con diseño mejorado
    if db["inventory"]:
        st.markdown("<hr style='margin: 2rem 0;'>", unsafe_allow_html=True)
        st.markdown("###  Ajustes rápidos de stock")
        st.caption("Incrementa o reduce el stock de tus productos rápidamente")
        
        # Filtrar productos con stock bajo
        low_stock = [p for p in db["inventory"] if p.get("stock", 0) < 5]
        if low_stock:
            st.warning(f"⚠️ {len(low_stock)} producto(s) con stock bajo (menos de 5 unidades)")
        
        # Ordenar productos por stock (los de menor stock primero)
        sorted_products = sorted(db["inventory"], key=lambda x: x.get("stock", 0))
        
        for idx, p in enumerate(sorted_products):
            with st.container():
                c1, c2, c3, c4, c5, c6 = st.columns([3,1,1,1,1,1])
                
                # Indicador de stock
                stock_val = p.get('stock', 0)
                stock_icon = "🔴" if stock_val < 5 else "🟡" if stock_val < 10 else "🟢"
                
                c1.markdown(f"{stock_icon} **{p['name']}**")
                c1.caption(f"{p.get('brand','')} • {p.get('size_ml','')} ml • PVP: {cop(p.get('price', 0))}")
                
                c2.metric("Stock", stock_val, delta=None, delta_color="off")
                
                if c3.button("", key=f"plus_{p['id']}", help="Incrementar stock"):
                    update_record("inventory", {"stock": int(p.get("stock", 0)) + 1}, p["id"])
                    st.rerun()
                    
                if c4.button("", key=f"minus_{p['id']}", help="Reducir stock"):
                    update_record("inventory", {"stock": max(0, int(p.get("stock", 0)) - 1)}, p["id"])
                    st.rerun()
                
                if c5.button("", key=f"edit_{p['id']}", help="Editar producto"):
                    st.info(" Usa el formulario superior para editar el producto")
                    
                if c6.button("", key=f"del_{p['id']}", help="Eliminar producto"):
                    if st.session_state.get(f"confirm_del_{p['id']}", False):
                        delete_record("inventory", p["id"])
                        st.rerun()
                    else:
                        st.session_state[f"confirm_del_{p['id']}"] = True
                        st.warning(" Presiona de nuevo para confirmar eliminación")
                
                if idx < len(sorted_products) - 1:
                    st.markdown("<hr style='margin: 0.5rem 0; opacity: 0.2;'>", unsafe_allow_html=True)