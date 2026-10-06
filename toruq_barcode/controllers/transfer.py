from odoo import _, http
from odoo.http import request

SENDER_GROUP = "toruq_barcode.group_barcode_transfer_operator"
RECEIVER_GROUP = "toruq_barcode.group_barcode_transfer_receiver"


class ToruqTransferController(http.Controller):

    def _source_warehouse(self):
        user = request.env.user
        if not user.has_group(SENDER_GROUP):
            return None, _("هذه الميزة غير مفعلة لحسابك.")
        warehouse = user.sudo().toruq_warehouse_id
        if not warehouse:
            return None, _("لم يتم تحديد مخزن الفرع لحسابك. اطلب من المدير ضبطه في بيانات المستخدم.")
        return warehouse, None

    def _receivers(self, warehouse):
        users = request.env["res.users"].sudo().search(
            [("toruq_warehouse_id", "=", warehouse.id), ("share", "=", False)]
        )
        return users.filtered(lambda u: u.has_group(RECEIVER_GROUP))

    def _open_action(self, picking):
        if hasattr(picking, "action_open_picking_client_action"):
            return picking.action_open_picking_client_action()
        return {
            "type": "ir.actions.client",
            "tag": "stock_barcode_picking_client_action",
            "target": "fullscreen",
            "context": {"active_id": picking.id},
            "params": {"model": "stock.picking", "picking_id": picking.id},
        }

    @http.route("/toruq_barcode/transfer/destinations", type="json", auth="user")
    def destinations(self):
        warehouse, error = self._source_warehouse()
        if error:
            return {"error": error}
        others = request.env["stock.warehouse"].sudo().search(
            [("company_id", "=", warehouse.company_id.id), ("id", "!=", warehouse.id)]
        )
        return {
            "source": {"id": warehouse.id, "name": warehouse.name},
            "destinations": [
                {
                    "id": w.id,
                    "name": w.name,
                    "receivers": [{"id": u.id, "name": u.name} for u in self._receivers(w)],
                }
                for w in others
            ],
        }

    @http.route("/toruq_barcode/transfer/create", type="json", auth="user")
    def create(self, destination_id, receiver_id, courier=""):
        warehouse, error = self._source_warehouse()
        if error:
            return {"error": error}
        dest = request.env["stock.warehouse"].sudo().browse(int(destination_id)).exists()
        if not dest or dest == warehouse or dest.company_id != warehouse.company_id:
            return {"error": _("الفرع المستلم غير صالح.")}
        receiver = self._receivers(dest).filtered(lambda u: u.id == int(receiver_id))
        if not receiver:
            return {"error": _("المستلم غير صالح لهذا الفرع.")}
        company = warehouse.company_id
        transit = company.internal_transit_location_id
        if not transit:
            transit = request.env["stock.location"].sudo().search(
                [("usage", "=", "transit"), ("company_id", "in", [company.id, False])], limit=1
            )
        if not transit or not warehouse.int_type_id:
            return {"error": _("إعداد موقع العبور أو نوع التحويل الداخلي غير مكتمل.")}
        picking = request.env["stock.picking"].sudo().create(
            {
                "picking_type_id": warehouse.int_type_id.id,
                "location_id": warehouse.lot_stock_id.id,
                "location_dest_id": transit.id,
                "origin": _("تحويل %(src)s إلى %(dst)s") % {"src": warehouse.name, "dst": dest.name},
                "toruq_flow": "out",
                "toruq_sender_id": request.env.user.id,
                "toruq_receiver_id": receiver.id,
                "toruq_courier": (courier or "").strip(),
                "toruq_src_warehouse_id": warehouse.id,
                "toruq_dest_warehouse_id": dest.id,
            }
        )
        return {"action": self._open_action(picking)}

    @http.route("/toruq_barcode/transfer/incoming", type="json", auth="user")
    def incoming(self):
        user = request.env.user
        if not user.has_group(RECEIVER_GROUP):
            return {"error": _("هذه الميزة غير مفعلة لحسابك.")}
        pickings = request.env["stock.picking"].sudo().search(
            [
                ("toruq_flow", "=", "in"),
                ("toruq_receiver_id", "=", user.id),
                ("state", "not in", ("done", "cancel")),
            ],
            order="id desc",
        )
        return {
            "pickings": [
                {
                    "id": p.id,
                    "name": p.name,
                    "from": p.toruq_src_warehouse_id.name or "",
                    "sender": p.toruq_sender_id.name or "",
                    "courier": p.toruq_courier or "",
                    "lines": len(p.move_ids),
                }
                for p in pickings
            ]
        }

    @http.route("/toruq_barcode/transfer/open", type="json", auth="user")
    def open(self, picking_id):
        user = request.env.user
        picking = request.env["stock.picking"].sudo().browse(int(picking_id)).exists()
        if not picking or picking.toruq_flow != "in" or picking.toruq_receiver_id != user:
            return {"error": _("هذا السند غير مخصص لك.")}
        return {"action": self._open_action(picking)}
