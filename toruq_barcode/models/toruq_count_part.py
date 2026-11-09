from odoo import api, fields, models


class ToruqCountPart(models.Model):
    _name = "toruq.count.part"
    _description = "Toruq count contribution of one user on one quant"

    quant_id = fields.Many2one("stock.quant", required=True, ondelete="cascade", index=True)
    user_id = fields.Many2one("res.users", required=True, ondelete="cascade", index=True)
    qty = fields.Float(string="الكمية", digits="Product Unit of Measure")

    _sql_constraints = [
        ("quant_user_uniq", "unique(quant_id, user_id)", "One part per user and quant."),
    ]

    @api.model
    def _toruq_set(self, quant, user_id, qty):
        """Store the user's own count and return the total of all users on this quant."""
        Part = self.sudo()
        part = Part.search([("quant_id", "=", quant.id), ("user_id", "=", user_id)], limit=1)
        if part:
            part.qty = qty
        else:
            Part.create({"quant_id": quant.id, "user_id": user_id, "qty": qty})
        return sum(Part.search([("quant_id", "=", quant.id)]).mapped("qty"))

    @api.model
    def _toruq_own(self, quant_ids, user_id):
        parts = self.sudo().search([("quant_id", "in", quant_ids), ("user_id", "=", user_id)])
        return {p.quant_id.id: p.qty for p in parts}
