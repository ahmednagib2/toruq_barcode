from odoo import _
from odoo.http import request

try:
    from odoo.addons.stock_barcode.controllers.stock_barcode import StockBarcodeController
except ImportError:  # older layout
    from odoo.addons.stock_barcode.controllers.main import StockBarcodeController


class ToruqStockBarcodeController(StockBarcodeController):

    def scan_from_main_menu(self, barcode, *args, **kwargs):
        if request.env.user.has_group("toruq_barcode.group_barcode_count_only"):
            return {
                "warning": _(
                    "Scanning from the home screen is disabled for your account. "
                    "Open 'Inventory Count' first."
                )
            }
        return super().scan_from_main_menu(barcode, *args, **kwargs)
