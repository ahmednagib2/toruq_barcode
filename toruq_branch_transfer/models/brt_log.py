from odoo import fields, models


class BrtTransferLog(models.Model):
    _name = "brt.transfer.log"
    _description = "Branch transfer log"
    _order = "id desc"

    date = fields.Datetime(string="التاريخ", default=fields.Datetime.now, readonly=True)
    event = fields.Selection(
        [("dispatch", "إرسال"), ("received", "استلام"), ("rejected", "رفض"), ("returned", "عودة للمصدر")],
        string="الحدث", required=True,
    )
    picking_id = fields.Many2one("stock.picking", string="التحويل")
    user_id = fields.Many2one("res.users", string="المنفذ", default=lambda self: self.env.user)
    src_warehouse_id = fields.Many2one("stock.warehouse", string="من فرع")
    dest_warehouse_id = fields.Many2one("stock.warehouse", string="إلى فرع")
    courier = fields.Char(string="المندوب")
    reason = fields.Text(string="السبب")
    detail = fields.Text(string="الأصناف والكميات")
    qty = fields.Float(string="إجمالي الكمية")
    lines = fields.Integer(string="عدد الأصناف")
    signed = fields.Boolean(string="موقّع إلكترونيًا")
