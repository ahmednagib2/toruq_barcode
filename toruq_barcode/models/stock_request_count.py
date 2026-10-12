from odoo import models

COUNT_ONLY_GROUP = "toruq_barcode.group_barcode_count_only"
MANAGER_GROUP = "stock.group_stock_manager"


class StockRequestCount(models.TransientModel):
    _inherit = "stock.request.count"

    def action_request_count(self):
        res = super().action_request_count()
        user = self.env.user
        restricted = user.has_group(COUNT_ONLY_GROUP) and not user.has_group(MANAGER_GROUP)
        if not restricted:
            for wizard in self:
                if wizard.user_id:
                    quants = wizard._get_quants_to_count().sudo()
                    quants.with_context(inventory_mode=False).write(
                        {"toruq_requester_id": user.id}
                    )
                    vals = quants._toruq_log_vals("requested")
                    if vals:
                        self.env["toruq.count.log"].sudo().create(vals)
        return res
