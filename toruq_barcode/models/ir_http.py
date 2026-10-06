from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        res = super().session_info()
        user = self.env.user
        count_only = user.has_group("toruq_barcode.group_barcode_count_only")
        res["toruq_barcode_count_only"] = count_only
        res["toruq_barcode_flags"] = {
            "uid": user.id,
            "count_only": count_only,
            "hide_scanner": user.has_group("toruq_barcode.group_barcode_hide_scanner"),
            "guided": user.has_group("toruq_barcode.group_barcode_guided_count"),
        }
        return res
