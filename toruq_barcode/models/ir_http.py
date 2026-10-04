from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        res = super().session_info()
        res["toruq_barcode_count_only"] = self.env.user.has_group(
            "toruq_barcode.group_barcode_count_only"
        )
        return res
