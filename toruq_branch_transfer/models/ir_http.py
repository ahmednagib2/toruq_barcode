from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        res = super().session_info()
        routes = self.env["brt.route"].sudo()
        user = self.env.user
        res["brt_flags"] = {
            "sender": bool(routes.search_count([("sender_id", "=", user.id)])),
            "receiver": bool(routes.search_count([("receiver_ids", "in", user.id)])),
        }
        return res
