import logging

from odoo import models

_logger = logging.getLogger(__name__)

COUNT_ONLY_GROUP = "toruq_barcode.group_barcode_count_only"
MANAGER_GROUP = "stock.group_stock_manager"


class StockQuantParts(models.Model):
    _inherit = "stock.quant"

    def _toruq_parts_user(self):
        user = self.env.user
        return user.has_group(COUNT_ONLY_GROUP) and not user.has_group(MANAGER_GROUP)

    def write(self, vals):
        if "inventory_quantity" in vals:
            Part = self.env["toruq.count.part"]
            if self._toruq_parts_user():
                # Each count-only user keeps his own part; the quant holds the total of all parts.
                result = True
                for quant in self:
                    total = Part._toruq_set(
                        quant, self.env.user.id, float(vals["inventory_quantity"] or 0.0)
                    )
                    new_vals = dict(vals, inventory_quantity=total)
                    result = super(StockQuantParts, quant).write(new_vals) and result
                return result
            # A manager sets the count directly: drop the per-user parts to avoid mixing.
            Part.sudo().search([("quant_id", "in", self.ids)]).unlink()
        return super().write(vals)

    def _read_format(self, fnames, load="_classic_read"):
        result = super()._read_format(fnames, load=load)
        try:
            if result and "inventory_quantity" in fnames and self._toruq_parts_user():
                # A count-only device only sees its own part, so it never continues on top of other devices.
                own = self.env["toruq.count.part"]._toruq_own(self.ids, self.env.user.id)
                for rec in result:
                    qty = own.get(rec.get("id"))
                    rec["inventory_quantity"] = qty or 0.0
                    if "inventory_quantity_set" in rec:
                        rec["inventory_quantity_set"] = qty is not None
                    if "inventory_diff_quantity" in rec and "quantity" in rec:
                        rec["inventory_diff_quantity"] = (qty or 0.0) - (rec["quantity"] or 0.0)
        except Exception:
            _logger.exception("toruq_barcode: could not mask the per-user count")
        return result
