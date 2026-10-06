from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .toruq_notify import toruq_notify

SENDER_GROUP = "toruq_barcode.group_barcode_transfer_operator"
RECEIVER_GROUP = "toruq_barcode.group_barcode_transfer_receiver"
MANAGER_GROUP = "stock.group_stock_manager"
GUARDED = {
    "toruq_flow", "toruq_link_id", "toruq_sender_id", "toruq_receiver_id", "toruq_courier",
    "toruq_src_warehouse_id", "toruq_dest_warehouse_id", "toruq_reject_reason",
}
EVENT_TITLES = {
    "dispatch": "إرسال بضاعة",
    "received": "استلام بضاعة",
    "rejected": "رفض بضاعة",
    "returned": "عودة بضاعة للمصدر",
}


class StockPicking(models.Model):
    _inherit = "stock.picking"

    toruq_flow = fields.Selection(
        [("none", "—"), ("out", "إرسال"), ("in", "استلام"), ("return", "عودة")],
        string="نوع حركة الفروع", default="none", copy=False, readonly=True,
    )
    toruq_link_id = fields.Many2one("stock.picking", string="السند المرتبط", copy=False, readonly=True)
    toruq_sender_id = fields.Many2one("res.users", string="المرسل", copy=False, readonly=True)
    toruq_receiver_id = fields.Many2one("res.users", string="المستلم", copy=False, readonly=True)
    toruq_courier = fields.Char(string="المندوب", copy=False, readonly=True)
    toruq_src_warehouse_id = fields.Many2one("stock.warehouse", string="من فرع", copy=False, readonly=True)
    toruq_dest_warehouse_id = fields.Many2one("stock.warehouse", string="إلى فرع", copy=False, readonly=True)
    toruq_reject_reason = fields.Text(string="سبب الرفض", copy=False, readonly=True)
    toruq_sender_attachment_ids = fields.Many2many(
        "ir.attachment", "toruq_picking_sender_att_rel", "picking_id", "attachment_id",
        string="فاتورة المرسل (اختياري)", copy=False,
    )
    toruq_receiver_attachment_ids = fields.Many2many(
        "ir.attachment", "toruq_picking_receiver_att_rel", "picking_id", "attachment_id",
        string="فاتورة المستلم (اختياري)", copy=False,
    )

    # ---------- guards ----------
    def _toruq_is_manager(self):
        return self.env.user.has_group(MANAGER_GROUP)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and not self._toruq_is_manager():
            vals_list = [{k: v for k, v in vals.items() if k not in GUARDED} for vals in vals_list]
        return super().create(vals_list)

    def write(self, vals):
        if GUARDED & set(vals) and not self.env.su and not self._toruq_is_manager():
            raise AccessError(_("لا تملك صلاحية تعديل بيانات حركة الفروع."))
        return super().write(vals)

    # ---------- helpers ----------
    def _toruq_notification(self, message, kind="success"):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"message": message, "type": kind, "sticky": False},
        }

    def _toruq_items_text(self, items):
        return "\n".join("%s: %s" % (product.display_name, qty) for product, qty in items)

    def _toruq_log(self, event, items=None, reason=None):
        self.ensure_one()
        detail = self._toruq_items_text(items or [])
        self.env["toruq.transfer.log"].sudo().create(
            {
                "event": event,
                "picking_id": self.id,
                "user_id": self.env.user.id,
                "src_warehouse_id": self.toruq_src_warehouse_id.id,
                "dest_warehouse_id": self.toruq_dest_warehouse_id.id,
                "courier": self.toruq_courier,
                "reason": reason,
                "detail": detail,
            }
        )
        head = "%s | من %s إلى %s | المندوب: %s | بواسطة %s" % (
            EVENT_TITLES.get(event, event),
            self.toruq_src_warehouse_id.name or "",
            self.toruq_dest_warehouse_id.name or "",
            self.toruq_courier or "-",
            self.env.user.name,
        )
        lines = [head] + detail.splitlines() + ([_("السبب: %s") % reason] if reason else [])
        body = Markup("<br/>").join(Markup("%s") % line for line in lines)
        for pick in self | self.toruq_link_id:
            pick.sudo().message_post(body=body)

    def _toruq_raw_validate(self, **ctx):
        """Standard Odoo validation, bypassing this module's override."""
        return super(StockPicking, self.with_context(**ctx)).button_validate()

    # ---------- validate entry point ----------
    def button_validate(self):
        ours = self.filtered(lambda p: p.toruq_flow in ("out", "in", "return"))
        if not ours:
            return super().button_validate()
        res = True
        for pick in ours:
            res = pick._toruq_validate_one()
        others = self - ours
        if others:
            res = super(StockPicking, others).button_validate()
        return res

    def _toruq_validate_one(self):
        self.ensure_one()
        user = self.env.user
        manager = self._toruq_is_manager()
        if self.toruq_flow == "out":
            if user != self.toruq_sender_id and not manager:
                raise AccessError(_("هذا التحويل خاص بمرسل آخر."))
            res = self._toruq_raw_validate()
            if self.state == "done":
                self._toruq_after_dispatch()
                return self._toruq_notification(_("تم إخراج البضاعة وإرسال إشعار للمستلم."))
            return res
        if self.toruq_flow == "in":
            return self._toruq_receive_flow()
        if not manager:
            raise AccessError(_("هذه الحركة تتم تلقائيًا."))
        return self._toruq_raw_validate()

    # ---------- dispatch ----------
    def _toruq_after_dispatch(self):
        self.ensure_one()
        if self.toruq_link_id:
            return
        dest = self.toruq_dest_warehouse_id
        moves = self.sudo().move_ids.filtered(lambda m: m.state == "done" and m.quantity > 0)
        if not moves:
            return
        transit = self.location_dest_id
        receipt = self.env["stock.picking"].sudo().create(
            {
                "picking_type_id": dest.int_type_id.id,
                "location_id": transit.id,
                "location_dest_id": dest.lot_stock_id.id,
                "origin": self.name,
                "toruq_flow": "in",
                "toruq_link_id": self.id,
                "toruq_sender_id": self.toruq_sender_id.id,
                "toruq_receiver_id": self.toruq_receiver_id.id,
                "toruq_courier": self.toruq_courier,
                "toruq_src_warehouse_id": self.toruq_src_warehouse_id.id,
                "toruq_dest_warehouse_id": dest.id,
                "move_ids": [
                    (0, 0, {
                        "name": m.product_id.display_name,
                        "product_id": m.product_id.id,
                        "product_uom_qty": m.quantity,
                        "product_uom": m.product_uom.id,
                        "location_id": transit.id,
                        "location_dest_id": dest.lot_stock_id.id,
                    })
                    for m in moves
                ],
            }
        )
        receipt.action_confirm()
        receipt.action_assign()
        self.sudo().write({"toruq_link_id": receipt.id})
        items = [(m.product_id, m.quantity) for m in moves]
        self._toruq_log("dispatch", items)
        text = _("%(sender)s أرسل لك %(count)s منتج من %(src)s (المندوب: %(courier)s). افتح «استلام تحويل» للمقارنة.") % {
            "sender": self.env.user.name,
            "count": len(items),
            "src": self.toruq_src_warehouse_id.name,
            "courier": self.toruq_courier or "-",
        }
        toruq_notify(self.env, self.toruq_receiver_id, _("بضاعة وارد إليك من فرع"), text)

    # ---------- receive ----------
    def _toruq_check_receiver(self):
        self.ensure_one()
        if self.toruq_flow != "in":
            raise UserError(_("هذا ليس سند استلام."))
        if self.env.user != self.toruq_receiver_id and not self._toruq_is_manager():
            raise AccessError(_("الاستلام للمستلم المحدد فقط."))

    def _toruq_compute(self):
        self.ensure_one()
        any_picked = any(self.move_line_ids.mapped("picked"))
        rows = []
        for move in self.move_ids:
            lines = move.move_line_ids
            if any_picked:
                lines = lines.filtered("picked")
            received = sum(lines.mapped("quantity"))
            if received > move.product_uom_qty + 1e-6:
                raise UserError(_("الكمية المستلمة من %s أكبر من المرسلة.") % move.product_id.display_name)
            rows.append(
                {"move": move, "lines": lines, "received": received,
                 "shortage": max(move.product_uom_qty - received, 0.0)}
            )
        return rows

    def action_toruq_accept_all(self):
        for pick in self:
            pick._toruq_check_receiver()
            if pick.state in ("done", "cancel"):
                continue
            pick.move_line_ids.sudo().write({"picked": True})
            if any(row["shortage"] for row in pick._toruq_compute()):
                raise UserError(_("الكمية المحجوزة أقل من المرسلة؛ استخدم تأكيد الاستلام بعد مراجعة الكميات."))
            pick._toruq_finalize_receive(None)
        return True

    def action_toruq_confirm_receive(self):
        return self.button_validate()

    def _toruq_receive_flow(self):
        self.ensure_one()
        self._toruq_check_receiver()
        if any(row["shortage"] for row in self._toruq_compute()):
            return {
                "type": "ir.actions.act_window",
                "res_model": "toruq.receive.wizard",
                "view_mode": "form",
                "target": "new",
                "context": {"default_picking_id": self.id},
            }
        return self._toruq_finalize_receive(None)

    def _toruq_finalize_receive(self, reason):
        self.ensure_one()
        self._toruq_check_receiver()
        rows = self._toruq_compute()
        shortages = [(r["move"].product_id, r["shortage"]) for r in rows if r["shortage"] > 0]
        accepted = [(r["move"].product_id, r["received"]) for r in rows if r["received"] > 0]
        if shortages and not (reason or "").strip():
            raise UserError(_("اكتب سبب الرفض."))
        pick = self.sudo()
        for row in rows:
            (row["move"].move_line_ids - row["lines"]).sudo().unlink()
            row["lines"].sudo().write({"picked": True})
        if accepted:
            res = pick._toruq_raw_validate(
                skip_backorder=True, picking_ids_not_to_backorder=pick.ids,
                skip_sms=True, skip_immediate=True,
            )
            if pick.state != "done":
                return res if isinstance(res, dict) else self._toruq_notification(_("تعذر إتمام الاستلام."), "danger")
        else:
            pick.action_cancel()
        if shortages:
            pick.write({"toruq_reject_reason": reason})
        if accepted:
            self._toruq_log("received", accepted)
        if shortages:
            self._toruq_log("rejected", shortages, reason)
            self._toruq_return_shortages(shortages, reason)
        text = _("%(name)s استلم %(ok)s منتج ورفض %(bad)s. %(reason)s") % {
            "name": self.env.user.name, "ok": len(accepted), "bad": len(shortages),
            "reason": ("السبب: %s" % reason) if shortages else "",
        }
        toruq_notify(self.env, self.toruq_sender_id, _("نتيجة استلام التحويل"), text)
        return self._toruq_notification(_("تم تسجيل الاستلام."))

    def _toruq_return_shortages(self, shortages, reason):
        self.ensure_one()
        src = self.toruq_src_warehouse_id
        transit = self.location_id
        ret = self.env["stock.picking"].sudo().create(
            {
                "picking_type_id": src.int_type_id.id,
                "location_id": transit.id,
                "location_dest_id": src.lot_stock_id.id,
                "origin": _("مرتجع %s") % self.name,
                "toruq_flow": "return",
                "toruq_link_id": self.id,
                "toruq_sender_id": self.toruq_sender_id.id,
                "toruq_receiver_id": self.toruq_receiver_id.id,
                "toruq_courier": self.toruq_courier,
                "toruq_src_warehouse_id": src.id,
                "toruq_dest_warehouse_id": self.toruq_dest_warehouse_id.id,
                "toruq_reject_reason": reason,
                "move_ids": [
                    (0, 0, {
                        "name": product.display_name,
                        "product_id": product.id,
                        "product_uom_qty": qty,
                        "product_uom": product.uom_id.id,
                        "location_id": transit.id,
                        "location_dest_id": src.lot_stock_id.id,
                    })
                    for product, qty in shortages
                ],
            }
        )
        ret.action_confirm()
        ret.action_assign()
        ret.move_line_ids.write({"picked": True})
        ret._toruq_raw_validate(skip_backorder=True, skip_sms=True, skip_immediate=True)
        if ret.state == "done":
            ret._toruq_log("returned", shortages, reason)
