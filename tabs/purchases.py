import streamlit as st
import pandas as pd
from datetime import date
from database import insert_record, update_record
from utils import uid, cop

def render_purchases(db):
    st.markdown("""
        <div style='margin-bottom: 2rem;'>
            <h2 style='margin: 0; color: #1a1a2e;'>Gestión de Compras</h2>
            <p style='margin: 0.5rem 0 0 0; color: #636e72;'>
                Registro de entradas de inventario y gastos operativos
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    # Selector de tipo de compra
    st.markdown("### Tipo de Transacción")
    compra_tipo = st.radio(
        "Selecciona el tipo de compra",
        ["Añadir al inventario (perfumes para vender)", "Gasto operativo (no afecta stock)"],
        label_visibility="collapsed"
    )

    # --- COMPRAS DE INVENTARIO ---
    if compra_tipo == "Añadir al inventario (perfumes para vender)":
        st.markdown("### Compra de Inventario")
        
        inv_options = [f"{p['name']} — {p.get('brand','')}" for p in db["inventory"]]
        opcion = st.selectbox(
            "Producto del inventario", 
            options=["(Crear nuevo producto)"] + inv_options,
            help="Selecciona un producto existente o crea uno nuevo"
        )
        
        creando_nuevo = (opcion == "(Crear nuevo producto)")
        
        if creando_nuevo:
            st.markdown("#### Datos del Nuevo Producto")
            c0, c1, c2, c3 = st.columns([2,1,1,1])
            new_name = c0.text_input("Nombre del perfume *", key="new_name_comp", placeholder="Ej: Aventus")
            new_brand = c1.text_input("Marca", key="new_brand_comp", placeholder="Ej: Creed")
            new_size = c2.number_input("Tamaño (ml)", min_value=0, step=1, value=0, key="new_size_comp")
            new_price = c3.number_input("Precio venta sugerido", min_value=0.0, step=1000.0, value=0.0, format="%.0f", key="new_price_comp")
        else:
            selected_index = inv_options.index(opcion)
            prod_sel = db["inventory"][selected_index]
            st.markdown(f"""
                <div style='background: linear-gradient(135deg, #d9e8ff, #b3d4ff); 
                            padding: 1rem; border-radius: 10px; margin-bottom: 1rem;'>
                    Producto seleccionado: <strong>{prod_sel['name']}</strong> — 
                    {prod_sel.get('brand','')} ({prod_sel.get('size_ml',0)} ml) | 
                    Stock actual: <strong>{prod_sel.get('stock', 0)}</strong>
                </div>
            """, unsafe_allow_html=True)

        with st.form("purchase_form_inv", clear_on_submit=True):
            st.markdown("#### Detalles de la Compra")
            
            c1, c2, c3 = st.columns(3)
            quantity = c1.number_input("Cantidad", min_value=1, step=1, value=1, key="qty_inv")
            unit_cost = c2.number_input("Costo unitario", min_value=0.0, step=1000.0, value=0.0, format="%.0f", key="uc_inv")
            supplier = c3.text_input("Proveedor (opcional)", key="sup_inv", placeholder="Nombre del proveedor")
            
            d1, d2, d3 = st.columns(3)
            pdate = d1.date_input("Fecha de compra", value=date.today(), key="pdate_inv")
            pago = d2.selectbox("Forma de pago", options=["Contado", "Crédito proveedor"], key="pago_inv")
            invoice = d3.text_input("N° factura/nota", key="invoice_inv", placeholder="Opcional")
            
            due = None
            medio_contado = None
            
            if pago == "Crédito proveedor":
                st.markdown("#### Información del Crédito")
                e1, e2 = st.columns(2)
                due = e1.date_input("Fecha de vencimiento", value=date.today(), key="due_inv")
                notes = e2.text_input("Notas", key="notes_inv", placeholder="Observaciones adicionales")
            else:
                st.markdown("#### Información del Pago")
                e1, e2 = st.columns(2)
                medio_contado = e1.selectbox("Medio de pago", options=["Efectivo", "Transferencia", "Tarjeta"], key="medio_inv")
                notes = e2.text_input("Notas", key="notes_inv2", placeholder="Observaciones adicionales")
            
            # Resumen
            if quantity and unit_cost:
                total_compra = quantity * unit_cost
                st.markdown(f"""
                    <div style='background: linear-gradient(135deg, #fff4d9, #ffe9b3); 
                                padding: 1.25rem; border-radius: 10px; margin-top: 1rem;'>
                        <div style='font-size: 0.875rem; color: #996c00; margin-bottom: 0.5rem;'>
                            <strong>RESUMEN DE LA COMPRA</strong>
                        </div>
                        <div style='display: flex; justify-content: space-between; font-size: 1.1rem;'>
                            <span>Total a pagar:</span>
                            <strong style='color: #996c00;'>{cop(total_compra)}</strong>
                        </div>
                        <div style='font-size: 0.85rem; color: #996c00; margin-top: 0.5rem;'>
                            {quantity} unidades × {cop(unit_cost)} c/u
                        </div>
                    </div>
                """, unsafe_allow_html=True)
            
            ok = st.form_submit_button("Registrar Compra", use_container_width=True, type="primary")
        
        if ok:
            if creando_nuevo:
                if not new_name.strip():
                    st.error("El nombre del producto es obligatorio.")
                    st.stop()
                new_prod = {
                    "id": uid(), "name": new_name.strip(), "brand": new_brand.strip(),
                    "size_ml": int(new_size or 0), "cost": float(unit_cost or 0),
                    "price": float(new_price or 0), "stock": 0, "notes": "", "inv": True
                }
                insert_record("inventory", new_prod)
                prod = new_prod
                db["inventory"].insert(0, new_prod)
            else:
                prod = db["inventory"][selected_index]
            
            purchase_id = uid()
            purchase = {
                "id": purchase_id, "date": pdate.isoformat(), "item_id": prod["id"],
                "quantity": int(quantity), "unit_cost": float(unit_cost or 0),
                "supplier": supplier.strip(), "notes": notes.strip(), "invoice": invoice.strip()
            }
            if pago == "Contado":
                purchase["cash_method"] = medio_contado
            
            insert_record("purchases", purchase)
            
            # Actualizar stock y costo
            new_stock = int(prod.get("stock", 0)) + int(quantity)
            update_data = {"stock": new_stock}
            if float(unit_cost or 0) > 0:
                update_data["cost"] = float(unit_cost)
            update_record("inventory", update_data, prod["id"])
            
            # Crear crédito si es necesario
            if pago == "Crédito proveedor":
                if not supplier.strip():
                    st.error("Para crédito proveedor debes indicar el nombre del proveedor.")
                    st.stop()
                total = int(quantity) * float(unit_cost or 0)
                insert_record("supplier_credits", {
                    "id": uid(), "supplier": supplier.strip(), "date": pdate.isoformat(),
                    "purchase_id": purchase_id, "invoice": invoice.strip(),
                    "total": float(total), "paid": 0.0,
                    "due_date": due.isoformat() if due else None, "notes": notes.strip()
                })
            
            st.success("Compra registrada exitosamente. Inventario actualizado.")
            st.rerun()
    
    # --- GASTOS OPERATIVOS ---
    else:
        st.markdown("### Gasto Operativo")
        
        with st.form("purchase_form_gasto", clear_on_submit=True):
            c1, c2 = st.columns(2)
            pdate = c1.date_input("Fecha del gasto", value=date.today(), key="pdate_gasto")
            categoria = c2.text_input("Categoría del gasto", key="cat_gasto", placeholder="Ej: Publicidad, Transporte, etc.")
            
            c3, c4 = st.columns(2)
            total_gasto = c3.number_input("Monto del gasto", min_value=0.0, step=1000.0, value=0.0, format="%.0f", key="total_gasto")
            supplier = c4.text_input("Proveedor/Beneficiario", key="sup_gasto", placeholder="Nombre del proveedor")
            
            d1, d2, d3 = st.columns(3)
            pago = d1.selectbox("Forma de pago", options=["Contado", "Crédito proveedor"], key="pago_gasto")
            medio_gasto = None
            if pago == "Contado":
                medio_gasto = d2.selectbox("Medio de pago", options=["Efectivo", "Transferencia", "Tarjeta"], key="medio_gasto")
            invoice = d3.text_input("N° factura", key="invoice_gasto", placeholder="Opcional")
            
            notes = st.text_area("Descripción del gasto", key="notes_gasto", placeholder="Detalle sobre este gasto...", height=80)
            
            due = None
            if pago == "Crédito proveedor":
                st.markdown("#### Información del Crédito")
                e1, _ = st.columns([1,3])
                due = e1.date_input("Fecha de vencimiento", value=date.today(), key="due_gasto")
            
            # Resumen
            if total_gasto > 0:
                st.markdown(f"""
                    <div style='background: linear-gradient(135deg, #ffd9e0, #ffb3c1); 
                                padding: 1.25rem; border-radius: 10px; margin-top: 1rem;'>
                        <div style='font-size: 0.875rem; color: #c4183c; margin-bottom: 0.5rem;'>
                            <strong>RESUMEN DEL GASTO</strong>
                        </div>
                        <div style='display: flex; justify-content: space-between; font-size: 1.1rem;'>
                            <span>Total del gasto:</span>
                            <strong style='color: #c4183c;'>{cop(total_gasto)}</strong>
                        </div>
                        <div style='font-size: 0.85rem; color: #c4183c; margin-top: 0.5rem;'>
                            Categoría: {categoria if categoria else 'Sin especificar'}
                        </div>
                    </div>
                """, unsafe_allow_html=True)
            
            ok2 = st.form_submit_button("Registrar Gasto", use_container_width=True, type="primary")
        
        if ok2:
            purchase_id = uid()
            purchase = {
                "id": purchase_id, "date": pdate.isoformat(), "item_id": "",
                "quantity": 1, "unit_cost": float(total_gasto or 0),
                "supplier": supplier.strip(),
                "notes": (categoria.strip() + " — " if categoria else "") + notes.strip(),
                "invoice": invoice.strip()
            }
            if pago == "Contado":
                purchase["cash_method"] = medio_gasto
            
            insert_record("purchases", purchase)
            
            if pago == "Crédito proveedor":
                if not supplier.strip():
                    st.error("Para crédito proveedor debes indicar el nombre del proveedor.")
                    st.stop()
                insert_record("supplier_credits", {
                    "id": uid(), "supplier": supplier.strip(), "date": pdate.isoformat(),
                    "purchase_id": purchase_id, "invoice": invoice.strip(),
                    "total": float(total_gasto or 0), "paid": 0.0,
                    "due_date": due.isoformat() if due else None,
                    "notes": (categoria.strip() + " — " if categoria else "") + notes.strip()
                })
            
            st.success("Gasto operativo registrado correctamente.")
            st.rerun()
    
    st.markdown("<hr style='margin: 2rem 0;'>", unsafe_allow_html=True)
    
    # Historial
    st.markdown("### Historial de Compras y Gastos")
    
    if db["purchases"]:
        df_purchases = pd.DataFrame(db["purchases"])
        
        # Preparar datos para visualización
        df_display = []
        for _, purchase in df_purchases.iterrows():
            item_id = purchase.get("item_id", "")
            
            if item_id:
                # Es una compra de inventario
                prod = next((p for p in db["inventory"] if p["id"] == item_id), None)
                tipo = "Inventario"
                descripcion = prod.get("name", "Producto eliminado") if prod else "Producto eliminado"
            else:
                # Es un gasto operativo
                tipo = "Gasto"
                descripcion = purchase.get("notes", "Sin descripción")[:50]
            
            total = purchase.get("quantity", 1) * purchase.get("unit_cost", 0)
            
            df_display.append({
                "Fecha": purchase.get("date", ""),
                "Tipo": tipo,
                "Descripción": descripcion,
                "Proveedor": purchase.get("supplier", "N/A") or "N/A",
                "Cantidad": purchase.get("quantity", 1),
                "Costo Unit.": cop(purchase.get("unit_cost", 0)),
                "Total": cop(total),
                "Pago": purchase.get("cash_method", "Crédito") or "Crédito",
                "Factura": purchase.get("invoice", "N/A") or "N/A"
            })
        
        df_final = pd.DataFrame(df_display)
        
        # Ordenar por fecha descendente
        if not df_final.empty and "Fecha" in df_final.columns:
            df_final = df_final.sort_values("Fecha", ascending=False)
        
        st.dataframe(df_final, use_container_width=True, hide_index=True)
        
        # Estadísticas
        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2, col3, col4 = st.columns(4)
        
        total_compras = sum(p["quantity"] * p["unit_cost"] for p in db["purchases"])
        compras_inv = sum(p["quantity"] * p["unit_cost"] for p in db["purchases"] if p.get("item_id"))
        gastos_op = sum(p["quantity"] * p["unit_cost"] for p in db["purchases"] if not p.get("item_id"))
        total_transacciones = len(db["purchases"])
        
        with col1:
            st.metric("Total Compras", cop(total_compras))
        with col2:
            st.metric("Inventario", cop(compras_inv))
        with col3:
            st.metric("Gastos Operativos", cop(gastos_op))
        with col4:
            st.metric("Transacciones", total_transacciones)
        
        # Descargar CSV
        csv = df_final.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Descargar historial en CSV",
            data=csv,
            file_name="historial_compras.csv",
            mime="text/csv"
        )
    else:
        st.info("Aún no hay compras o gastos registrados.")