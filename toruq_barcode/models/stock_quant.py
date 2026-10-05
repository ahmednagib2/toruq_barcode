import logging

from markupsafe import Markup

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

COUNT_ONLY_GROUP = "toruq_barcode.group_barcode_count_only"
MANAGER_GROUP = "stock.group_stock_manager"


class StockQuant(models.Model):
    _inherit = "stock.quant"

    toruq_requester_id = fields.Many2one(
        "res.users",
        string="Count requested by",
        copy=False,
        readonly=True,
        help="User who assigned this count (set when a non count-only user sets the counter).",
    )

    def _toruq_is_count_only_user(self):
        user = self.env.user
        return user.has_group(COUNT_ONLY_GROUP) and not user.has_group(MANAGER_GROUP)

    def _toruq_blocked_message(self):
        return _("الاعتماد النهائي للجرد لمن طلبه أو لمدير المخزون. تم إرسال طلب الموافقة له.")

    def write(self, vals):
        # Remember who assigned the counter (Odoo does not store the requester).
        set_requester = bool(vals.get("user_id")) and not self._toruq_is_count_only_user()
        res = super().write(vals)
        if set_requester:
            self.sudo().with_context(inventory_mode=False).write(
                {"toruq_requester_id": self.env.user.id}
            )
        return res

    def _toruq_notify_approvers(self):
        """Pop-up (+ inbox message) to whoever requested the count.

        Falls back to all inventory managers when no requester is recorded.
        Runs in a separate cursor so it survives the rollback caused by the
        UserError raised right after.
        """
        counter_name = self.env.user.name
        line_count = len(self)
        quants = self.sudo()
        requester_ids = set(quants.mapped("toruq_requester_id").ids)
        has_unassigned = any(not q.toruq_requester_id for q in quants)
        try:
            with self.pool.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                target_ids = set(requester_ids)
                if has_unassigned or not target_ids:
                    target_ids |= set(env.ref(MANAGER_GROUP).users.filtered("active").ids)
                users = env["res.users"].browse(list(target_ids)).filtered("active")
                title = _("طلب جرد بانتظار موافقتك")
                text = _("%(name)s أرسل جرد %(count)s منتج ويحتاج موافقتك.") % {
                    "name": counter_name,
                    "count": line_count,
                }
                body = Markup("<p>%s</p><p>%s</p>") % (
                    text,
                    _("راجع: المخزون ← العمليات ← الجرد الفعلي، ثم اضغط تطبيق بعد المراجعة."),
                )
                for user in users:
                    partner = user.partner_id
                    env["bus.bus"]._sendone(
                        partner,
                        "simple_notification",
                        {"title": title, "message": text, "type": "warning", "sticky": True},
                    )
                    partner.message_notify(
                        partner_ids=[partner.id], subject=title, body=body
                    )
        except Exception:  # never block the user because a notification failed
            _logger.exception("toruq_barcode: could not notify approvers")

    def action_apply_inventory(self):
        if self._toruq_is_count_only_user():
            self._toruq_notify_approvers()
            raise UserError(self._toruq_blocked_message())
        return super().action_apply_inventory()

    def _apply_inventory(self):
        # Safety net for any other code path that applies the adjustment.
        if self._toruq_is_count_only_user():
            raise UserError(self._toruq_blocked_message())
        return super()._apply_inventory()
