# tabs/__init__.py
from .inventory import render_inventory
from .purchases import render_purchases
from .sales import render_sales
from .fiados import render_fiados
from .investor import render_investor
from .reports import render_reports
from .suppliers import render_suppliers
from .cash_bank import render_cash_bank
from .settings import render_settings

__all__ = [
    'render_inventory',
    'render_purchases',
    'render_sales',
    'render_fiados',
    'render_investor',
    'render_reports',
    'render_suppliers',
    'render_cash_bank',
    'render_settings'
]