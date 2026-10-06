from odoo import _, http
from odoo.http import request


class BrtTransferController(http.Controller):

    def _routes(self):
        return request.env["brt.route"].sudo().search(
            [("sender_id", "=", request.env.user.id), ("active", "=", True)]
        )

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

    @http.route("/brt/routes", type="json", auth="user")
    def routes(self):
        routes = self._routes()
        if not routes:
            return {"error": _("لا يوجد مسار تحويل مسجل لك. اطلب من المدير إضافته.")}
        return {
            "routes": [
                {
                    "id": r.id,
                    "src": r.src_warehouse_id.name,
                    "dst": r.dest_warehouse_id.name,
                    "receivers": [{"id": u.id, "name": u.name} for u in r.receiver_ids.filtered("active")],
                }
                for r in routes
            ]
        }

    @http.route("/brt/create", type="json", auth="user")
    def create(self, route_id, receiver_id, courier=""):
        route = self._routes().filtered(lambda r: r.id == int(route_id))
        if not route:
            return {"error": _("هذا المسار غير مسموح لك.")}
        receiver = route.receiver_ids.filtered(lambda u: u.id == int(receiver_id) and u.active)
        if not receiver:
            return {"error": _("المستلم غير مسموح في هذا المسار.")}
        src, dest = route.src_warehouse_id, route.dest_warehouse_id
        company = src.company_id
        transit = company.internal_transit_location_id
        if not transit:
            transit = request.env["stock.location"].sudo().search(
                [("usage", "=", "transit"), ("company_id", "in", [company.id, False])], limit=1
            )
        if not transit or not src.int_type_id:
            return {"error": _("إعداد موقع العبور أو نوع التحويل الداخلي غير مكتمل.")}
        picking = request.env["stock.picking"].sudo().create(
            {
                "picking_type_id": src.int_type_id.id,
                "location_id": src.lot_stock_id.id,
                "location_dest_id": transit.id,
                "origin": _("تحويل %(src)s إلى %(dst)s") % {"src": src.name, "dst": dest.name},
                "brt_flow": "out",
                "brt_route_id": route.id,
                "brt_sender_id": request.env.user.id,
                "brt_receiver_id": receiver.id,
                "brt_courier": (courier or "").strip(),
                "brt_src_warehouse_id": src.id,
                "brt_dest_warehouse_id": dest.id,
            }
        )
        return {"action": self._open_action(picking)}

    @http.route("/brt/incoming", type="json", auth="user")
    def incoming(self):
        user = request.env.user
        pickings = request.env["stock.picking"].sudo().search(
            [("brt_flow", "=", "in"), ("brt_receiver_id", "=", user.id), ("state", "not in", ("done", "cancel"))],
            order="id desc",
        )
        return {
            "pickings": [
                {
                    "id": p.id,
                    "name": p.name,
                    "from": p.brt_src_warehouse_id.name or "",
                    "sender": p.brt_sender_id.name or "",
                    "courier": p.brt_courier or "",
                    "lines": len(p.move_ids),
                }
                for p in pickings
            ]
        }

    @http.route("/brt/open", type="json", auth="user")
    def open(self, picking_id):
        picking = request.env["stock.picking"].sudo().browse(int(picking_id)).exists()
        if not picking or picking.brt_flow != "in" or picking.brt_receiver_id != request.env.user:
            return {"error": _("هذا السند غير مخصص لك.")}
        return {"action": self._open_action(picking)}
