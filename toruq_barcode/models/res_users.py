from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    toruq_warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="مخزن الفرع (مصدر التحويلات)",
        help="Warehouse this user sends stock from when starting a transfer in Barcode.",
    )
