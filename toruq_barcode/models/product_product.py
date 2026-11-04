from odoo import api, models
from odoo.osv import expression

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def _tokens(operator, value):
    if operator in ("ilike", "like") and isinstance(value, str):
        tokens = value.translate(_AR_DIGITS).split()
        if len(tokens) > 1:
            return tokens
    return None


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def _search_display_name(self, operator, value):
        tokens = _tokens(operator, value)
        if not tokens:
            return super()._search_display_name(operator, value)
        domains = []
        for token in tokens:
            domains.append(super()._search_display_name(operator, token))
        return expression.AND(domains)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model
    def _search_display_name(self, operator, value):
        tokens = _tokens(operator, value)
        if not tokens:
            return super()._search_display_name(operator, value)
        domains = []
        for token in tokens:
            domains.append(super()._search_display_name(operator, token))
        return expression.AND(domains)
