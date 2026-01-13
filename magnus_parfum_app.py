import json
import os
from datetime import date, datetime
from typing import Dict, Any, List, Tuple
import base64
from io import BytesIO
from fpdf import FPDF
import pandas as pd
import streamlit as st
from collections import defaultdict
import re
import gspread
from google.oauth2.service_account import Credentials

GSHEETS_CREDENTIALS_FILE = "magnusparfum-3da1ae652226.json"
GS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

APP_TITLE = "Magnus Parfum — Gestión simple (Streamlit)"
DB_PATH = "magnus_parfum_db.json"

# ----------------- Utilidades de persistencia -----------------
DEFAULT_DB = {
    "settings": {
        "currency": "COP",
        "investor_share": 50,   # % de utilidad para el inversionista
        "gsheets_sheet_id": "",
        "gsheets_sync": False,
        "gsheets_tabs": {
            "Inventario": "Inventario",
            "Compras": "Compras",
            "Ventas": "Ventas",
            "AbonosClientes": "AbonosClientes",
            "PagosProveedores": "PagosProveedores"
        }
    },
    "inventory": [],         # [{id, name, brand, size_ml, cost, price, stock, notes, inv?}]
    "purchases": [],         # [{id, date, item_id, quantity, unit_cost, supplier, notes, invoice?, cash_method?}]
    "sales": [],             # [{id, date, item_id, quantity, unit_price, customer, payment, notes, inv?}]
    "credits": [],           # [{id, customer, sale_id, date, total, paid, due_date, phone, notes}]
    "investor": [],          # [{id, date, type("Aporte"/"Retiro"/"Utilidad"), amount, notes}]
    "credit_payments": [],   # [{id, customer, date, amount, notes, method}]
    "supplier_credits": [],  # Deudas con proveedores por compras a crédito
    "supplier_payments": [], # [{id, supplier, date, amount, notes, method}]
}

def load_db(path: str = DB_PATH) -> Dict[str, Any]:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_DB.copy()

def save_db(db: Dict[str, Any], path: str = DB_PATH):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

def uid() -> str:
    return f"{datetime.utcnow().timestamp():.6f}".replace(".", "")

def cop(n: float) -> str:
    try:
        n = float(n)
    except Exception:
        return "-"
    return f"${int(round(n, 0)):,}".replace(",", ".")

def today_iso() -> str:
    return date.today().isoformat()

# ----------------- Libro de Caja/Banco -----------------
def _movements_ledger(db) -> List[dict]:
    """
    Construye un libro de movimientos con:
      + Ventas (entran a Caja/Banco según payment)
      + Abonos de clientes (entran según method)
      - Compras al contado (salen según cash_method)
      - Pagos a proveedores (salen según method)
    """
    movs = []

    # Ventas
    for s in db.get("sales", []):
        amt = float(s.get("quantity", 0) or 0) * float(s.get("unit_price", 0) or 0)
        meth = (s.get("payment") or "").strip().title()
        if meth in ("Efectivo", "Transferencia", "Tarjeta"):
            movs.append({
                "fecha": s.get("date", ""),
                "tipo": "Entrada",
                "medio": "Caja" if meth == "Efectivo" else "Banco",
                "concepto": f"Venta — {meth}",
                "detalle": s.get("customer", "") or "",
                "monto": amt
            })

    # Abonos clientes (fiados)
    for p in db.get("credit_payments", []):
        amt = float(p.get("amount", 0) or 0)
        meth = (p.get("method") or "").strip().title()
        medio = "Caja" if meth == "Efectivo" else "Banco"
        movs.append({
            "fecha": p.get("date", ""),
            "tipo": "Entrada",
            "medio": medio,
            "concepto": f"Abono cliente — {meth}",
            "detalle": p.get("customer", ""),
            "monto": amt
        })

    # Compras al contado
    for pu in db.get("purchases", []):
        meth = (pu.get("cash_method") or "").strip().title()
        if meth:
            q = int(pu.get("quantity", 1) or 1)
            uc = float(pu.get("unit_cost", 0) or 0)
            amt = q * uc
            medio = "Caja" if meth == "Efectivo" else "Banco"
            concepto = "Compra inventario" if pu.get("item_id") else "Gasto operativo"
            movs.append({
                "fecha": pu.get("date", ""),
                "tipo": "Salida",
                "medio": medio,
                "concepto": f"{concepto} — {meth}",
                "detalle": pu.get("supplier", "") or "",
                "monto": amt
            })

    # Pagos a proveedores
    for sp in db.get("supplier_payments", []):
        amt = float(sp.get("amount", 0) or 0)
        meth = (sp.get("method") or "").strip().title()
        medio = "Caja" if meth == "Efectivo" else "Banco"
        movs.append({
            "fecha": sp.get("date", ""),
            "tipo": "Salida",
            "medio": medio,
            "concepto": f"Pago a proveedor — {meth}",
            "detalle": sp.get("supplier", "") or "",
            "monto": amt
        })

    # Normalizar fechas para ordenar
    def _key(m):
        try:
            return m["fecha"]
        except Exception:
            return ""
    movs.sort(key=_key)
    return movs

def cash_bank_balances(db) -> Tuple[float, float]:
    """Suma entradas/salidas del libro: retorna (caja, banco). Inicia en 0 siempre."""
    caja = 0.0
    banco = 0.0
    for m in _movements_ledger(db):
        sign = 1 if m["tipo"] == "Entrada" else -1
        if m["medio"] == "Caja":
            caja += sign * float(m["monto"] or 0)
        else:
            banco += sign * float(m["monto"] or 0)
    return caja, banco

# ----------------- Saldos y abonos (clientes y proveedores) -----------------
def credit_saldo(c):
    return float(c.get("total", 0)) - float(c.get("paid", 0))

def apply_customer_payment(db, customer: str, amount: float, when: str, notes: str = "", method: str = ""):
    """Distribuye un abono entre deudas abiertas (FIFO) y registra el medio de pago."""
    if amount <= 0:
        return 0.0
    open_credits = [c for c in db["credits"]
                    if (c.get("customer","").strip().lower() == customer.strip().lower()) and credit_saldo(c) > 0]
    open_credits.sort(key=lambda c: c.get("date",""))
    remaining = float(amount)
    for c in open_credits:
        if remaining <= 0:
            break
        s = credit_saldo(c)
        if s <= 0:
            continue
        pay = min(s, remaining)
        c["paid"] = float(c.get("paid", 0)) + pay
        remaining -= pay
    db["credit_payments"].insert(0, {
        "id": uid(), "customer": customer, "date": when, "amount": float(amount),
        "notes": notes, "method": method
    })
    save_db(db)
    return float(amount) - remaining

def supplier_credit_saldo(c):
    return float(c.get("total", 0)) - float(c.get("paid", 0))

def apply_supplier_payment(db, supplier: str, amount: float, when: str, notes: str = "", method: str = ""):
    """Abona a un proveedor (FIFO) y registra el medio de pago."""
    if amount <= 0:
        return 0.0
    open_credits = [c for c in db["supplier_credits"]
                    if (c.get("supplier","").strip().lower() == supplier.strip().lower()) and supplier_credit_saldo(c) > 0]
    open_credits.sort(key=lambda c: c.get("date",""))
    remaining = float(amount)
    for c in open_credits:
        if remaining <= 0:
            break
        s = supplier_credit_saldo(c)
        if s <= 0:
            continue
        pay = min(s, remaining)
        c["paid"] = float(c.get("paid", 0)) + pay
        remaining -= pay
    db["supplier_payments"].insert(0, {
        "id": uid(), "supplier": supplier, "date": when, "amount": float(amount),
        "notes": notes, "method": method
    })
    save_db(db)
    return float(amount) - remaining

# ----------------- Google Sheets Helpers -----------------
def _parse_sheet_id(s: str) -> str | None:
    """Acepta ID puro o URL completa y devuelve el ID del Spreadsheet."""
    if not s:
        return None
    s = s.strip()
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", s)
    if m:
        return m.group(1)
    if re.fullmatch(r"[a-zA-Z0-9-_]{20,}", s):
        return s
    return None

def _gs_client_from_file():
    creds = Credentials.from_service_account_file(
        GSHEETS_CREDENTIALS_FILE,
        scopes=GS_SCOPES
    )
    return gspread.authorize(creds)

def _open_ss(db):
    sid = _parse_sheet_id(db["settings"].get("gsheets_sheet_id", ""))
    if not sid:
        raise RuntimeError("Falta el Spreadsheet ID (guárdalo en Ajustes).")
    gc = _gs_client_from_file()
    return gc.open_by_key(sid)

def _service_email_from_file() -> str | None:
    """Lee el client_email del JSON de credenciales para mostrarlo en Ajustes."""
    try:
        creds = Credentials.from_service_account_file(GSHEETS_CREDENTIALS_FILE, scopes=GS_SCOPES)
        return getattr(creds, "service_account_email", None) or getattr(creds, "client_email", None)
    except Exception:
        return None

# ----------------- Sincronización a Google Sheets -----------------
def _ensure_ws(ss, title: str, headers: list[str]):
    try:
        ws = ss.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        ws = ss.add_worksheet(title=title, rows=1000, cols=max(10, len(headers)))
    values = ws.get_all_values()
    if not values:
        ws.append_row(headers, value_input_option="USER_ENTERED")
    return ws

def _clear_and_write(ws, headers: list[str], rows: list[list]):
    """Borra toda la hoja y escribe encabezados + datos."""
    ws.clear()
    ws.update("A1", [headers])
    if rows:
        ws.update("A2", rows, value_input_option="USER_INPUT")

def _sync_safe(db, fn, *args, **kwargs):
    """Solo corre si gsheets_sync=True y hay ID; no detiene la app si falla."""
    try:
        if not db["settings"].get("gsheets_sync"):
            return
        sid = db["settings"].get("gsheets_sheet_id", "").strip()
        if not sid:
            return
        return fn(*args, **kwargs)
    except Exception as e:
        st.warning(f"No se pudo sincronizar con Google Sheets: {e}")

def sync_inventory_item(db, prod: dict):
    ss = _open_ss(db)
    tab = db["settings"]["gsheets_tabs"].get("Inventario", "Inventario")
    # Añadimos columna "inv"
    ws = _ensure_ws(ss, tab, ["id","name","brand","size_ml","cost","price","stock","notes","inv","updated_at"])
    ws.append_row([
        prod.get("id",""), prod.get("name",""), prod.get("brand",""),
        prod.get("size_ml",0), prod.get("cost",0), prod.get("price",0),
        prod.get("stock",0), prod.get("notes",""),
        "Sí" if prod.get("inv") else "",
        datetime.utcnow().isoformat()
    ], value_input_option="USER_ENTERED")

def sync_purchase(db, purchase: dict):
    ss = _open_ss(db)
    tab = db["settings"]["gsheets_tabs"].get("Compras", "Compras")
    ws = _ensure_ws(ss, tab, [
        "id","date","item_id","quantity","unit_cost","total","supplier",
        "cash_or_credit","cash_method","invoice","notes","created_at"
    ])
    q = int(purchase.get("quantity",1) or 1)
    uc = float(purchase.get("unit_cost",0) or 0)
    total = q*uc
    ws.append_row([
        purchase.get("id",""), purchase.get("date",""), purchase.get("item_id",""),
        q, uc, total, purchase.get("supplier",""),
        ("Contado" if purchase.get("cash_method") else "Crédito"),
        purchase.get("cash_method",""), purchase.get("invoice",""), purchase.get("notes",""),
        datetime.utcnow().isoformat()
    ], value_input_option="USER_ENTERED")

def sync_sale(db, sale: dict):
    ss = _open_ss(db)
    tab = db["settings"]["gsheets_tabs"].get("Ventas", "Ventas")
    # Añadimos columna "inv"
    ws = _ensure_ws(ss, tab, [
        "id","date","item_id","quantity","unit_price","total","customer","payment","notes","inv","created_at"
    ])
    q = int(sale.get("quantity",0) or 0)
    up = float(sale.get("unit_price",0) or 0)
    ws.append_row([
        sale.get("id",""), sale.get("date",""), sale.get("item_id",""),
        q, up, q*up, sale.get("customer",""), sale.get("payment",""),
        sale.get("notes",""), "Sí" if sale.get("inv") else "",
        datetime.utcnow().isoformat()
    ], value_input_option="USER_ENTERED")

def sync_credit_payment(db, pay: dict):
    ss = _open_ss(db)
    tab = db["settings"]["gsheets_tabs"].get("AbonosClientes", "AbonosClientes")
    ws = _ensure_ws(ss, tab, [
        "id","date","customer","amount","method","notes","created_at"
    ])
    ws.append_row([
        pay.get("id",""), pay.get("date",""), pay.get("customer",""),
        float(pay.get("amount",0) or 0), pay.get("method",""),
        pay.get("notes",""), datetime.utcnow().isoformat()
    ], value_input_option="USER_ENTERED")

def sync_supplier_payment(db, pay: dict):
    ss = _open_ss(db)
    tab = db["settings"]["gsheets_tabs"].get("PagosProveedores", "PagosProveedores")
    ws = _ensure_ws(ss, tab, [
        "id","date","supplier","amount","method","notes","created_at"
    ])
    ws.append_row([
        pay.get("id",""), pay.get("date",""), pay.get("supplier",""),
        float(pay.get("amount",0) or 0), pay.get("method",""),
        pay.get("notes",""), datetime.utcnow().isoformat()
    ], value_input_option="USER_ENTERED")

def sync_all_to_sheets(db) -> dict:
    """
    Sube TODO el contenido actual a Google Sheets.
    Crea pestañas si no existen, limpia y carga:
    - Inventario
    - Compras
    - Ventas
    - AbonosClientes
    - PagosProveedores
    """
    ss = _open_ss(db)
    tabs = db["settings"]["gsheets_tabs"]

    # Inventario (con inv)
    inv_headers = ["id","name","brand","size_ml","cost","price","stock","notes","inv","updated_at"]
    ws_inv = _ensure_ws(ss, tabs.get("Inventario","Inventario"), inv_headers)
    inv_rows = []
    for p in db.get("inventory", []):
        inv_rows.append([
            p.get("id",""), p.get("name",""), p.get("brand",""),
            p.get("size_ml",0), p.get("cost",0), p.get("price",0),
            p.get("stock",0), p.get("notes",""),
            "Sí" if p.get("inv") else "",
            datetime.utcnow().isoformat()
        ])
    _clear_and_write(ws_inv, inv_headers, inv_rows)

    # Compras
    pur_headers = ["id","date","item_id","quantity","unit_cost","total","supplier","cash_or_credit","cash_method","invoice","notes","created_at"]
    ws_pur = _ensure_ws(ss, tabs.get("Compras","Compras"), pur_headers)
    pur_rows = []
    for pu in db.get("purchases", []):
        q = int(pu.get("quantity",1) or 1)
        uc = float(pu.get("unit_cost",0) or 0)
        total = q*uc
        pur_rows.append([
            pu.get("id",""), pu.get("date",""), pu.get("item_id",""),
            q, uc, total, pu.get("supplier",""),
            ("Contado" if pu.get("cash_method") else "Crédito"),
            pu.get("cash_method",""), pu.get("invoice",""), pu.get("notes",""),
            datetime.utcnow().isoformat()
        ])
    _clear_and_write(ws_pur, pur_headers, pur_rows)

    # Ventas (con inv)
    sale_headers = ["id","date","item_id","quantity","unit_price","total","customer","payment","notes","inv","created_at"]
    ws_sale = _ensure_ws(ss, tabs.get("Ventas","Ventas"), sale_headers)
    sale_rows = []
    for s in db.get("sales", []):
        q = int(s.get("quantity",0) or 0)
        up = float(s.get("unit_price",0) or 0)
        sale_rows.append([
            s.get("id",""), s.get("date",""), s.get("item_id",""),
            q, up, q*up, s.get("customer",""), s.get("payment",""),
            s.get("notes",""), "Sí" if s.get("inv") else "",
            datetime.utcnow().isoformat()
        ])
    _clear_and_write(ws_sale, sale_headers, sale_rows)

    # Abonos de clientes
    cp_headers = ["id","date","customer","amount","method","notes","created_at"]
    ws_cp = _ensure_ws(ss, tabs.get("AbonosClientes","AbonosClientes"), cp_headers)
    cp_rows = []
    for p in db.get("credit_payments", []):
        cp_rows.append([
            p.get("id",""), p.get("date",""), p.get("customer",""),
            float(p.get("amount",0) or 0), p.get("method",""),
            p.get("notes",""), datetime.utcnow().isoformat()
        ])
    _clear_and_write(ws_cp, cp_headers, cp_rows)

    # Pagos a proveedores
    sp_headers = ["id","date","supplier","amount","method","notes","created_at"]
    ws_sp = _ensure_ws(ss, tabs.get("PagosProveedores","PagosProveedores"), sp_headers)
    sp_rows = []
    for sp in db.get("supplier_payments", []):
        sp_rows.append([
            sp.get("id",""), sp.get("date",""), sp.get("supplier",""),
            float(sp.get("amount",0) or 0), sp.get("method",""),
            sp.get("notes",""), datetime.utcnow().isoformat()
        ])
    _clear_and_write(ws_sp, sp_headers, sp_rows)

    return {
        "inventario": len(inv_rows),
        "compras": len(pur_rows),
        "ventas": len(sale_rows),
        "abonos_clientes": len(cp_rows),
        "pagos_proveedores": len(sp_rows),
    }

# ----------------- Helpers PDF / Logo -----------------
def _get_logo_temp_path(db) -> str | None:
    try:
        b64 = db["settings"].get("logo_b64")
        if not b64:
            return None
        raw = base64.b64decode(b64)
        temp_path = "magnus_logo_tmp.png"
        with open(temp_path, "wb") as f:
            f.write(raw)
        return temp_path
    except Exception:
        return None

def _pdf_header(pdf: FPDF, title: str, logo_path: str | None):
    if logo_path:
        try:
            pdf.image(logo_path, x=10, y=8, w=25)
        except Exception:
            pass
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "MAGNUS PARFUM", ln=1, align="R")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 6, title, ln=1, align="R")
    pdf.ln(6)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

def _pdf_kv(pdf: FPDF, label: str, value: str):
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(50, 6, label + ":", border=0)
    pdf.set_font("Helvetica", "", 11)
    if not value:
        value = "-"
    pdf.cell(0, 6, value, border=0, ln=1)

def build_receipt_pdf(db, *, who_type: str, who_name: str, receipt_id: str,
                      date_str: str, amount: float,
                      balance_before: float, balance_after: float,
                      notes: str = "", breakdown: list[dict] | None = None) -> bytes:
    logo_path = _get_logo_temp_path(db)
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    _pdf_header(pdf, f"RECIBO DE ABONO - {who_type}", logo_path)

    _pdf_kv(pdf, "Recibo", receipt_id)
    _pdf_kv(pdf, "Fecha", date_str)
    _pdf_kv(pdf, who_type.title(), who_name or ("Cliente" if who_type=="CLIENTE" else "Proveedor"))
    _pdf_kv(pdf, "Monto abonado", cop(amount))
    _pdf_kv(pdf, "Saldo ANTES", cop(balance_before))
    _pdf_kv(pdf, "Saldo DESPUÉS", cop(balance_after))
    if notes:
        _pdf_kv(pdf, "Notas", notes)

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Desglose de aplicación", ln=1)
    pdf.set_font("Helvetica", "", 10)
    if breakdown:
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(50, 7, "ID deuda", border=1, align="C", fill=True)
        pdf.cell(40, 7, "Fecha", border=1, align="C", fill=True)
        pdf.cell(40, 7, "Aplicado", border=1, align="C", fill=True)
        pdf.cell(40, 7, "Saldo restante", border=1, align="C", fill=True)
        pdf.ln(7)
        for row in breakdown:
            pdf.cell(50, 7, str(row.get("id","")), border=1)
            pdf.cell(40, 7, str(row.get("date",""))[:10], border=1)
            pdf.cell(40, 7, cop(row.get("applied", 0)), border=1, align="R")
            pdf.cell(40, 7, cop(row.get("remaining", 0)), border=1, align="R")
            pdf.ln(7)
    else:
        pdf.multi_cell(0, 6, "El abono se aplicó a deudas abiertas según antigüedad (FIFO).")

    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(0, 5, "Este recibo ha sido generado automáticamente por el sistema de gestión de Magnus Parfum.")

    out = BytesIO()
    pdf.output(out)
    try:
        if logo_path and os.path.exists(logo_path):
            os.remove(logo_path)
    except Exception:
        pass
    return out.getvalue()

# ----------------- App -----------------
st.set_page_config(page_title=APP_TITLE, page_icon="💐", layout="wide")
st.title(APP_TITLE)
st.caption("Inventario • Ventas • Fiados • Proveedores • Inversionista — Datos en un archivo local JSON + (opcional) Google Sheets")

# Cargar DB en sesión
if "db" not in st.session_state:
    st.session_state.db = load_db()
db = st.session_state.db

# Migración simple: asegura llaves nuevas si vienes de una versión anterior
for k, v in {
    "credit_payments": [],
    "supplier_credits": [],
    "supplier_payments": [],
}.items():
    if k not in db:
        db[k] = v
# Migración de settings de sync
db["settings"].setdefault("gsheets_sheet_id", "")
db["settings"].setdefault("gsheets_sync", False)
db["settings"].setdefault("gsheets_tabs", {
    "Inventario": "Inventario",
    "Compras": "Compras",
    "Ventas": "Ventas",
    "AbonosClientes": "AbonosClientes",
    "PagosProveedores": "PagosProveedores"
})

# ---- MIGRACIÓN de flags 'inv' en inventory y sales (si no existen) ----
for p in db.get("inventory", []):
    p.setdefault("inv", False)
for s in db.get("sales", []):
    s.setdefault("inv", None)  # None = no definido (hereda del producto). True/False = explícito

# Barra superior con indicadores
caja_actual, banco_actual = cash_bank_balances(db)
col1, col2, col3 = st.columns(3)
stock_cost = sum((p.get("cost", 0) or 0) * (p.get("stock", 0) or 0) for p in db["inventory"])
stock_retail = sum((p.get("price", 0) or 0) * (p.get("stock", 0) or 0) for p in db["inventory"])
col1.metric("Stock valorizado (costo)", cop(stock_cost))
col2.metric("Caja actual (efectivo)", cop(caja_actual))
col3.metric("Banco actual", cop(banco_actual))

tabs = st.tabs([
    "Inventario", "Compras", "Ventas", "Fiados", "Inversionista",
    "Reportes", "Importar/Exportar", "Ajustes", "Proveedores", "Caja y Bancos"
])

# ----------------- Inventario -----------------
with tabs[0]:
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
        inv_flag = st.checkbox("Contar este perfume para inversionista", value=True,
                               help="Si está marcado, las ganancias de este producto cuentan para el inversionista.")
        notes = st.text_input("Notas (opcional)")
        submitted = st.form_submit_button("Agregar/Actualizar")
        if submitted:
            if not name.strip():
                st.error("El nombre es obligatorio.")
            else:
                found_idx = None
                for i, p in enumerate(db["inventory"]):
                    if (p.get("name","").strip().lower() == name.strip().lower()
                        and p.get("brand","").strip().lower() == brand.strip().lower()
                        and int(p.get("size_ml") or 0) == int(size_ml or 0)):
                        found_idx = i
                        break
                if found_idx is not None:
                    p = db["inventory"][found_idx]
                    p.update({"cost": cost, "price": price, "stock": stock, "notes": notes, "inv": bool(inv_flag)})
                    st.success("Producto actualizado.")
                    save_db(db)
                else:
                    db["inventory"].insert(0, {
                        "id": uid(),
                        "name": name.strip(),
                        "brand": brand.strip(),
                        "size_ml": int(size_ml or 0),
                        "cost": float(cost or 0),
                        "price": float(price or 0),
                        "stock": int(stock or 0),
                        "notes": notes.strip(),
                        "inv": bool(inv_flag),
                    })
                    # Sincroniza el último insertado
                    _sync_safe(db, sync_inventory_item, db, db["inventory"][0])
                    st.success("Producto agregado.")
                    save_db(db)
            st.rerun()

    q = st.text_input("Buscar", "")
    df_inv = pd.DataFrame(db["inventory"])
    if not df_inv.empty:
        if q:
            mask = df_inv.apply(lambda r: q.lower() in f"{r.get('name','')} {r.get('brand','')}".lower(), axis=1)
            df_inv = df_inv[mask]
        st.dataframe(df_inv, use_container_width=True)
    else:
        st.info("No hay productos aún.")

    st.markdown("### Ajustes rápidos de stock")
    for p in db["inventory"]:
        c1, c2, c3, c4, c5 = st.columns([2,1,1,1,1])
        c1.write(f"**{p['name']}** — {p.get('brand','')} ({p.get('size_ml','')} ml)")
        c2.write(f"Stock: {p.get('stock',0)}")
        plus = c3.button("+1", key=f"plus_{p['id']}")
        minus = c4.button("-1", key=f"minus_{p['id']}")
        delete = c5.button("Eliminar", key=f"del_{p['id']}")
        if plus:
            p["stock"] = int(p.get("stock", 0)) + 1
            save_db(db)
            st.rerun()
        if minus:
            p["stock"] = max(0, int(p.get("stock", 0)) - 1)
            save_db(db)
            st.rerun()
        if delete:
            db["inventory"] = [x for x in db["inventory"] if x["id"] != p["id"]]
            save_db(db)
            st.rerun()

# ----------------- Compras -----------------
with tabs[1]:
    st.subheader("Compras (entradas)")

    compra_tipo = st.radio(
        "¿Qué tipo de compra es?",
        ["Añadir al inventario (perfumes para vender)", "Gasto operativo (no afecta stock)"],
        horizontal=False
    )

    # --- A) Inventario ---
    if compra_tipo == "Añadir al inventario (perfumes para vender)":
        st.markdown("**Selecciona un producto existente o crea uno nuevo**")

        inv_options = [f"{p['name']} — {p.get('brand','')}" for p in db["inventory"]]
        opcion = st.selectbox("Producto del inventario", options=["(Crear nuevo)"] + inv_options)

        creando_nuevo = (opcion == "(Crear nuevo)")
        if creando_nuevo:
            c0, c1, c2, c3 = st.columns([2,1,1,1])
            new_name = c0.text_input("Nombre del perfume *")
            new_brand = c1.text_input("Marca", placeholder="Emper, Armani, ...")
            new_size = c2.number_input("Tamaño (ml)", min_value=0, step=1, value=0)
            new_price = c3.number_input("Precio de venta sugerido", min_value=0.0, step=1000.0, value=0.0, format="%.0f")
        else:
            selected_index = inv_options.index(opcion)
            prod_sel = db["inventory"][selected_index]
            st.info(f"Seleccionado: **{prod_sel['name']}** — {prod_sel.get('brand','')} ({prod_sel.get('size_ml',0)} ml)")

        with st.form("purchase_form_inv", clear_on_submit=True):
            c1, c2, c3 = st.columns([1,1,2])
            quantity = c1.number_input("Cantidad", min_value=1, step=1, value=1)
            unit_cost = c2.number_input("Costo unit.", min_value=0.0, step=1000.0, value=0.0, format="%.0f")
            supplier = c3.text_input("Proveedor (opcional)")

            d1, d2, d3 = st.columns([1,1,2])
            pdate = d1.date_input("Fecha", value=date.today())
            pago = d2.selectbox("Pago", options=["Contado", "Crédito proveedor"])
            invoice = d3.text_input("N° factura/nota (opcional)")

            due = None
            medio_contado = None
            if pago == "Crédito proveedor":
                e1, e2 = st.columns([1,2])
                due = e1.date_input("Vence", value=date.today())
                notes = e2.text_input("Notas (opcional)")
            else:
                e1, e2 = st.columns([1,2])
                medio_contado = e1.selectbox("Medio (si es contado)", options=["Efectivo", "Transferencia", "Tarjeta"])
                notes = e2.text_input("Notas (opcional)")

            ok = st.form_submit_button("Registrar compra")

        if ok:
            if creando_nuevo:
                if not new_name.strip():
                    st.error("Para crear producto nuevo, el nombre es obligatorio.")
                    st.stop()
                new_prod = {
                    "id": uid(),
                    "name": new_name.strip(),
                    "brand": new_brand.strip(),
                    "size_ml": int(new_size or 0),
                    "cost": float(unit_cost or 0),
                    "price": float(new_price or 0),
                    "stock": 0,
                    "notes": "",
                    "inv": True  # por defecto se considera inversión si lo creas aquí
                }
                db["inventory"].insert(0, new_prod)
                _sync_safe(db, sync_inventory_item, db, new_prod)
                prod = new_prod
            else:
                prod = db["inventory"][selected_index]

            purchase_id = uid()
            purchase = {
                "id": purchase_id,
                "date": pdate.isoformat(),
                "item_id": prod["id"],
                "quantity": int(quantity),
                "unit_cost": float(unit_cost or 0),
                "supplier": supplier.strip(),
                "notes": notes.strip(),
                "invoice": invoice.strip()
            }
            if pago == "Contado":
                purchase["cash_method"] = medio_contado
            db["purchases"].insert(0, purchase)
            _sync_safe(db, sync_purchase, db, purchase)

            prod["stock"] = int(prod.get("stock", 0)) + int(quantity)
            if float(unit_cost or 0) > 0:
                prod["cost"] = float(unit_cost)

            if pago == "Crédito proveedor":
                if not supplier.strip():
                    st.error("Para crédito proveedor debes indicar el nombre del proveedor.")
                    st.stop()
                total = int(quantity) * float(unit_cost or 0)
                db["supplier_credits"].insert(0, {
                    "id": uid(),
                    "supplier": supplier.strip(),
                    "date": pdate.isoformat(),
                    "purchase_id": purchase_id,
                    "invoice": invoice.strip(),
                    "total": float(total),
                    "paid": 0.0,
                    "due_date": due.isoformat() if due else None,
                    "notes": notes.strip(),
                })

            save_db(db)
            st.success("Compra registrada. Inventario actualizado.")
            st.rerun()

    # --- B) Gasto operativo ---
    else:
        with st.form("purchase_form_gasto", clear_on_submit=True):
            c1, c2 = st.columns([1,1])
            pdate = c1.date_input("Fecha", value=date.today())
            categoria = c2.text_input("Categoría del gasto (opcional)", placeholder="Papelería, Envíos, Servicios, ...")

            c3, c4 = st.columns([1,1])
            total_gasto = c3.number_input("Monto del gasto", min_value=0.0, step=1000.0, value=0.0, format="%.0f")
            supplier = c4.text_input("Proveedor (opcional)")

            d1, d2, d3 = st.columns([1,1,2])
            pago = d1.selectbox("Pago", options=["Contado", "Crédito proveedor"])
            medio_gasto = None
            if pago == "Contado":
                medio_gasto = d2.selectbox("Medio", options=["Efectivo", "Transferencia", "Tarjeta"])
            invoice = d3.text_input("N° factura/nota (opcional)")

            notes = st.text_input("Notas (opcional)")

            due = None
            if pago == "Crédito proveedor":
                e1, _ = st.columns([1,3])
                due = e1.date_input("Vence", value=date.today())

            ok2 = st.form_submit_button("Registrar gasto")

        if ok2:
            purchase_id = uid()
            purchase = {
                "id": purchase_id,
                "date": pdate.isoformat(),
                "item_id": "",
                "quantity": 1,
                "unit_cost": float(total_gasto or 0),
                "supplier": supplier.strip(),
                "notes": (categoria.strip() + " — " if categoria else "") + notes.strip(),
                "invoice": invoice.strip()
            }
            if pago == "Contado":
                purchase["cash_method"] = medio_gasto
            db["purchases"].insert(0, purchase)
            _sync_safe(db, sync_purchase, db, purchase)

            if pago == "Crédito proveedor":
                if not supplier.strip():
                    st.error("Para crédito proveedor debes indicar el nombre del proveedor.")
                    st.stop()
                db["supplier_credits"].insert(0, {
                    "id": uid(),
                    "supplier": supplier.strip(),
                    "date": pdate.isoformat(),
                    "purchase_id": purchase_id,
                    "invoice": invoice.strip(),
                    "total": float(total_gasto or 0),
                    "paid": 0.0,
                    "due_date": due.isoformat() if due else None,
                    "notes": (categoria.strip() + " — " if categoria else "") + notes.strip(),
                })

            save_db(db)
            st.success("Gasto registrado. (No afecta inventario)")
            st.rerun()

    if db["purchases"]:
        st.markdown("### Historial de compras / gastos")
        st.dataframe(pd.DataFrame(db["purchases"]), use_container_width=True)
    else:
        st.info("Sin compras/gastos registrados.")

# ----------------- Ventas -----------------
with tabs[2]:
    st.subheader("Ventas (salidas)")
    options = [f"{p['name']} — Stock {p.get('stock',0)}" for p in db["inventory"]]
    item_name = st.selectbox("Producto", options=["Selecciona..."] + options)

    with st.form("sale_form", clear_on_submit=True):
        c1, c2, c3 = st.columns([2,1,1])
        selected = None
        if item_name != "Selecciona...":
            selected = options.index(item_name)

        quantity = c2.number_input("Cantidad", min_value=1, step=1, value=1)
        unit_price = c3.number_input("Precio unit.", min_value=0.0, step=1000.0, value=0.0, format="%.0f")

        c4, c5, c6 = st.columns(3)
        payment = c4.selectbox("Pago", options=["Efectivo", "Transferencia", "Tarjeta", "Fiado"])
        customer = c5.text_input("Cliente (opcional)")
        sdate = c6.date_input("Fecha", value=date.today())
        notes = st.text_input("Notas")

        # Checkbox de Inversionista (hereda por defecto del producto)
        default_inv = False
        if selected is not None:
            prod = db["inventory"][selected]
            default_inv = bool(prod.get("inv", False))
        inv_flag_sale = st.checkbox("Contar esta venta para inversionista", value=default_inv,
                                    help="Si está marcado, la utilidad de esta venta cuenta para el inversionista.")

        phone, due = None, None
        if payment == "Fiado":
            c7, c8 = st.columns(2)
            phone = c7.text_input("Teléfono")
            due = c8.date_input("Vence", value=date.today())

        ok = st.form_submit_button("Registrar venta")
        if ok:
            if selected is None:
                st.error("Selecciona un producto.")
            else:
                prod = db["inventory"][selected]
                qty = int(quantity)
                if prod.get("stock",0) < qty:
                    st.error("Stock insuficiente.")
                else:
                    price = float(unit_price or prod.get("price", 0))
                    sale = {
                        "id": uid(), "date": sdate.isoformat(), "item_id": prod["id"],
                        "quantity": qty, "unit_price": price, "customer": customer,
                        "payment": payment, "notes": notes,
                        "inv": bool(inv_flag_sale)  # guardamos la marca a nivel de venta
                    }
                    db["sales"].insert(0, sale)
                    _sync_safe(db, sync_sale, db, sale)

                    prod["stock"] = int(prod.get("stock",0)) - qty

                    if payment == "Fiado":
                        credit = {
                            "id": uid(), "customer": customer or "Cliente", "sale_id": sale["id"],
                            "date": sdate.isoformat(), "total": qty * price, "paid": 0.0,
                            "due_date": due.isoformat() if isinstance(due, date) else None,
                            "phone": phone or "", "notes": "",
                        }
                        db["credits"].insert(0, credit)

                    save_db(db)
                    st.success("Venta registrada.")
                    st.rerun()

    if db["sales"]:
        st.dataframe(pd.DataFrame(db["sales"]), use_container_width=True)
    else:
        st.info("Sin ventas registradas.")

# ----------------- Fiados (clientes) -----------------
with tabs[3]:
    st.subheader("Créditos/Fiados")

    per_customer = defaultdict(lambda: {"total": 0.0, "paid": 0.0})
    for c in db["credits"]:
        cust = (c.get("customer") or "Cliente").strip()
        per_customer[cust]["total"] += float(c.get("total", 0))
        per_customer[cust]["paid"] += float(c.get("paid", 0))

    resumen = []
    for cust, vals in per_customer.items():
        saldo = vals["total"] - vals["paid"]
        if saldo > 0 or vals["total"] > 0:
            resumen.append({"cliente": cust, "total": vals["total"], "pagado": vals["paid"], "saldo": saldo})
    resumen.sort(key=lambda r: (-r["saldo"], r["cliente"].lower() if isinstance(r["cliente"], str) else ""))

    if resumen:
        st.markdown("### Resumen por cliente")
        st.dataframe(pd.DataFrame(resumen), use_container_width=True)
    else:
        st.info("No hay créditos registrados todavía.")

    st.markdown("---")
    st.markdown("### Registrar abono por cliente")
    
    if 'pdf_data' not in st.session_state:
        st.session_state.pdf_data = None
    if 'pdf_filename' not in st.session_state:
        st.session_state.pdf_filename = None

    if st.session_state.pdf_data:
        st.success("Abono aplicado. Puedes descargar el recibo a continuación.")
        st.download_button(
            "⬇️ Descargar recibo (PDF)",
            data=st.session_state.pdf_data,
            file_name=st.session_state.pdf_filename,
            mime="application/pdf",
        )
        st.session_state.pdf_data = None
        st.session_state.pdf_filename = None

    clientes = sorted(list(per_customer.keys()))
    if clientes:
        with st.form("credit_payment_form", clear_on_submit=True):
            c1, c2, c3 = st.columns([2,1,1])
            sel_customer = c1.selectbox("Cliente", options=clientes)
            abono = c2.number_input("Abono", min_value=0.0, step=1000.0, value=0.0, format="%.0f")
            fecha_abono = c3.date_input("Fecha", value=date.today())
            c4, c5 = st.columns([1,2])
            medio_abono = c4.selectbox("Medio del abono", options=["Efectivo", "Transferencia", "Tarjeta"])
            notas_abono = c5.text_input("Notas (opcional)")
            ok = st.form_submit_button("Registrar abono")
        
        if ok:
            monto = float(abono or 0)
            if monto > 0:
                before = sum(credit_saldo(c) for c in db["credits"]
                             if (c.get("customer","").strip().lower() == sel_customer.strip().lower()))
                snapshot = [
                    {"id": c["id"], "date": c.get("date",""), "saldo": credit_saldo(c)}
                    for c in db["credits"]
                    if (c.get("customer","").strip().lower() == sel_customer.strip().lower()) and credit_saldo(c) > 0
                ]
                applied = apply_customer_payment(db, sel_customer, monto, fecha_abono.isoformat(), notas_abono, medio_abono)
                after = sum(credit_saldo(c) for c in db["credits"]
                            if (c.get("customer","").strip().lower() == sel_customer.strip().lower()))

                breakdown = []
                for s in snapshot:
                    cnow = next((c for c in db["credits"] if c["id"] == s["id"]), None)
                    if cnow:
                        before_s = float(s["saldo"])
                        after_s = credit_saldo(cnow)
                        applied_s = max(0.0, before_s - after_s)
                        if applied_s > 0:
                            breakdown.append({
                                "id": s["id"], "date": s.get("date",""),
                                "applied": applied_s, "remaining": after_s
                            })

                rid = "RC-" + uid()[-8:]
                pdf_bytes = build_receipt_pdf(
                    db,
                    who_type="CLIENTE",
                    who_name=sel_customer,
                    receipt_id=rid,
                    date_str=fecha_abono.isoformat(),
                    amount=applied,
                    balance_before=before,
                    balance_after=after,
                    notes=notas_abono,
                    breakdown=breakdown
                )
                
                st.session_state.pdf_data = pdf_bytes
                st.session_state.pdf_filename = f"recibo_abono_cliente_{sel_customer}_{fecha_abono.isoformat()}.pdf"

                # Sincronizar último abono
                if db["credit_payments"]:
                    last_pay = db["credit_payments"][0]
                    _sync_safe(db, sync_credit_payment, db, last_pay)

                st.rerun()
            else:
                st.warning("No se aplicó el abono (monto 0 o cliente sin deudas abiertas).")

# ----------------- Inversionista -----------------
with tabs[4]:
    st.subheader("Inversionista")
    with st.form("inv_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        idate = c1.date_input("Fecha", value=date.today())
        itype = c2.selectbox("Tipo", options=["Aporte", "Retiro", "Utilidad"])
        amount = c3.number_input("Monto", min_value=0.0, step=1000.0, value=0.0, format="%.0f")
        notes = st.text_input("Notas")
        ok = st.form_submit_button("Registrar")
        if ok:
            db["investor"].insert(0, {"id": uid(), "date": idate.isoformat(), "type": itype, "amount": float(amount or 0), "notes": notes})
            save_db(db)
            st.success("Movimiento guardado.")
            st.rerun()
    if db["investor"]:
        st.dataframe(pd.DataFrame(db["investor"]), use_container_width=True)
    else:
        st.info("Sin movimientos.")

# ----------------- Reportes -----------------
with tabs[5]:
    st.subheader("Reportes rápidos")
    c1, c2 = st.columns(2)
    ffrom = c1.date_input("Desde", value=date.today().replace(day=1))
    fto = c2.date_input("Hasta", value=date.today())

    # Ventas en rango
    fsales = [s for s in db["sales"] if ffrom.isoformat() <= s["date"] <= fto.isoformat()]
    sales_total = sum(s["quantity"] * s["unit_price"] for s in fsales)

    # Costo total (todas las ventas del rango)
    cost_total = 0.0
    for s in fsales:
        prod = next((p for p in db["inventory"] if p["id"] == s["item_id"]), None)
        cost_total += s["quantity"] * float(prod["cost"] if prod else 0)
    profit = sales_total - cost_total

    # ======== Cálculo INVERSOR: Solo ventas marcadas inv ========
    def is_inv_sale(sale: dict) -> bool:
        """True si la venta está marcada inv=True; si es None, hereda del producto."""
        v = sale.get("inv", None)
        if v is True:
            return True
        if v is False:
            return False
        # hereda del producto
        prod = next((p for p in db["inventory"] if p["id"] == sale.get("item_id")), None)
        return bool(prod.get("inv")) if prod else False

    fsales_inv = [s for s in fsales if is_inv_sale(s)]
    sales_total_inv = sum(s["quantity"] * s["unit_price"] for s in fsales_inv)
    cost_total_inv = 0.0
    for s in fsales_inv:
        prod = next((p for p in db["inventory"] if p["id"] == s["item_id"]), None)
        cost_total_inv += s["quantity"] * float(prod["cost"] if prod else 0)
    profit_inv = sales_total_inv - cost_total_inv

    # Capital invertido: Aportes - Retiros
    aportes = sum(float(x.get("amount",0)) for x in db["investor"] if x.get("type") == "Aporte")
    retiros = sum(float(x.get("amount",0)) for x in db["investor"] if x.get("type") == "Retiro")
    capital_invertido = aportes - retiros

    investor_pct = db["settings"].get("investor_share", 50) / 100.0
    investor_cut = profit_inv * investor_pct

    m1, m2, m3 = st.columns(3)
    m1.metric("Ventas (rango)", cop(sales_total))
    m2.metric("Utilidad (rango)", cop(profit))
    m3.metric("Parte inversionista (según %)", cop(investor_cut))

    i1, i2, i3 = st.columns(3)
    i1.metric("Ventas INV (marcadas)", cop(sales_total_inv))
    i2.metric("Utilidad INV (aprox)", cop(profit_inv))
    i3.metric("% Inversionista", f"{int(investor_pct*100)}%")

    st.caption(f"Capital invertido (Aportes − Retiros): {cop(capital_invertido)}")

    st.markdown("#### Detalle de ventas en rango")
    st.dataframe(pd.DataFrame(fsales), use_container_width=True)

# ----------------- Importar / Exportar -----------------
with tabs[6]:
    st.subheader("Respaldos")
    c1, c2, _ = st.columns(3)
    if c1.download_button("⬇️ Descargar respaldo JSON", data=json.dumps(db, ensure_ascii=False, indent=2), file_name=f"magnus_parfum_backup_{today_iso()}.json", mime="application/json"):
        st.toast("Respaldo exportado.", icon="✅")
    up_json = c2.file_uploader("Subir JSON de respaldo", type=["json"], accept_multiple_files=False)
    if up_json is not None:
        try:
            imported = json.load(up_json)
            # asegurar migraciones al importar
            for p in imported.get("inventory", []):
                p.setdefault("inv", False)
            for s in imported.get("sales", []):
                s.setdefault("inv", None)
            st.session_state.db = imported
            save_db(imported)
            st.success("Respaldo importado correctamente.")
            st.rerun()
        except Exception as e:
            st.error(f"No se pudo importar: {e}")

    st.markdown("---")
    st.subheader("Importar desde Excel/CSV (tu archivo actual)")
    up = st.file_uploader("Sube tu Excel (.xlsx) o CSV", type=["xlsx", "csv"])
    kind = st.selectbox("¿Qué quieres importar?", ["Inventario", "Compras", "Ventas", "Créditos", "Inversionista"])
    if up is not None and st.button("Importar archivo"):
        try:
            if up.name.endswith(".csv"):
                df = pd.read_csv(up)
            else:
                try:
                    df = pd.read_excel(up, sheet_name="Inventario")
                except Exception:
                    df = pd.read_excel(up)

            cols_lower = {c.lower().strip(): c for c in df.columns}
            if kind == "Inventario":
                name_col = cols_lower.get("nombre") or cols_lower.get("name") or list(df.columns)[0]
                brand_col = cols_lower.get("marca") or cols_lower.get("brand")
                size_col = cols_lower.get("ml") or cols_lower.get("tamaño") or cols_lower.get("size") or cols_lower.get("size_ml")
                cost_col = cols_lower.get("costo") or cols_lower.get("cost")
                price_col = cols_lower.get("precio") or cols_lower.get("price")
                stock_col = cols_lower.get("stock") or cols_lower.get("cantidad")
                notes_col = cols_lower.get("notas") or cols_lower.get("notes")
                inv_col = cols_lower.get("inv")  # opcional

                imported = []
                for _, r in df.iterrows():
                    name = str(r.get(name_col, "")).strip()
                    if not name:
                        continue
                    imported.append({
                        "id": uid(),
                        "name": name,
                        "brand": str(r.get(brand_col, "")).strip() if brand_col else "",
                        "size_ml": int(pd.to_numeric(r.get(size_col, 0), errors="coerce") or 0) if size_col else 0,
                        "cost": float(pd.to_numeric(r.get(cost_col, 0), errors="coerce") or 0) if cost_col else 0.0,
                        "price": float(pd.to_numeric(r.get(price_col, 0), errors="coerce") or 0) if price_col else 0.0,
                        "stock": int(pd.to_numeric(r.get(stock_col, 0), errors="coerce") or 0) if stock_col else 0,
                        "notes": str(r.get(notes_col, "")).strip() if notes_col else "",
                        "inv": str(r.get(inv_col,"")).strip().lower() in ("si","sí","true","1","x") if inv_col else False,
                    })
                db["inventory"] = imported + db["inventory"]
                save_db(db)
                st.success(f"Importados {len(imported)} productos al inventario.")
                st.rerun()

            elif kind == "Compras":
                date_col = cols_lower.get("fecha") or cols_lower.get("date")
                prod_col = cols_lower.get("producto") or cols_lower.get("name") or cols_lower.get("nombre")
                qty_col = cols_lower.get("cantidad") or cols_lower.get("qty")
                cost_col = cols_lower.get("costo") or cols_lower.get("unit_cost") or cols_lower.get("costo unit.") or cols_lower.get("costo_unit")
                sup_col = cols_lower.get("proveedor") or cols_lower.get("supplier")
                notes_col = cols_lower.get("notas") or cols_lower.get("notes")

                for _, r in df.iterrows():
                    name = str(r.get(prod_col, "")).strip()
                    if not name:
                        continue
                    prod = next((p for p in db["inventory"] if p["name"].lower() == name.lower()), None)
                    if not prod:
                        prod = {"id": uid(), "name": name, "brand": "", "size_ml": 0, "cost": 0.0, "price": 0.0, "stock": 0, "notes": "", "inv": False}
                        db["inventory"].append(prod)
                    quantity = int(pd.to_numeric(r.get(qty_col, 0), errors="coerce") or 0)
                    unit_cost = float(pd.to_numeric(r.get(cost_col, 0), errors="coerce") or 0)
                    pdate = str(r.get(date_col, today_iso()))
                    db["purchases"].insert(0, {"id": uid(), "date": pdate, "item_id": prod["id"], "quantity": quantity, "unit_cost": unit_cost, "supplier": str(r.get(sup_col, "")), "notes": str(r.get(notes_col, ""))})
                    prod["stock"] = int(prod.get("stock",0)) + quantity
                    if unit_cost > 0:
                        prod["cost"] = unit_cost
                save_db(db)
                st.success("Compras importadas.")
                st.rerun()

            elif kind == "Ventas":
                date_col = cols_lower.get("fecha") or cols_lower.get("date")
                prod_col = cols_lower.get("producto") or cols_lower.get("name") or cols_lower.get("nombre")
                qty_col = cols_lower.get("cantidad") or cols_lower.get("qty")
                price_col = cols_lower.get("precio") or cols_lower.get("unit_price") or cols_lower.get("precio unit.") or cols_lower.get("precio_unit")
                cust_col = cols_lower.get("cliente") or cols_lower.get("customer")
                pay_col = cols_lower.get("pago") or cols_lower.get("payment")
                notes_col = cols_lower.get("notas") or cols_lower.get("notes")
                inv_col = cols_lower.get("inv")

                for _, r in df.iterrows():
                    name = str(r.get(prod_col, "")).strip()
                    if not name:
                        continue
                    prod = next((p for p in db["inventory"] if p["name"].lower() == name.lower()), None)
                    if not prod:
                        prod = {"id": uid(), "name": name, "brand": "", "size_ml": 0, "cost": 0.0, "price": 0.0, "stock": 0, "notes": "", "inv": False}
                        db["inventory"].append(prod)
                    quantity = int(pd.to_numeric(r.get(qty_col, 0), errors="coerce") or 0)
                    unit_price = float(pd.to_numeric(r.get(price_col, 0), errors="coerce") or 0)
                    sdate = str(r.get(date_col, today_iso()))
                    payment = str(r.get(pay_col, "Efectivo"))
                    customer = str(r.get(cust_col, ""))
                    notes = str(r.get(notes_col, ""))
                    sale = {
                        "id": uid(), "date": sdate, "item_id": prod["id"], "quantity": quantity,
                        "unit_price": unit_price, "customer": customer, "payment": payment,
                        "notes": notes,
                        "inv": (str(r.get(inv_col,"")).strip().lower() in ("si","sí","true","1","x")) if inv_col else None
                    }
                    db["sales"].insert(0, sale)
                    prod["stock"] = int(prod.get("stock",0)) - quantity
                    if "fiado" in payment.lower():
                        credit = {
                            "id": uid(), "customer": customer or "Cliente", "sale_id": sale["id"],
                            "date": sdate, "total": quantity * unit_price, "paid": 0.0,
                            "due_date": sdate, "phone": "", "notes": notes,
                        }
                        db["credits"].insert(0, credit)
                save_db(db)
                st.success("Ventas importadas.")
                st.rerun()

            elif kind == "Créditos":
                cust_col = cols_lower.get("cliente") or cols_lower.get("customer")
                total_col = cols_lower.get("total")
                paid_col = cols_lower.get("pagado") or cols_lower.get("paid")
                date_col = cols_lower.get("fecha") or cols_lower.get("date")
                due_col = cols_lower.get("vence") or cols_lower.get("due_date")
                notes_col = cols_lower.get("notas") or cols_lower.get("notes")
                phone_col = cols_lower.get("telefono") or cols_lower.get("phone")

                for _, r in df.iterrows():
                    cust = str(r.get(cust_col, "")).strip()
                    if not cust:
                        continue
                    db["credits"].insert(0, {
                        "id": uid(), "customer": cust, "sale_id": "",
                        "date": str(r.get(date_col, today_iso())),
                        "total": float(pd.to_numeric(r.get(total_col, 0), errors="coerce") or 0),
                        "paid": float(pd.to_numeric(r.get(paid_col, 0), errors="coerce") or 0),
                        "due_date": str(r.get(due_col, "")) or None,
                        "phone": str(r.get(phone_col, "")) or "",
                        "notes": str(r.get(notes_col, "")) or "",
                    })
                save_db(db)
                st.success("Créditos importados.")
                st.rerun()

            elif kind == "Inversionista":
                date_col = cols_lower.get("fecha") or cols_lower.get("date")
                type_col = cols_lower.get("tipo") or cols_lower.get("type")
                amount_col = cols_lower.get("monto") or cols_lower.get("amount")
                notes_col = cols_lower.get("notas") or cols_lower.get("notes")
                for _, r in df.iterrows():
                    db["investor"].insert(0, {
                        "id": uid(),
                        "date": str(r.get(date_col, today_iso())),
                        "type": str(r.get(type_col, "Aporte")),
                        "amount": float(pd.to_numeric(r.get(amount_col, 0), errors="coerce") or 0),
                        "notes": str(r.get(notes_col, "")),
                    })
                save_db(db)
                st.success("Movimientos de inversionista importados.")
                st.rerun()

            st.rerun()
        except Exception as e:
            st.error(f"Ocurrió un error al importar el archivo. Asegúrate de que las columnas tengan los nombres correctos: {e}")

# ----------------- Ajustes -----------------
with tabs[7]:
    st.subheader("Ajustes de la app")
    with st.form("settings_form"):
        currency = st.text_input("Símbolo de moneda (ej: COP, USD, €)", db["settings"].get("currency", "COP"))
        investor_share = st.number_input("Porcentaje de utilidad para el inversionista (%)", min_value=0, max_value=100, step=5, value=db["settings"].get("investor_share", 50))
        logo_file = st.file_uploader("Subir logo para recibos (PNG, JPG)", type=["png", "jpg"], accept_multiple_files=False)
        
        delete_logo_button = st.form_submit_button("Quitar logo actual")
        save_button = st.form_submit_button("Guardar ajustes")

        if delete_logo_button:
            db["settings"]["logo_b64"] = None
            save_db(db)
            st.success("El logo ha sido eliminado. Guardando ajustes.")
            st.rerun()
        
        if save_button:
            db["settings"]["currency"] = currency
            db["settings"]["investor_share"] = investor_share
            if logo_file:
                db["settings"]["logo_b64"] = base64.b64encode(logo_file.getvalue()).decode("utf-8")
            save_db(db)
            st.success("Ajustes guardados.")
            st.rerun()

    st.markdown("---")
    st.subheader("Google Sheets")

    service_email = _service_email_from_file()
    if service_email:
        st.info(f"Comparte tu Spreadsheet con **{service_email}** como *Editor*.")

    gs_in = st.text_input(
        "Spreadsheet ID o URL",
        value=db["settings"].get("gsheets_sheet_id", ""),
        help="Pega aquí el ID o la URL completa del documento de Google Sheets compartido con tu cuenta de servicio."
    )
    cgs1, cgs2 = st.columns([1,1])
    if cgs1.button("Guardar Spreadsheet"):
        db["settings"]["gsheets_sheet_id"] = gs_in.strip()
        save_db(db)
        st.success("Spreadsheet guardado.")
        st.rerun()
    if cgs2.button("Probar conexión"):
        try:
            ss = _open_ss(db)
            st.success(f"Conexión OK: {ss.title}")
            st.info("Las hojas se crean automáticamente al sincronizar (Inventario, Compras, Ventas, AbonosClientes, PagosProveedores).")
        except Exception as e:
            st.error(f"No se pudo abrir el Spreadsheet: {e}")

    st.markdown("#### Sincronización automática (beta)")
    sync_enabled = st.checkbox("Sincronizar automáticamente a Google Sheets", value=db["settings"].get("gsheets_sync", False))
    tabs_cfg = db["settings"].get("gsheets_tabs", {
        "Inventario": "Inventario",
        "Compras": "Compras",
        "Ventas": "Ventas",
        "AbonosClientes": "AbonosClientes",
        "PagosProveedores": "PagosProveedores"
    })

    cA, cB, cC = st.columns(3)
    tabs_cfg["Inventario"] = cA.text_input("Hoja Inventario", value=tabs_cfg.get("Inventario","Inventario"))
    tabs_cfg["Compras"] = cB.text_input("Hoja Compras", value=tabs_cfg.get("Compras","Compras"))
    tabs_cfg["Ventas"] = cC.text_input("Hoja Ventas", value=tabs_cfg.get("Ventas","Ventas"))
    cD, cE = st.columns(2)
    tabs_cfg["AbonosClientes"] = cD.text_input("Hoja Abonos Clientes", value=tabs_cfg.get("AbonosClientes","AbonosClientes"))
    tabs_cfg["PagosProveedores"] = cE.text_input("Hoja Pagos Proveedores", value=tabs_cfg.get("PagosProveedores","PagosProveedores"))

    c1, c2 = st.columns([1,1])
    if c1.button("Guardar configuración de sincronización"):
        db["settings"]["gsheets_sync"] = bool(sync_enabled)
        db["settings"]["gsheets_tabs"] = tabs_cfg
        save_db(db)
        st.success("Preferencias de sincronización guardadas.")
        st.rerun()

    if c2.button("Forzar sincronización ahora"):
        try:
            counts = sync_all_to_sheets(db)
            st.success(
                f"Sincronizado ✅ | Inventario: {counts['inventario']} | Compras: {counts['compras']} "
                f"| Ventas: {counts['ventas']} | AbonosClientes: {counts['abonos_clientes']} "
                f"| PagosProveedores: {counts['pagos_proveedores']}"
            )
            st.toast("Google Sheets actualizado.", icon="✅")
        except Exception as e:
            st.error(f"No se pudo sincronizar todo: {e}")

# ----------------- Proveedores -----------------
with tabs[8]:
    st.subheader("Deudas con proveedores")
    per_supplier = defaultdict(lambda: {"total": 0.0, "paid": 0.0})
    for c in db["supplier_credits"]:
        sup = (c.get("supplier") or "Proveedor").strip()
        per_supplier[sup]["total"] += float(c.get("total", 0))
        per_supplier[sup]["paid"] += float(c.get("paid", 0))

    resumen = []
    for sup, vals in per_supplier.items():
        saldo = vals["total"] - vals["paid"]
        if saldo > 0 or vals["total"] > 0:
            resumen.append({"proveedor": sup, "total": vals["total"], "pagado": vals["paid"], "saldo": saldo})
    resumen.sort(key=lambda r: (-r["saldo"], r["proveedor"].lower() if isinstance(r["proveedor"], str) else ""))

    if resumen:
        st.markdown("### Resumen por proveedor")
        st.dataframe(pd.DataFrame(resumen), use_container_width=True)
    else:
        st.info("No hay deudas con proveedores.")

    st.markdown("---")
    st.markdown("### Registrar pago a proveedor")
    
    if 'pdf_data_sup' not in st.session_state:
        st.session_state.pdf_data_sup = None
    if 'pdf_filename_sup' not in st.session_state:
        st.session_state.pdf_filename_sup = None

    if st.session_state.pdf_data_sup:
        st.success("Abono aplicado. Puedes descargar el recibo a continuación.")
        st.download_button(
            "⬇️ Descargar recibo (PDF)",
            data=st.session_state.pdf_data_sup,
            file_name=st.session_state.pdf_filename_sup,
            mime="application/pdf",
        )
        st.session_state.pdf_data_sup = None
        st.session_state.pdf_filename_sup = None

    suppliers = sorted(list(per_supplier.keys()))
    if suppliers:
        with st.form("supplier_payment_form", clear_on_submit=True):
            c1, c2, c3 = st.columns([2,1,1])
            sel_supplier = c1.selectbox("Proveedor", options=suppliers)
            abono = c2.number_input("Abono", min_value=0.0, step=1000.0, value=0.0, format="%.0f")
            fecha_abono = c3.date_input("Fecha", key="pago_sup_date", value=date.today())
            c4, c5 = st.columns([1,2])
            medio_pago_sup = c4.selectbox("Medio del pago", options=["Efectivo", "Transferencia", "Tarjeta"], key="medio_pago_sup")
            notas_abono = c5.text_input("Notas (opcional)", key="pago_sup_notes")
            ok = st.form_submit_button("Registrar pago")
            
        if ok:
            monto = float(abono or 0)
            if monto > 0:
                before = sum(supplier_credit_saldo(c) for c in db["supplier_credits"]
                             if (c.get("supplier","").strip().lower() == sel_supplier.strip().lower()))

                snapshot = [
                    {"id": c["id"], "date": c.get("date",""), "saldo": supplier_credit_saldo(c)}
                    for c in db["supplier_credits"]
                    if (c.get("supplier","").strip().lower() == sel_supplier.strip().lower()) and supplier_credit_saldo(c) > 0
                ]
                applied = apply_supplier_payment(db, sel_supplier, monto, fecha_abono.isoformat(), notas_abono, medio_pago_sup)
                after = sum(supplier_credit_saldo(c) for c in db["supplier_credits"]
                            if (c.get("supplier","").strip().lower() == sel_supplier.strip().lower()))

                breakdown = []
                for s in snapshot:
                    cnow = next((c for c in db["supplier_credits"] if c["id"] == s["id"]), None)
                    if cnow:
                        before_s = float(s["saldo"])
                        after_s = supplier_credit_saldo(cnow)
                        applied_s = max(0.0, before_s - after_s)
                        if applied_s > 0:
                            breakdown.append({
                                "id": s["id"], "date": s.get("date",""),
                                "applied": applied_s, "remaining": after_s
                            })

                rid = "RP-" + uid()[-8:]
                pdf_bytes = build_receipt_pdf(
                    db,
                    who_type="PROVEEDOR",
                    who_name=sel_supplier,
                    receipt_id=rid,
                    date_str=fecha_abono.isoformat(),
                    amount=applied,
                    balance_before=before,
                    balance_after=after,
                    notes=notas_abono,
                    breakdown=breakdown
                )
                
                st.session_state.pdf_data_sup = pdf_bytes
                st.session_state.pdf_filename_sup = f"recibo_pago_proveedor_{sel_supplier}_{fecha_abono.isoformat()}.pdf"

                # Sincronizar último pago a proveedor
                if db["supplier_payments"]:
                    last_sp = db["supplier_payments"][0]
                    _sync_safe(db, sync_supplier_payment, db, last_sp)

                st.rerun()
            else:
                st.warning("No se aplicó el pago (monto 0 o proveedor sin deudas abiertas).")

# ----------------- Caja y Bancos -----------------
with tabs[9]:
    st.subheader("Caja y Bancos")
    caja, banco = cash_bank_balances(db)

    c1, c2 = st.columns(2)
    c1.metric("Caja (efectivo) — actual", cop(caja))
    c2.metric("Banco — actual", cop(banco))
    st.caption("Se calcula SOLO con abonos de clientes, ventas, compras al contado y pagos a proveedores, según el medio de pago.")

    st.markdown("### Libro diario de movimientos")
    movs = _movements_ledger(db)
    if movs:
        df_movs = pd.DataFrame(movs)
        df_movs = df_movs.sort_values("fecha")
        st.dataframe(df_movs, use_container_width=True)
    else:
        st.info("Aún no hay movimientos.")
