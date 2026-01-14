import streamlit as st
import pandas as pd
from database import insert_record, update_record, delete_record
from utils import uid, cop # Importamos cop para los ajustes rápidos

def render_inventory(db):
    st.subheader("Inventario")
    
    with st.form("add_item", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns([2,1,1,1])
        name = c1.text_input("Nombre del perfume *")
        brand = c2.text_input("Marca", placeholder="Emper, Armani, ...")
        size_ml = c3.number_input("Tamaño (ml)", min_value=0, step=1, value=0)
        stock = c4.number_input("Stock inicial", min_value=0, step=1, value=0)
        
        c5, c6 = st.columns(2)
        cost = c5.number_input("Costo unitario", min_value=0.0, step=1000.0, value=0.0, format="%.0f")
        price = c6.number_input("Precio de venta", min_value=0.0, step=1000.0, value=0.0, format="%.0f")
        
        inv_flag = st.checkbox("Contar este perfume para inversionista", value=True)
        notes = st.text_input("Notas (opcional)")
        submitted = st.form_submit_button("Agregar/Actualizar")
        
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
                    st.success("Producto actualizado.")
                else:
                    new_prod = {
                        "id": uid(), "name": name.strip(), "brand": brand.strip(),
                        "size_ml": int(size_ml or 0), "cost": float(cost or 0),
                        "price": float(price or 0), "stock": int(stock or 0),
                        "notes": notes.strip(), "inv": bool(inv_flag)
                    }
                    insert_record("inventory", new_prod)
                    st.success("Producto agregado.")
                st.rerun()

    # Búsqueda
    q = st.text_input("Buscar", "")
    df_inv = pd.DataFrame(db["inventory"])
    
    if not df_inv.empty:
        if q:
            mask = df_inv.apply(lambda r: q.lower() in f"{r.get('name','')} {r.get('brand','')}".lower(), axis=1)
            df_inv = df_inv[mask]
        
        # --- CAMBIO AQUÍ: Formato de miles para la tabla de inventario ---
        st.dataframe(
            df_inv.style.format({
                "cost": "{:,.0f}",
                "price": "{:,.0f}",
                "stock": "{:,.0f}"
            }).replace(",", "."), 
            use_container_width=True
        )
        # ---------------------------------------------------------------
    else:
        st.info("No hay productos aún.")

    # Ajustes rápidos
    st.markdown("### Ajustes rápidos de stock")
    for p in db["inventory"]:
        c1, c2, c3, c4, c5 = st.columns([2,1,1,1,1])
        # Usamos cop() para que el costo y precio se vean bien aquí también
        info_prod = f"**{p['name']}** — {p.get('brand','')} ({p.get('size_ml','')} ml)"
        precios = f" | Costo: {cop(p.get('cost',0))} | PVP: {cop(p.get('price',0))}"
        
        c1.write(info_prod + precios)
        c2.write(f"Stock: {p.get('stock',0)}")
        
        if c3.button("+1", key=f"plus_{p['id']}"):
            update_record("inventory", {"stock": int(p.get("stock", 0)) + 1}, p["id"])
            st.rerun()
        if c4.button("-1", key=f"minus_{p['id']}"):
            update_record("inventory", {"stock": max(0, int(p.get("stock", 0)) - 1)}, p["id"])
            st.rerun()
        if c5.button("Eliminar", key=f"del_{p['id']}"):
            delete_record("inventory", p["id"])
            st.rerun()