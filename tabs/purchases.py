import streamlit as st
import pandas as pd
from datetime import date
from database import insert_record, update_record
from utils import uid

def render_purchases(db):
    st.subheader("Compras (entradas)")
    
    compra_tipo = st.radio(
        "¿Qué tipo de compra es?",
        ["Añadir al inventario (perfumes para vender)", "Gasto operativo (no afecta stock)"]
    )

    # --- COMPRAS DE INVENTARIO ---
    if compra_tipo == "Añadir al inventario (perfumes para vender)":
        inv_options = [f"{p['name']} — {p.get('brand','')}" for p in db["inventory"]]
        opcion = st.selectbox("Producto del inventario", options=["(Crear nuevo)"] + inv_options)
        
        creando_nuevo = (opcion == "(Crear nuevo)")
        if creando_nuevo:
            c0, c1, c2, c3 = st.columns([2,1,1,1])
            new_name = c0.text_input("Nombre del perfume *", key="new_name_comp")
            new_brand = c1.text_input("Marca", key="new_brand_comp")
            new_size = c2.number_input("Tamaño (ml)", min_value=0, step=1, value=0, key="new_size_comp")
            new_price = c3.number_input("Precio venta sugerido", min_value=0.0, step=1000.0, value=0.0, format="%.0f", key="new_price_comp")
        else:
            selected_index = inv_options.index(opcion)
            prod_sel = db["inventory"][selected_index]
            st.info(f"Seleccionado: **{prod_sel['name']}** — {prod_sel.get('brand','')} ({prod_sel.get('size_ml',0)} ml)")

        with st.form("purchase_form_inv", clear_on_submit=True):
            c1, c2, c3 = st.columns([1,1,2])
            quantity = c1.number_input("Cantidad", min_value=1, step=1, value=1, key="qty_inv")
            unit_cost = c2.number_input("Costo unit.", min_value=0.0, step=1000.0, value=0.0, format="%.0f", key="uc_inv")
            supplier = c3.text_input("Proveedor (opcional)", key="sup_inv")
            
            d1, d2, d3 = st.columns([1,1,2])
            pdate = d1.date_input("Fecha", value=date.today(), key="pdate_inv")
            pago = d2.selectbox("Pago", options=["Contado", "Crédito proveedor"], key="pago_inv")
            invoice = d3.text_input("N° factura/nota", key="invoice_inv")
            
            due = None
            medio_contado = None
            if pago == "Crédito proveedor":
                e1, e2 = st.columns([1,2])
                due = e1.date_input("Vence", value=date.today(), key="due_inv")
                notes = e2.text_input("Notas", key="notes_inv")
            else:
                e1, e2 = st.columns([1,2])
                medio_contado = e1.selectbox("Medio", options=["Efectivo", "Transferencia", "Tarjeta"], key="medio_inv")
                notes = e2.text_input("Notas", key="notes_inv2")
            
            ok = st.form_submit_button("Registrar compra")
        
        if ok:
            if creando_nuevo:
                if not new_name.strip():
                    st.error("El nombre es obligatorio.")
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
                    st.error("Para crédito proveedor debes indicar el proveedor.")
                    st.stop()
                total = int(quantity) * float(unit_cost or 0)
                insert_record("supplier_credits", {
                    "id": uid(), "supplier": supplier.strip(), "date": pdate.isoformat(),
                    "purchase_id": purchase_id, "invoice": invoice.strip(),
                    "total": float(total), "paid": 0.0,
                    "due_date": due.isoformat() if due else None, "notes": notes.strip()
                })
            
            st.success("Compra registrada. Inventario actualizado.")
            st.rerun()
    
    # --- GASTOS OPERATIVOS ---
    else:
        with st.form("purchase_form_gasto", clear_on_submit=True):
            c1, c2 = st.columns([1,1])
            pdate = c1.date_input("Fecha", value=date.today(), key="pdate_gasto")
            categoria = c2.text_input("Categoría del gasto", key="cat_gasto")
            
            c3, c4 = st.columns([1,1])
            total_gasto = c3.number_input("Monto", min_value=0.0, step=1000.0, value=0.0, format="%.0f", key="total_gasto")
            supplier = c4.text_input("Proveedor", key="sup_gasto")
            
            d1, d2, d3 = st.columns([1,1,2])
            pago = d1.selectbox("Pago", options=["Contado", "Crédito proveedor"], key="pago_gasto")
            medio_gasto = None
            if pago == "Contado":
                medio_gasto = d2.selectbox("Medio", options=["Efectivo", "Transferencia", "Tarjeta"], key="medio_gasto")
            invoice = d3.text_input("N° factura", key="invoice_gasto")
            
            notes = st.text_input("Notas", key="notes_gasto")
            
            due = None
            if pago == "Crédito proveedor":
                e1, _ = st.columns([1,3])
                due = e1.date_input("Vence", value=date.today(), key="due_gasto")
            
            ok2 = st.form_submit_button("Registrar gasto")
        
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
                    st.error("Para crédito proveedor debes indicar el proveedor.")
                    st.stop()
                insert_record("supplier_credits", {
                    "id": uid(), "supplier": supplier.strip(), "date": pdate.isoformat(),
                    "purchase_id": purchase_id, "invoice": invoice.strip(),
                    "total": float(total_gasto or 0), "paid": 0.0,
                    "due_date": due.isoformat() if due else None,
                    "notes": (categoria.strip() + " — " if categoria else "") + notes.strip()
                })
            
            st.success("Gasto registrado.")
            st.rerun()
    
    # Historial
    if db["purchases"]:
        st.markdown("### Historial de compras/gastos")
        st.dataframe(pd.DataFrame(db["purchases"]), use_container_width=True)
    else:
        st.info("Sin compras/gastos registrados.")