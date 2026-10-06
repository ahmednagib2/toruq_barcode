from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError

from .toruq_notify import toruq_notify

OPERATOR_GROUP = "toruq_barcode.group_barcode_transfer_operator"
APPROVER_GROUP = "toruq_barcode.group_barcode_transfer_approver"
MANAGER_GROUP = "stock.group_stock_manager"
GUARDED_FIELDS = {"toruq_approval_state", "toruq_requested_by", "toruq_approver_id"}


class StockPicking(models.Model):
    _inherit = "stock.picking"

    toruq_approval_state = fields.Selection(
        [
            ("none", "بدون"),
            ("requested", "بانتظار الاعتماد"),
            ("approved", "معتمد"),
            ("rejected", "مرفوض"),
        ],
        string="حالة الاعتماد",
        default="none",
        copy=False,
        tracking=True,
    )
    toruq_requested_by = fields.Many2one("res.users", string="طلب بواسطة", copy=False, readonly=True)
    toruq_approver_id = fields.Many2one("res.users", string="اعتمد بواسطة", copy=False, readonly=True)

    # ---------- helpers ----------
    def _toruq_is_approver(self):
        user = self.env.user
        return user.has_group(APPROVER_GROUP) or user.has_group(MANAGER_GROUP)

    def _toruq_is_operator(self):
        return self.env.user.has_group(OPERATOR_GROUP) and not self._toruq_is_approver()

    def _toruq_approvers(self):
        users = self.env.ref(APPROVER_GROUP).sudo().users.filtered("active")
        return users or self.env.ref(MANAGER_GROUP).sudo().users.filtered("active")

    def _toruq_notification(self, message, kind="success"):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"message": message, "type": kind, "sticky": False},
        }

    def write(self, vals):
        if GUARDED_FIELDS & set(vals) and not self.env.su and not self._toruq_is_approver():
            raise AccessError(_("لا تملك صلاحية تعديل حالة اعتماد التحويل."))
        return super().write(vals)

    # ---------- operator: send for approval ----------
    def action_toruq_request_approval(self):
        pickings = self.filtered(
            lambda p: p.picking_type_code == "internal"
            and p.state not in ("done", "cancel")
            and p.toruq_approval_state in ("none", "rejected")
        )
        for picking in pickings:
            if not (picking.move_ids or picking.move_line_ids):
                raise UserError(_("لا توجد منتجات في التحويل %s.") % picking.display_name)
        approvers = self._toruq_approvers()
        if pickings and not approvers:
            raise UserError(_("لم يتم تحديد معتمد للتحويلات. اطلب من المدير تفعيل مجموعة معتمد التحويلات لأحد المستخدمين."))
        pickings.sudo().write(
            {"toruq_approval_state": "requested", "toruq_requested_by": self.env.user.id}
        )
        for picking in pickings:
            picking.sudo().message_post(body=_("تم إرسال التحويل للاعتماد بواسطة %s.") % self.env.user.name)
            text = _("%(user)s أرسل التحويل %(name)s من %(src)s إلى %(dst)s ويحتاج موافقتك.") % {
                "user": self.env.user.name,
                "name": picking.display_name,
                "src": picking.sudo().location_id.display_name,
                "dst": picking.sudo().location_dest_id.display_name,
            }
            toruq_notify(self.env, approvers, _("تحويل مخزون بانتظار موافقتك"), text)
        return True

    # operator pressing Validate (Barcode or form) = send for approval
    def button_validate(self):
        if self._toruq_is_operator():
            if any(p.picking_type_code != "internal" for p in self):
                raise UserError(_("غير مسموح لك بتأكيد هذه العملية."))
            self.action_toruq_request_approval()
            return self._toruq_notification(
                _("تم إرسال التحويل للمحاسب للاعتماد. ستنتقل البضاعة بعد موافقته.")
            )
        return super().button_validate()

    # ---------- approver ----------
    def action_toruq_approve(self):
        if not self._toruq_is_approver():
            raise AccessError(_("الاعتماد للمعتمد أو لمدير المخزون فقط."))
        for picking in self:
            if picking.toruq_approval_state != "requested":
                raise UserError(_("التحويل %s ليس بانتظار الاعتماد.") % picking.display_name)
        drafts = self.filtered(lambda p: p.state == "draft")
        if drafts:
            drafts.sudo().action_confirm()
        for picking in self:
            if not any(picking.move_line_ids.mapped("quantity")):
                raise UserError(_("لا توجد كميات ممسوحة في التحويل %s.") % picking.display_name)
        res = self.sudo().with_context(
            skip_backorder=True, skip_sms=True, skip_immediate=True
        ).button_validate()
        done = self.filtered(lambda p: p.state == "done")
        if done:
            done.sudo().write(
                {"toruq_approval_state": "approved", "toruq_approver_id": self.env.user.id}
            )
            for picking in done:
                if picking.toruq_requested_by:
                    toruq_notify(
                        self.env,
                        picking.toruq_requested_by,
                        _("تم اعتماد التحويل"),
                        _("تم اعتماد التحويل %(name)s ونقل الكميات إلى %(dst)s.")
                        % {"name": picking.display_name, "dst": picking.sudo().location_dest_id.display_name},
                    )
        if isinstance(res, dict):
            return res
        return True

    def action_toruq_reject(self):
        if not self._toruq_is_approver():
            raise AccessError(_("الرفض للمعتمد أو لمدير المخزون فقط."))
        pickings = self.filtered(lambda p: p.toruq_approval_state == "requested")
        pickings.sudo().write({"toruq_approval_state": "rejected", "toruq_approver_id": self.env.user.id})
        for picking in pickings:
            picking.sudo().message_post(body=_("تم رفض التحويل بواسطة %s.") % self.env.user.name)
            if picking.toruq_requested_by:
                toruq_notify(
                    self.env,
                    picking.toruq_requested_by,
                    _("تم رفض التحويل"),
                    _("تم رفض التحويل %s. عدّله وأعد إرساله.") % picking.display_name,
                )
        return True
