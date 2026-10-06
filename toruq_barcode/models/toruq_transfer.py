from odoo import api, fields, models


class ToruqTransferLog(models.Model):
    _name = "toruq.transfer.log"
    _description = "Toruq branch transfer log"
    _order = "id desc"

    date = fields.Datetime(string="التاريخ", default=fields.Datetime.now, readonly=True)
    event = fields.Selection(
        [
            ("dispatch", "إرسال"),
            ("received", "استلام"),
            ("rejected", "رفض"),
            ("returned", "عودة للمصدر"),
            ("cancelled", "إلغاء"),
        ],
        string="الحدث",
        required=True,
    )
    picking_id = fields.Many2one("stock.picking", string="التحويل")
    user_id = fields.Many2one("res.users", string="المنفذ", default=lambda self: self.env.user)
    src_warehouse_id = fields.Many2one("stock.warehouse", string="من فرع")
    dest_warehouse_id = fields.Many2one("stock.warehouse", string="إلى فرع")
    courier = fields.Char(string="المندوب")
    reason = fields.Text(string="السبب")
    detail = fields.Text(string="التفاصيل")


class ToruqReceiveWizard(models.TransientModel):
    _name = "toruq.receive.wizard"
    _description = "Toruq receive confirmation"

    picking_id = fields.Many2one("stock.picking", required=True, readonly=True)
    summary = fields.Text(string="المقارنة", compute="_compute_summary")
    reason = fields.Text(string="سبب الرفض", default="لم يصلني", required=True)

    @api.depends("picking_id")
    def _compute_summary(self):
        for wizard in self:
            lines = []
            if wizard.picking_id:
                for row in wizard.picking_id._toruq_compute():
                    move = row["move"]
                    lines.append(
                        "%s | مرسل: %s | مستلم: %s | مرفوض: %s"
                        % (move.product_id.display_name, move.product_uom_qty, row["received"], row["shortage"])
                    )
            wizard.summary = "\n".join(lines)

    def action_confirm(self):
        self.ensure_one()
        return self.picking_id._toruq_finalize_receive(self.reason)
