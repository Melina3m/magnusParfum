import streamlit as st
import pandas as pd
from datetime import date
from database import insert_record, update_record
from utils import uid, cop

def render_sales(db):
    st.markdown("""
        <div style='margin-bottom: 2rem;'>
            <h2 style='margin: 0; color: #1a1a2e;'>Registro de Ventas</h2>
            <p style='margin: 0.5rem 0 0 0; color: #636e72;'>
                Gestión de salidas de productos y transacciones
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    # Preparar opciones de productos
    options = [f"{p['name']} — Stock {p.get('stock',0)}" for p in db["inventory"]]
    
    if not options:
        st.warning("No hay productos en el inventario. Agrega productos primero en la pestaña de Inventario.")
        return
    
    st.markdown("### Nueva Venta")
    
    # Selector de producto
    item_name = st.selectbox(
        "Selecciona el producto", 
        options=["Selecciona un producto..."] + options, 
        key="sel_venta",
        help="Elige el producto que deseas vender"
    )

    with st.form("sale_form", clear_on_submit=True):
        selected_idx = None
        prod = None
        
        if item_name != "Selecciona un producto...":
            selected_idx = options.index(item_name)
            prod = db["inventory"][selected_idx]
            
            # Mostrar información del producto seleccionado
            st.markdown(f"""
                <div style='background: linear-gradient(135deg, #d9e8ff, #b3d4ff); 
                            padding: 1rem; border-radius: 10px; margin-bottom: 1rem;'>
                    <strong>{prod['name']}</strong> — {prod.get('brand', 'Sin marca')} 
                    ({prod.get('size_ml', 0)} ml) | 
                    Stock disponible: <strong>{prod.get('stock', 0)}</strong> | 
                    Precio sugerido: <strong>{cop(prod.get('price', 0))}</strong>
                </div>
            """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3)
        
        with col1:
            quantity = st.number_input(
                "Cantidad", 
                min_value=1, 
                step=1, 
                value=1, 
                key="qty_venta",
                help="Número de unidades a vender"
            )
        
        with col2:
            default_price = float(prod.get('price', 0)) if prod else 0.0
            unit_price = st.number_input(
                "Precio unitario", 
                min_value=0.0, 
                step=1000.0, 
                value=default_price, 
                format="%.0f", 
                key="up_venta",
                help="Precio de venta por unidad"
            )
        
        with col3:
            sdate = st.date_input(
                "Fecha", 
                value=date.today(), 
                key="sdate_venta",
                help="Fecha de la transacción"
            )

        col4, col5 = st.columns(2)
        
        with col4:
            payment = st.selectbox(
                "Forma de pago", 
                options=["Efectivo", "Transferencia", "Tarjeta", "Fiado"], 
                key="pay_venta",
                help="Método de pago utilizado"
            )
        
        with col5:
            customer = st.text_input(
                "Cliente", 
                key="cust_venta",
                placeholder="Nombre del cliente (opcional)",
                help="Nombre o identificación del cliente"
            )

        # Lógica de Inversionista automática según el producto
        default_inv = False
        if prod:
            default_inv = bool(prod.get("inv", False))
        
        inv_flag_sale = st.checkbox(
            "Contar esta venta para el inversionista", 
            value=default_inv, 
            key="inv_venta",
            help="Marca si esta venta se incluye en el cálculo de utilidades del inversionista"
        )
        
        # Opción de compra al proveedor si no hay stock suficiente
        auto_purchase = False
        supplier_name = ""
        purchase_cost = 0.0
        
        if prod and quantity > 0:
            stock_disponible = prod.get("stock", 0)
            if stock_disponible < quantity:
                faltante = quantity - stock_disponible
                st.markdown("---")
                st.warning(f"⚠️ Stock insuficiente. Faltan {faltante} unidad(es)")
                
                auto_purchase = st.checkbox(
                    f"✓ Comprar {faltante} unidad(es) al proveedor (a crédito) automáticamente",
                    value=False,
                    key="auto_purchase_check",
                    help="Registra automáticamente la compra al proveedor a crédito antes de la venta"
                )
                
                if auto_purchase:
                    col_prov1, col_prov2 = st.columns(2)
                    with col_prov1:
                        supplier_name = st.text_input(
                            "Nombre del proveedor *",
                            key="auto_supplier_name",
                            placeholder="Ej: Distribuidora XYZ"
                        )
                    with col_prov2:
                        purchase_cost = st.number_input(
                            "Costo unitario de compra",
                            min_value=0.0,
                            step=1000.0,
                            value=float(prod.get("cost", 0)),
                            format="%.0f",
                            key="auto_purchase_cost",
                            help="Costo por unidad al proveedor"
                        )
                    
                    total_compra = faltante * purchase_cost
                    st.info(f"💰 Total a deber al proveedor: {cop(total_compra)}")

        # Campos adicionales para ventas a crédito
        phone, due = None, None
        if payment == "Fiado":
            st.markdown("#### Información de Crédito")
            col6, col7 = st.columns(2)
            with col6:
                phone = st.text_input(
                    "Teléfono del cliente", 
                    key="phone_venta",
                    placeholder="Ej: 3001234567",
                    help="Número de contacto para seguimiento"
                )
            with col7:
                due = st.date_input(
                    "Fecha de vencimiento", 
                    value=date.today(), 
                    key="due_venta",
                    help="Fecha límite para el pago"
                )

        notes = st.text_area(
            "Notas adicionales (opcional)", 
            key="notes_venta",
            placeholder="Observaciones sobre la venta...",
            height=80
        )

        # Mostrar resumen de la venta
        if prod and quantity and unit_price:
            total_sale = quantity * unit_price
            estimated_cost = quantity * prod.get('cost', 0)
            estimated_profit = total_sale - estimated_cost
            
            st.markdown(f"""
                <div style='background: linear-gradient(135deg, #d4f1e8, #b8e6d5); 
                            padding: 1.25rem; border-radius: 10px; margin-top: 1rem;'>
                    <div style='font-size: 0.875rem; color: #037856; margin-bottom: 0.5rem;'>
                        <strong>RESUMEN DE LA VENTA</strong>
                    </div>
                    <div style='display: flex; justify-content: space-between; font-size: 0.95rem;'>
                        <span>Total a cobrar:</span>
                        <strong>{cop(total_sale)}</strong>
                    </div>
                    <div style='display: flex; justify-content: space-between; font-size: 0.95rem;'>
                        <span>Costo estimado:</span>
                        <strong>{cop(estimated_cost)}</strong>
                    </div>
                    <div style='display: flex; justify-content: space-between; font-size: 1.1rem; 
                                margin-top: 0.5rem; padding-top: 0.5rem; border-top: 2px solid #06d6a0;'>
                        <span>Utilidad estimada:</span>
                        <strong style='color: #037856;'>{cop(estimated_profit)}</strong>
                    </div>
                </div>
            """, unsafe_allow_html=True)

        ok = st.form_submit_button("Registrar Venta", use_container_width=True, type="primary")
        
        if ok:
            if selected_idx is None:
                st.error("Debes seleccionar un producto.")
            else:
                prod = db["inventory"][selected_idx]
                qty = int(quantity)
                stock_disponible = prod.get("stock", 0)
                
                # Validar si necesita compra automática
                if stock_disponible < qty and not auto_purchase:
                    st.error(f"⚠️ Stock insuficiente ({stock_disponible} disponibles). Marca la opción de compra al proveedor para continuar.")
                elif auto_purchase and not supplier_name.strip():
                    st.error("⚠️ Debes indicar el nombre del proveedor para la compra automática.")
                else:
                    # Si hay compra automática, registrarla primero
                    if auto_purchase and stock_disponible < qty:
                        from database import insert_record as db_insert
                        
                        faltante = qty - stock_disponible
                        purchase_id = uid()
                        
                        # Registrar la compra
                        purchase = {
                            "id": purchase_id,
                            "date": sdate.isoformat(),
                            "item_id": prod["id"],
                            "quantity": faltante,
                            "unit_cost": float(purchase_cost),
                            "supplier": supplier_name.strip(),
                            "notes": f"Compra automática para venta - Cliente: {customer or 'N/A'}",
                            "invoice": ""
                        }
                        db_insert("purchases", purchase)
                        
                        # Actualizar stock después de la compra
                        new_stock_after_purchase = stock_disponible + faltante
                        update_record("inventory", {"stock": new_stock_after_purchase}, prod["id"])
                        
                        # Registrar crédito con proveedor
                        total_deuda_proveedor = faltante * float(purchase_cost)
                        db_insert("supplier_credits", {
                            "id": uid(),
                            "supplier": supplier_name.strip(),
                            "date": sdate.isoformat(),
                            "purchase_id": purchase_id,
                            "invoice": "",
                            "total": total_deuda_proveedor,
                            "paid": 0.0,
                            "due_date": None,
                            "notes": f"Compra para venta - Cliente: {customer or 'N/A'}"
                        })
                        
                        # Actualizar costo del producto si es diferente
                        if float(purchase_cost) > 0:
                            update_record("inventory", {"cost": float(purchase_cost)}, prod["id"])
                        
                        # Refrescar datos del producto
                        prod = next((p for p in db["inventory"] if p["id"] == prod["id"]), prod)
                    
                    # Registrar la venta
                    price = float(unit_price or prod.get("price", 0))
                    current_cost = float(prod.get("cost", 0))
                    
                    sale = {
                        "id": uid(), 
                        "date": sdate.isoformat(), 
                        "item_id": prod["id"],
                        "quantity": qty, 
                        "unit_price": price, 
                        "cost_at_sale": current_cost,
                        "customer": customer,
                        "payment": payment, 
                        "notes": notes, 
                        "inv": bool(inv_flag_sale)
                    }
                    
                    insert_record("sales", sale)

                    # Actualizar Inventario después de la venta
                    final_stock = int(prod.get("stock", 0)) - qty
                    update_record("inventory", {"stock": final_stock}, prod["id"])

                    # Registrar Crédito si es Fiado
                    if payment == "Fiado":
                        credit = {
                            "id": uid(), 
                            "customer": customer or "Cliente", 
                            "sale_id": sale["id"],
                            "date": sdate.isoformat(), 
                            "total": qty * price, 
                            "paid": 0.0,
                            "due_date": due.isoformat() if isinstance(due, date) else None,
                            "phone": phone or "", 
                            "notes": ""
                        }
                        insert_record("credits", credit)

                    profit = (price - current_cost) * qty
                    
                    if auto_purchase:
                        st.success(f"✓ Compra al proveedor y venta registradas exitosamente. Utilidad: {cop(profit)}")
                    else:
                        st.success(f"✓ Venta registrada exitosamente. Utilidad: {cop(profit)}")
                    
                    st.rerun()

    st.markdown("<hr style='margin: 2rem 0;'>", unsafe_allow_html=True)

    # Historial de ventas
    st.markdown("### Historial de Ventas")
    
    if db["sales"]:
        df_sales = pd.DataFrame(db["sales"])
        
        # Ordenar por fecha descendente
        if "date" in df_sales.columns:
            df_sales = df_sales.sort_values("date", ascending=False)
        
        # Preparar datos para visualización
        df_display = []
        for _, sale in df_sales.iterrows():
            prod = next((p for p in db["inventory"] if p["id"] == sale.get("item_id")), None)
            prod_name = prod.get("name", "Producto eliminado") if prod else "Producto eliminado"
            
            total = sale.get("quantity", 0) * sale.get("unit_price", 0)
            cost_total = sale.get("quantity", 0) * sale.get("cost_at_sale", 0)
            profit = total - cost_total
            
            df_display.append({
                "Fecha": sale.get("date", ""),
                "Producto": prod_name,
                "Cliente": sale.get("customer", "N/A") or "N/A",
                "Cantidad": sale.get("quantity", 0),
                "Precio Unit.": cop(sale.get("unit_price", 0)),
                "Total": cop(total),
                "Utilidad": cop(profit),
                "Pago": sale.get("payment", "N/A"),
                "INV": "Sí" if sale.get("inv") else "No"
            })
        
        df_final = pd.DataFrame(df_display)
        
        # Mostrar tabla
        st.dataframe(df_final, use_container_width=True, hide_index=True)
        
        # Estadísticas rápidas
        st.markdown("<br>", unsafe_allow_html=True)
        
        col1, col2, col3, col4 = st.columns(4)
        
        total_sales = sum(s["quantity"] * s["unit_price"] for s in db["sales"])
        total_profit = sum(s["quantity"] * (s["unit_price"] - s.get("cost_at_sale", 0)) 
                          for s in db["sales"])
        total_transactions = len(db["sales"])
        avg_ticket = total_sales / total_transactions if total_transactions > 0 else 0
        
        with col1:
            st.metric("Total Vendido", cop(total_sales))
        with col2:
            st.metric("Utilidad Total", cop(total_profit))
        with col3:
            st.metric("Transacciones", total_transactions)
        with col4:
            st.metric("Ticket Promedio", cop(avg_ticket))
        
        # Descargar CSV
        csv = df_final.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Descargar historial en CSV",
            data=csv,
            file_name="historial_ventas.csv",
            mime="text/csv"
        )
    else:
        st.info("Aún no hay ventas registradas. Realiza tu primera venta usando el formulario.")