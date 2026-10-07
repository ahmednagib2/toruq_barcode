from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .brt_notify import brt_notify

MANAGER_GROUP = "stock.group_stock_manager"
GUARDED = {
    "brt_flow", "brt_route_id", "brt_link_id", "brt_sender_id", "brt_receiver_id", "brt_courier",
    "brt_src_warehouse_id", "brt_dest_warehouse_id", "brt_reject_reason",
    "brt_sender_signature", "brt_sender_signed_by", "brt_sender_signed_at",
    "brt_receiver_signature", "brt_receiver_signed_by", "brt_receiver_signed_at",
}
EVENT_TITLES = {
    "dispatch": "إرسال بضاعة",
    "received": "استلام بضاعة",
    "rejected": "رفض بضاعة",
    "returned": "عودة بضاعة للمصدر",
}


class StockPicking(models.Model):
    _inherit = "stock.picking"

    brt_flow = fields.Selection(
        [("none", "—"), ("out", "إرسال"), ("in", "استلام"), ("return", "عودة")],
        string="حركة الفروع", default="none", copy=False, readonly=True,
    )
    brt_route_id = fields.Many2one("brt.route", copy=False, readonly=True)
    brt_link_id = fields.Many2one("stock.picking", string="السند المرتبط", copy=False, readonly=True)
    brt_sender_id = fields.Many2one("res.users", string="المرسل", copy=False, readonly=True)
    brt_receiver_id = fields.Many2one("res.users", string="المستلم", copy=False, readonly=True)
    brt_courier = fields.Char(string="المندوب", copy=False, readonly=True)
    brt_src_warehouse_id = fields.Many2one("stock.warehouse", string="من فرع", copy=False, readonly=True)
    brt_dest_warehouse_id = fields.Many2one("stock.warehouse", string="إلى فرع", copy=False, readonly=True)
    brt_reject_reason = fields.Text(string="سبب الرفض", copy=False, readonly=True)
    brt_sender_signature = fields.Binary(string="توقيع المرسل", attachment=True, copy=False, readonly=True)
    brt_sender_signed_by = fields.Many2one("res.users", string="وقّع المرسل", copy=False, readonly=True)
    brt_sender_signed_at = fields.Datetime(string="وقت توقيع المرسل", copy=False, readonly=True)
    brt_receiver_signature = fields.Binary(string="توقيع المستلم", attachment=True, copy=False, readonly=True)
    brt_receiver_signed_by = fields.Many2one("res.users", string="وقّع المستلم", copy=False, readonly=True)
    brt_receiver_signed_at = fields.Datetime(string="وقت توقيع المستلم", copy=False, readonly=True)
    brt_sender_attachment_ids = fields.Many2many(
        "ir.attachment", "brt_picking_sender_att_rel", "picking_id", "attachment_id",
        string="فاتورة المرسل (اختياري)", copy=False,
    )
    brt_receiver_attachment_ids = fields.Many2many(
        "ir.attachment", "brt_picking_receiver_att_rel", "picking_id", "attachment_id",
        string="فاتورة المستلم (اختياري)", copy=False,
    )

    # ---------- guards ----------
    def _brt_is_manager(self):
        return self.env.user.has_group(MANAGER_GROUP)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and not self._brt_is_manager():
            vals_list = [{k: v for k, v in vals.items() if k not in GUARDED} for vals in vals_list]
        return super().create(vals_list)

    def write(self, vals):
        if GUARDED & set(vals) and not self.env.su and not self._brt_is_manager():
            raise AccessError(_("لا تملك صلاحية تعديل بيانات حركة الفروع."))
        return super().write(vals)

    @api.constrains("location_id", "location_dest_id", "picking_type_id")
    def _brt_check_direct_interbranch(self):
        """Optional (system parameter brt.block_direct_interbranch = 1)."""
        if self.env.su or self._brt_is_manager():
            return
        if self.env["ir.config_parameter"].sudo().get_param("brt.block_direct_interbranch") != "1":
            return
        for pick in self:
            if pick.brt_flow != "none" or pick.picking_type_code != "internal":
                continue
            src = pick.location_id.warehouse_id
            dst = pick.location_dest_id.warehouse_id
            if src and dst and src != dst:
                raise ValidationError(_("التحويل المباشر بين الفروع غير مسموح. استخدم «ابدأ بتحويل المخزون»."))

    # ---------- helpers ----------
    def _brt_notification(self, message, kind="success"):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"message": message, "type": kind, "sticky": False},
        }

    def _brt_wizard(self, mode):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("التوقيع الإلكتروني"),
            "res_model": "brt.sign.wizard",
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
            "context": {"default_picking_id": self.id, "default_mode": mode},
        }

    def _brt_log(self, event, items=None, reason=None, signed=True):
        self.ensure_one()
        items = items or []
        detail = "\n".join("%s: %s" % (product.display_name, qty) for product, qty in items)
        self.env["brt.transfer.log"].sudo().create(
            {
                "event": event,
                "picking_id": self.id,
                "user_id": self.env.user.id,
                "src_warehouse_id": self.brt_src_warehouse_id.id,
                "dest_warehouse_id": self.brt_dest_warehouse_id.id,
                "courier": self.brt_courier,
                "reason": reason,
                "detail": detail,
                "qty": sum(qty for _p, qty in items),
                "lines": len(items),
                "signed": signed,
            }
        )
        head = "%s | من %s إلى %s | المندوب: %s | بواسطة %s" % (
            EVENT_TITLES.get(event, event),
            self.brt_src_warehouse_id.name or "",
            self.brt_dest_warehouse_id.name or "",
            self.brt_courier or "-",
            self.env.user.name,
        )
        lines = [head] + detail.splitlines() + ([_("السبب: %s") % reason] if reason else [])
        body = Markup("<br/>").join(Markup("%s") % line for line in lines)
        for pick in self | self.brt_link_id:
            pick.sudo().message_post(body=body)

    def _brt_raw_validate(self, **ctx):
        """Standard Odoo validation, bypassing this module's override."""
        return super(StockPicking, self.with_context(**ctx)).button_validate()

    # ---------- validate entry point ----------
    def button_validate(self):
        ours = self.filtered(lambda p: p.brt_flow in ("out", "in", "return"))
        if not ours:
            return super().button_validate()
        res = True
        for pick in ours:
            res = pick._brt_validate_one()
        others = self - ours
        if others:
            res = super(StockPicking, others).button_validate()
        return res

    def _brt_check_sender(self):
        self.ensure_one()
        if self.brt_flow != "out":
            raise UserError(_("هذا ليس سند إرسال."))
        if self.env.user != self.brt_sender_id and not self._brt_is_manager():
            raise AccessError(_("هذا التحويل خاص بمرسل آخر."))

    def _brt_check_receiver(self):
        self.ensure_one()
        if self.brt_flow != "in":
            raise UserError(_("هذا ليس سند استلام."))
        if self.env.user != self.brt_receiver_id and not self._brt_is_manager():
            raise AccessError(_("الاستلام للمستلم المحدد فقط."))

    def _brt_validate_one(self):
        self.ensure_one()
        if self.brt_flow == "out":
            self._brt_check_sender()
            if not self.brt_sender_signature:
                return self._brt_wizard("send")
            return self._brt_do_dispatch()
        if self.brt_flow == "in":
            self._brt_check_receiver()
            return self._brt_wizard("receive")
        if not self._brt_is_manager():
            raise AccessError(_("هذه الحركة تتم تلقائيًا."))
        return self._brt_raw_validate()

    def _brt_signed_action(self, mode, signature, reason):
        self.ensure_one()
        values = lambda who: {  # noqa: E731
            "brt_%s_signature" % who: signature,
            "brt_%s_signed_by" % who: self.env.user.id,
            "brt_%s_signed_at" % who: fields.Datetime.now(),
        }
        if mode == "send":
            self._brt_check_sender()
            self.sudo().write(values("sender"))
            return self._brt_do_dispatch()
        self._brt_check_receiver()
        self.sudo().write(values("receiver"))
        return self._brt_finalize_receive(reason)

    # ---------- dispatch ----------
    def _brt_do_dispatch(self):
        self.ensure_one()
        res = self._brt_raw_validate()
        if self.state == "done":
            self._brt_after_dispatch()
            return self._brt_notification(_("تم توقيع وإخراج البضاعة وإرسال إشعار للمستلم."))
        return res

    def _brt_after_dispatch(self):
        self.ensure_one()
        if self.brt_link_id:
            return
        dest = self.brt_dest_warehouse_id
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
                "brt_flow": "in",
                "brt_route_id": self.brt_route_id.id,
                "brt_link_id": self.id,
                "brt_sender_id": self.brt_sender_id.id,
                "brt_receiver_id": self.brt_receiver_id.id,
                "brt_courier": self.brt_courier,
                "brt_src_warehouse_id": self.brt_src_warehouse_id.id,
                "brt_dest_warehouse_id": dest.id,
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
        self.sudo().write({"brt_link_id": receipt.id})
        items = [(m.product_id, m.quantity) for m in moves]
        self._brt_log("dispatch", items)
        text = _("%(sender)s أرسل لك %(count)s منتج من %(src)s (المندوب: %(courier)s). افتح «استلام تحويل وارد» للمقارنة والتوقيع.") % {
            "sender": self.env.user.name,
            "count": len(items),
            "src": self.brt_src_warehouse_id.name,
            "courier": self.brt_courier or "-",
        }
        brt_notify(self.env, self.brt_receiver_id, _("بضاعة وارد إليك من فرع"), text)

    # ---------- receive ----------
    def _brt_compute(self):
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

    def action_brt_accept_all(self):
        self.ensure_one()
        self._brt_check_receiver()
        if self.state in ("done", "cancel"):
            return True
        self.move_line_ids.sudo().write({"picked": True})
        return self._brt_wizard("receive")

    def action_brt_confirm_receive(self):
        self.ensure_one()
        self._brt_check_receiver()
        return self._brt_wizard("receive")

    def _brt_finalize_receive(self, reason):
        self.ensure_one()
        self._brt_check_receiver()
        rows = self._brt_compute()
        shortages = [(r["move"].product_id, r["shortage"]) for r in rows if r["shortage"] > 0]
        accepted = [(r["move"].product_id, r["received"]) for r in rows if r["received"] > 0]
        if shortages and not (reason or "").strip():
            raise UserError(_("اكتب سبب الرفض."))
        pick = self.sudo()
        for row in rows:
            (row["move"].move_line_ids - row["lines"]).sudo().unlink()
            row["lines"].sudo().write({"picked": True})
        if accepted:
            res = pick._brt_raw_validate(
                skip_backorder=True, picking_ids_not_to_backorder=pick.ids,
                skip_sms=True, skip_immediate=True,
            )
            if pick.state != "done":
                return res if isinstance(res, dict) else self._brt_notification(_("تعذر إتمام الاستلام."), "danger")
        else:
            pick.action_cancel()
        if shortages:
            pick.write({"brt_reject_reason": reason})
        if accepted:
            self._brt_log("received", accepted)
        if shortages:
            self._brt_log("rejected", shortages, reason)
            self._brt_return_shortages(shortages, reason)
        text = _("%(name)s وقّع استلام %(ok)s منتج ورفض %(bad)s. %(reason)s") % {
            "name": self.env.user.name, "ok": len(accepted), "bad": len(shortages),
            "reason": ("السبب: %s" % reason) if shortages else "",
        }
        brt_notify(self.env, self.brt_sender_id, _("نتيجة استلام التحويل"), text)
        return self._brt_notification(_("تم توقيع الاستلام وتسجيله."))

    def _brt_return_shortages(self, shortages, reason):
        self.ensure_one()
        src = self.brt_src_warehouse_id
        transit = self.location_id
        ret = self.env["stock.picking"].sudo().create(
            {
                "picking_type_id": src.int_type_id.id,
                "location_id": transit.id,
                "location_dest_id": src.lot_stock_id.id,
                "origin": _("مرتجع %s") % self.name,
                "brt_flow": "return",
                "brt_route_id": self.brt_route_id.id,
                "brt_link_id": self.id,
                "brt_sender_id": self.brt_sender_id.id,
                "brt_receiver_id": self.brt_receiver_id.id,
                "brt_courier": self.brt_courier,
                "brt_src_warehouse_id": src.id,
                "brt_dest_warehouse_id": self.brt_dest_warehouse_id.id,
                "brt_reject_reason": reason,
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
        ret._brt_raw_validate(skip_backorder=True, skip_sms=True, skip_immediate=True)
        if ret.state == "done":
            ret._brt_log("returned", shortages, reason, signed=False)
