from odoo import _, http
from odoo.http import request

OPERATOR_GROUP = "toruq_barcode.group_barcode_transfer_operator"


class ToruqTransferController(http.Controller):

    def _source_warehouse(self):
        user = request.env.user
        if not user.has_group(OPERATOR_GROUP):
            return None, _("هذه الميزة غير مفعلة لحسابك.")
        warehouse = user.sudo().toruq_warehouse_id
        if not warehouse:
            return None, _("لم يتم تحديد مخزن الفرع لحسابك. اطلب من المدير ضبطه في بيانات المستخدم.")
        return warehouse, None

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
            "destinations": [{"id": w.id, "name": w.name} for w in others],
        }

    @http.route("/toruq_barcode/transfer/create", type="json", auth="user")
    def create(self, destination_id):
        warehouse, error = self._source_warehouse()
        if error:
            return {"error": error}
        dest = request.env["stock.warehouse"].sudo().browse(int(destination_id)).exists()
        if not dest or dest == warehouse or dest.company_id != warehouse.company_id:
            return {"error": _("الفرع المستلم غير صالح.")}
        picking_type = warehouse.int_type_id
        if not picking_type:
            return {"error": _("لا يوجد نوع تحويل داخلي لمخزن المصدر.")}
        picking = request.env["stock.picking"].create(
            {
                "picking_type_id": picking_type.id,
                "location_id": warehouse.lot_stock_id.id,
                "location_dest_id": dest.lot_stock_id.id,
                "origin": _("تحويل %(src)s إلى %(dst)s") % {"src": warehouse.name, "dst": dest.name},
            }
        )
        if hasattr(picking, "action_open_picking_client_action"):
            action = picking.action_open_picking_client_action()
        else:
            action = {
                "type": "ir.actions.client",
                "tag": "stock_barcode_picking_client_action",
                "target": "fullscreen",
                "context": {"active_id": picking.id},
                "params": {"model": "stock.picking", "picking_id": picking.id},
            }
        return {"action": action}
