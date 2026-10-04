import logging

from markupsafe import Markup

from odoo import SUPERUSER_ID, _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

COUNT_ONLY_GROUP = "toruq_barcode.group_barcode_count_only"
MANAGER_GROUP = "stock.group_stock_manager"


class StockQuant(models.Model):
    _inherit = "stock.quant"

    def _toruq_is_count_only_user(self):
        user = self.env.user
        return user.has_group(COUNT_ONLY_GROUP) and not user.has_group(MANAGER_GROUP)

    def _toruq_blocked_message(self):
        return _("الاعتماد النهائي للجرد للمدير فقط. تم إبلاغ المدير بطلبك.")

    def _toruq_notify_managers(self, line_count):
        """Send an inbox notification to inventory managers.

        Uses a separate cursor so the notification survives the rollback
        caused by the UserError raised right after.
        """
        counter_name = self.env.user.name
        try:
            with self.pool.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                managers = env.ref(MANAGER_GROUP).users.filtered("active")
                body = Markup("<p>%s</p><p>%s</p>") % (
                    _("الموظف %(name)s أنهى عدّ %(count)s سطر جرد وبانتظار اعتمادك.")
                    % {"name": counter_name, "count": line_count},
                    _("راجع: المخزون ← العمليات ← الجرد الفعلي، ثم اضغط تطبيق بعد المراجعة."),
                )
                for manager in managers:
                    env["res.partner"].browse(manager.partner_id.id).message_notify(
                        partner_ids=[manager.partner_id.id],
                        subject=_("جرد بانتظار الاعتماد"),
                        body=body,
                    )
        except Exception:  # never block the user because a notification failed
            _logger.exception("toruq_barcode: could not notify inventory managers")

    def action_apply_inventory(self):
        if self._toruq_is_count_only_user():
            self._toruq_notify_managers(len(self))
            raise UserError(self._toruq_blocked_message())
        return super().action_apply_inventory()

    def _apply_inventory(self):
        # Safety net for any other code path that applies the adjustment.
        if self._toruq_is_count_only_user():
            raise UserError(self._toruq_blocked_message())
        return super()._apply_inventory()
