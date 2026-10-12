from odoo import fields, models

EVENTS = [
    ("requested", "طلب جرد"),
    ("submitted", "إرسال للاعتماد"),
    ("applied", "اعتماد وتطبيق"),
    ("rejected", "رفض / تصفير"),
]


class ToruqCountLog(models.Model):
    _name = "toruq.count.log"
    _description = "Toruq inventory count log"
    _order = "id desc"

    date = fields.Datetime(string="التاريخ", default=fields.Datetime.now, readonly=True, index=True)
    event = fields.Selection(EVENTS, string="الحدث", required=True, index=True)
    product_id = fields.Many2one("product.product", string="المنتج", ondelete="set null", index=True)
    location_id = fields.Many2one("stock.location", string="الموقع", ondelete="set null")
    warehouse_id = fields.Many2one(
        "stock.warehouse", string="الفرع", related="location_id.warehouse_id", store=True
    )
    lot_id = fields.Many2one("stock.lot", string="الدفعة / التسلسل", ondelete="set null")
    user_id = fields.Many2one("res.users", string="المنفذ", ondelete="set null")
    counter_id = fields.Many2one("res.users", string="المكلّف بالجرد", ondelete="set null")
    requester_id = fields.Many2one("res.users", string="طالب الجرد", ondelete="set null")
    system_qty = fields.Float(string="كمية النظام", digits="Product Unit of Measure")
    counted_qty = fields.Float(string="الكمية المعدودة", digits="Product Unit of Measure")
    diff_qty = fields.Float(string="الفرق", digits="Product Unit of Measure")
    company_id = fields.Many2one("res.company", string="الشركة")
