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

    def _toruq_log_vals(self, event):
        """Values for toruq.count.log, one per quant (call on a sudo recordset)."""
        actor = self.env.user.id
        company = self.env.company.id
        return [
            {
                "event": event,
                "product_id": q.product_id.id,
                "location_id": q.location_id.id,
                "lot_id": q.lot_id.id or False,
                "user_id": actor,
                "counter_id": q.user_id.id or False,
                "requester_id": q.toruq_requester_id.id or False,
                "system_qty": q.quantity,
                "counted_qty": q.inventory_quantity,
                "diff_qty": q.inventory_diff_quantity,
                "company_id": q.company_id.id or company,
            }
            for q in self
        ]

    def _toruq_log_in_new_cursor(self, vals):
        """Persist log rows even when the current transaction is rolled back by a UserError."""
        if not vals:
            return
        try:
            with self.pool.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                env["toruq.count.log"].create(vals)
        except Exception:
            _logger.exception("toruq_barcode: could not write count log")

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
                    _("راجع: المخزون ← التقارير ← لوحة الجرد، أو المخزون ← العمليات ← الجرد الفعلي."),
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
            quants = self.sudo().filtered("inventory_quantity_set") or self.sudo()
            log_vals = quants._toruq_log_vals("submitted")
            self._toruq_notify_approvers()
            self._toruq_log_in_new_cursor(log_vals)
            raise UserError(self._toruq_blocked_message())
        return super().action_apply_inventory()

    def _apply_inventory(self):
        # Safety net for any other code path that applies the adjustment.
        if self._toruq_is_count_only_user():
            raise UserError(self._toruq_blocked_message())
        log_vals = self.sudo().filtered("inventory_quantity_set")._toruq_log_vals("applied")
        res = super()._apply_inventory()
        if log_vals:
            self.env["toruq.count.log"].sudo().create(log_vals)
        return res

    def action_clear_inventory_quantity(self):
        # Only the dashboard reject button passes toruq_reject, to avoid logging internal clears.
        log_vals = []
        if self.env.context.get("toruq_reject"):
            log_vals = self.sudo().filtered("inventory_quantity_set")._toruq_log_vals("rejected")
        res = super().action_clear_inventory_quantity()
        if log_vals:
            self.env["toruq.count.log"].sudo().create(log_vals)
        return res
