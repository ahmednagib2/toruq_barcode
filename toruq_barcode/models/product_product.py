from odoo import api, fields, models
from odoo.osv import expression

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def _split(value):
    return str(value or "").translate(_AR_DIGITS).split()


def _tokens(operator, value):
    if operator in ("ilike", "like") and isinstance(value, str):
        tokens = _split(value)
        if len(tokens) > 1:
            return tokens
    return None


class ProductProduct(models.Model):
    _inherit = "product.product"

    toruq_multi_search = fields.Char(
        string="Product Search (Toruq)",
        compute="_compute_toruq_multi_search",
        search="_search_toruq_multi",
    )

    def _compute_toruq_multi_search(self):
        for rec in self:
            rec.toruq_multi_search = False

    @api.model
    def _search_toruq_multi(self, operator, value):
        domains = []
        for token in _split(value):
            domains.append(
                [
                    "|",
                    "|",
                    ("name", "ilike", token),
                    ("default_code", "ilike", token),
                    ("barcode", "ilike", token),
                ]
            )
        return expression.AND(domains) if domains else []

    @api.model
    def _name_search(self, name, domain=None, operator="ilike", limit=None, order=None):
        # many2one autocomplete (order lines, etc.): every typed word must match, any order
        tokens = _tokens(operator, name)
        if not tokens:
            return super()._name_search(
                name, domain=domain, operator=operator, limit=limit, order=order
            )
        partner_id = self.env.context.get("partner_id")
        use_sellers = bool(partner_id) and self.env["ir.model.access"].check(
            "product.supplierinfo", "read", False
        )
        token_domains = []
        for token in tokens:
            leaves = [
                ("name", "ilike", token),
                ("default_code", "ilike", token),
                ("barcode", "ilike", token),
            ]
            if use_sellers:
                leaves.append(
                    (
                        "seller_ids",
                        "any",
                        [
                            ("partner_id", "=", partner_id),
                            "|",
                            ("product_name", "ilike", token),
                            ("product_code", "ilike", token),
                        ],
                    )
                )
            token_domains.append(expression.OR([[leaf] for leaf in leaves]))
        full_domain = expression.AND([list(domain or [])] + token_domains)
        return self._search(full_domain, limit=limit, order=order)

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

    toruq_multi_search = fields.Char(
        string="Product Search (Toruq)",
        compute="_compute_toruq_multi_search",
        search="_search_toruq_multi",
    )

    def _compute_toruq_multi_search(self):
        for rec in self:
            rec.toruq_multi_search = False

    @api.model
    def _search_toruq_multi(self, operator, value):
        domains = []
        for token in _split(value):
            domains.append(
                [
                    "|",
                    "|",
                    "|",
                    ("name", "ilike", token),
                    ("default_code", "ilike", token),
                    ("product_variant_ids.default_code", "ilike", token),
                    ("product_variant_ids.barcode", "ilike", token),
                ]
            )
        return expression.AND(domains) if domains else []

    @api.model
    def _search_display_name(self, operator, value):
        tokens = _tokens(operator, value)
        if not tokens:
            return super()._search_display_name(operator, value)
        domains = []
        for token in tokens:
            domains.append(super()._search_display_name(operator, token))
        return expression.AND(domains)
