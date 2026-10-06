from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class BrtRoute(models.Model):
    _name = "brt.route"
    _description = "Branch transfer route"
    _order = "sender_id, src_warehouse_id, dest_warehouse_id"

    name = fields.Char(compute="_compute_name", store=True)
    sender_id = fields.Many2one("res.users", string="المرسل", required=True, domain=[("share", "=", False)])
    src_warehouse_id = fields.Many2one("stock.warehouse", string="من فرع", required=True)
    dest_warehouse_id = fields.Many2one("stock.warehouse", string="إلى فرع", required=True)
    receiver_ids = fields.Many2many(
        "res.users", "brt_route_receiver_rel", "route_id", "user_id",
        string="المستلمون المسموحون", domain=[("share", "=", False)],
    )
    active = fields.Boolean(default=True)
    note = fields.Char(string="ملاحظات")

    _sql_constraints = [
        ("brt_route_unique", "unique(sender_id, src_warehouse_id, dest_warehouse_id)",
         "هذا المسار مسجل مسبقًا لنفس المرسل."),
    ]

    @api.depends("sender_id", "src_warehouse_id", "dest_warehouse_id")
    def _compute_name(self):
        for route in self:
            route.name = "%s: %s ← %s" % (
                route.sender_id.name or "", route.src_warehouse_id.name or "", route.dest_warehouse_id.name or "",
            )

    @api.constrains("src_warehouse_id", "dest_warehouse_id", "receiver_ids")
    def _check_route(self):
        for route in self:
            if route.src_warehouse_id == route.dest_warehouse_id:
                raise ValidationError(_("الفرع المرسل والمستلم لا بد أن يختلفا."))
            if route.src_warehouse_id.company_id != route.dest_warehouse_id.company_id:
                raise ValidationError(_("الفرعان لا بد أن يكونا في نفس الشركة."))
            if not route.receiver_ids:
                raise ValidationError(_("حدّد مستلمًا واحدًا على الأقل."))

    def _grant_group(self):
        group = self.env.ref("toruq_branch_transfer.group_brt_user")
        users = (self.mapped("sender_id") | self.mapped("receiver_ids")).sudo()
        users.write({"groups_id": [(4, group.id)]})

    @api.model_create_multi
    def create(self, vals_list):
        routes = super().create(vals_list)
        routes._grant_group()
        return routes

    def write(self, vals):
        res = super().write(vals)
        self._grant_group()
        return res
