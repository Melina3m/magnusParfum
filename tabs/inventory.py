import streamlit as st
import pandas as pd
from database import insert_record, update_record, delete_record
from utils import uid, cop

def render_inventory(db):
    st.markdown("### Gestión de Inventario")
    st.caption("Administra tus productos, stock y precios")
    
    # Formulario con diseño mejorado
    with st.expander("Agregar o actualizar producto", expanded=False):
        with st.form("add_item", clear_on_submit=True):
            st.markdown("#### Información del producto")
            c1, c2, c3, c4 = st.columns([2,1,1,1])
            name = c1.text_input("Nombre del perfume *", placeholder="Ej: Black Afgano")
            brand = c2.text_input("Marca", placeholder="Nasomatto")
            size_ml = c3.number_input("Tamaño (ml)", min_value=0, step=1, value=0)
            stock = c4.number_input("Stock inicial", min_value=0, step=1, value=0)
            
            st.markdown("#### Costos y precios")
            c5, c6 = st.columns(2)
            cost = c5.number_input("Costo unitario", min_value=0.0, step=1000.0, value=0.0, format="%.0f")
            price = c6.number_input("Precio de venta", min_value=0.0, step=1000.0, value=0.0, format="%.0f")
            
            # Mostrar margen si hay datos
            if cost > 0 and price > 0:
                margin = ((price - cost) / cost) * 100
                margin_color = "🟢" if margin > 50 else "🟡" if margin > 30 else "🔴"
                st.info(f"{margin_color} Margen de ganancia: **{margin:.1f}%** ({cop(price - cost)} por unidad)")
            
            inv_flag = st.checkbox("Contar este perfume para inversionista", value=True)
            notes = st.text_area("Notas (opcional)", placeholder="Información adicional del producto...")
            
            submitted = st.form_submit_button("Guardar producto", use_container_width=True)
            
            if submitted:
                if not name.strip():
                    st.error("El nombre es obligatorio.")
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
                        st.success("Producto actualizado exitosamente.")
                    else:
                        new_prod = {
                            "id": uid(), "name": name.strip(), "brand": brand.strip(),
                            "size_ml": int(size_ml or 0), "cost": float(cost or 0),
                            "price": float(price or 0), "stock": int(stock or 0),
                            "notes": notes.strip(), "inv": bool(inv_flag)
                        }
                        insert_record("inventory", new_prod)
                        st.success("Producto agregado exitosamente.")
                    
                    st.rerun()

    st.markdown("---")
    
    # Búsqueda mejorada
    col_search, col_total = st.columns([3,1])
    with col_search:
        q = st.text_input("Buscar productos", "", placeholder="Buscar por nombre o marca...")
    with col_total:
        total_products = len(db["inventory"])
        total_stock = sum(p.get("stock", 0) for p in db["inventory"])
        st.metric("Total productos", f"{total_products} ({total_stock} und.)")
    
    # Tabla de inventario
    df_inv = pd.DataFrame(db["inventory"])
    if not df_inv.empty:
        if q:
            mask = df_inv.apply(lambda r: q.lower() in f"{r.get('name','')} {r.get('brand','')}".lower(), axis=1)
            df_inv = df_inv[mask]
        
        # Calcular valor total del inventario
        if not df_inv.empty:
            df_inv['valor_stock'] = df_inv.apply(lambda r: r.get('cost', 0) * r.get('stock', 0), axis=1)
            valor_total = df_inv['valor_stock'].sum()
            
            st.markdown(f"**Valor total del inventario:** {cop(valor_total)}")
            
            # Reordenar columnas para mejor visualización
            display_cols = ['name', 'brand', 'size_ml', 'stock', 'cost', 'price', 'valor_stock', 'inv']
            available_cols = [col for col in display_cols if col in df_inv.columns]
            st.dataframe(
                df_inv[available_cols].sort_values('stock', ascending=False), 
                use_container_width=True,
                hide_index=True
            )
    else:
        st.info("No hay productos en el inventario. ¡Agrega el primero!")

    # Ajustes rápidos de stock con diseño mejorado
    if db["inventory"]:
        st.markdown("---")
        st.markdown("### Ajustes rápidos de stock")
        st.caption("Incrementa o reduce el stock de tus productos rápidamente")
        
        # Filtrar productos con stock bajo
        low_stock = [p for p in db["inventory"] if p.get("stock", 0) < 5]
        if low_stock:
            st.warning(f"⚠️ {len(low_stock)} producto(s) con stock bajo (menos de 5 unidades)")
        
        for idx, p in enumerate(db["inventory"]):
            with st.container():
                c1, c2, c3, c4, c5, c6 = st.columns([3,1,1,1,1,1])
                
                # Indicador de stock
                stock_val = p.get('stock', 0)
                stock_icon = "🔴" if stock_val < 5 else "🟡" if stock_val < 10 else "🟢"
                
                c1.markdown(f"{stock_icon} **{p['name']}**")
                c1.caption(f"{p.get('brand','')} • {p.get('size_ml','')} ml • {cop(p.get('price', 0))}")
                
                c2.metric("Stock", stock_val, delta=None, delta_color="off")
                
                if c3.button("➕", key=f"plus_{p['id']}", help="Incrementar stock"):
                    update_record("inventory", {"stock": int(p.get("stock", 0)) + 1}, p["id"])
                    st.rerun()
                    
                if c4.button("➖", key=f"minus_{p['id']}", help="Reducir stock"):
                    update_record("inventory", {"stock": max(0, int(p.get("stock", 0)) - 1)}, p["id"])
                    st.rerun()
                
                if c5.button("✏️", key=f"edit_{p['id']}", help="Editar producto"):
                    st.info("Usa el formulario superior para editar el producto")
                    
                if c6.button("🗑️", key=f"del_{p['id']}", help="Eliminar producto"):
                    delete_record("inventory", p["id"])
                    st.rerun()
                
                if idx < len(db["inventory"]) - 1:
                    st.divider()