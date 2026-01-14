import streamlit as st
import pandas as pd
from datetime import date
from database import insert_record, update_record
from utils import uid, cop

def render_sales(db):
    st.subheader("Ventas (salidas)")
    
    # Preparamos la lista de opciones
    options = [f"{p['name']} — Stock {p.get('stock',0)}" for p in db["inventory"]]
    item_name = st.selectbox("Producto", options=["Selecciona..."] + options, key="sel_venta")
    
    with st.form("sale_form", clear_on_submit=True):
        selected_idx = None
        if item_name != "Selecciona...":
            selected_idx = options.index(item_name)
            
        c1, c2, c3 = st.columns([2,1,1])
        quantity = c2.number_input("Cantidad", min_value=1, step=1, value=1, key="qty_venta")
        unit_price = c3.number_input("Precio unit.", min_value=0.0, step=1000.0, value=0.0, format="%.0f", key="up_venta")
        
        c4, c5, c6 = st.columns(3)
        payment = c4.selectbox("Pago", options=["Efectivo", "Transferencia", "Tarjeta", "Fiado"], key="pay_venta")
        customer = c5.text_input("Cliente", key="cust_venta")
        sdate = c6.date_input("Fecha", value=date.today(), key="sdate_venta")
        notes = st.text_input("Notas", key="notes_venta")

        default_inv = False
        if selected_idx is not None:
            prod = db["inventory"][selected_idx]
            default_inv = bool(prod.get("inv", False))
                
        inv_flag_sale = st.checkbox("Contar esta venta para inversionista", value=default_inv, key="inv_venta")
        
        phone, due = None, None
        if payment == "Fiado":
            c7, c8 = st.columns(2)
            phone = c7.text_input("Teléfono", key="phone_venta")
            due = c8.date_input("Vence", value=date.today(), key="due_venta")
            
        ok = st.form_submit_button("Registrar venta")
        
        if ok:
            if selected_idx is None:
                st.error("Selecciona un producto.")
            else:
                prod = db["inventory"][selected_idx]
                qty = int(quantity)
                
                if prod.get("stock", 0) < qty:
                    st.error(f"Stock insuficiente. Solo quedan {prod.get('stock', 0)} unidades.")
                else:
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
                    new_stock = int(prod.get("stock", 0)) - qty
                    update_record("inventory", {"stock": new_stock}, prod["id"])
                    
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
                    
                    # Mensaje de éxito usando la función cop() para que se vea con puntos
                    utilidad = (price - current_cost) * qty
                    st.success(f"Venta registrada. Utilidad estimada: {cop(utilidad)}")
                    st.rerun()

    # Visualización de la tabla
    if db["sales"]:
        st.markdown("### Historial de Ventas")
        df_sales = pd.DataFrame(db["sales"])
        
        if "date" in df_sales:
            df_sales = df_sales.sort_values("date", ascending=False)
        
        # --- CAMBIO AQUÍ: Formato de miles para la tabla de ventas ---
        st.dataframe(
            df_sales.style.format({
                "unit_price": "{:,.0f}",
                "cost_at_sale": "{:,.0f}",
                "quantity": "{:,.0f}"
            }).replace(",", "."), 
            use_container_width=True
        )
    else:
        st.info("Sin ventas registradas.")