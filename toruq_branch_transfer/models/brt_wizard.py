from odoo import _, api, fields, models
from odoo.exceptions import UserError


class BrtSignWizard(models.TransientModel):
    _name = "brt.sign.wizard"
    _description = "Branch transfer e-signature"

    picking_id = fields.Many2one("stock.picking", required=True, readonly=True)
    mode = fields.Selection([("send", "إرسال"), ("receive", "استلام")], required=True, readonly=True)
    signer_name = fields.Char(string="اسم الموقّع", default=lambda self: self.env.user.name, readonly=True)
    summary = fields.Text(string="ملخص", compute="_compute_summary")
    has_shortage = fields.Boolean(compute="_compute_summary")
    reason = fields.Text(string="سبب رفض غير الواصل", default="لم يصلني")
    signature = fields.Binary(string="التوقيع")

    @api.depends("picking_id", "mode")
    def _compute_summary(self):
        for wizard in self:
            lines, shortage = [], False
            pick = wizard.picking_id
            if pick and wizard.mode == "receive":
                for row in pick._brt_compute():
                    shortage = shortage or row["shortage"] > 0
                    lines.append(
                        "%s | مرسل: %s | مستلم: %s | مرفوض: %s"
                        % (row["move"].product_id.display_name, row["move"].product_uom_qty,
                           row["received"], row["shortage"])
                    )
            elif pick:
                for move in pick.move_ids:
                    lines.append("%s | الكمية: %s" % (move.product_id.display_name, move.product_uom_qty or move.quantity))
            wizard.summary = "\n".join(lines)
            wizard.has_shortage = shortage

    def action_confirm(self):
        self.ensure_one()
        if not self.signature:
            raise UserError(_("التوقيع الإلكتروني مطلوب."))
        return self.picking_id._brt_signed_action(self.mode, self.signature, self.reason)
