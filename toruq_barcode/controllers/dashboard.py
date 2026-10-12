from odoo import fields, http
from odoo.exceptions import AccessError
from odoo.http import request

MANAGER_GROUP = "stock.group_stock_manager"
COUNT_ONLY_GROUP = "toruq_barcode.group_barcode_count_only"
LIMIT = 50


def _num(value):
    return round(value or 0.0, 2)


class ToruqCountDashboard(http.Controller):

    @http.route("/toruq/count_dashboard", type="json", auth="user")
    def dashboard(self, warehouse_id=None):
        """Manager-only data for the inventory dashboard. Runs as the current user (no sudo)."""
        env = request.env
        if not env.user.has_group(MANAGER_GROUP):
            return {"error": "forbidden"}
        try:
            wh = int(warehouse_id) if warehouse_id else False
        except (TypeError, ValueError):
            wh = False

        Quant = env["stock.quant"]
        today = fields.Date.to_string(fields.Date.context_today(Quant))
        base = [("location_id.usage", "=", "internal")]
        if wh:
            base.append(("location_id.warehouse_id", "=", wh))
        d_negative = base + [("quantity", "<", 0)]
        d_to_count = base + [("inventory_quantity_set", "=", False), ("inventory_date", "<=", today)]
        d_pending = base + [("inventory_quantity_set", "=", True)]

        op_domain = [("active", "=", True)]
        if wh:
            op_domain.append(("warehouse_id", "=", wh))
        ops = env["stock.warehouse.orderpoint"].search(op_domain, limit=2000)
        low_ops = ops.filtered(lambda o: o.qty_on_hand < o.product_min_qty)
        low_ops = low_ops.sorted(lambda o: o.qty_on_hand - o.product_min_qty)

        low = [
            {
                "id": o.id,
                "product_id": o.product_id.id,
                "product": o.product_id.display_name,
                "location": o.location_id.display_name,
                "qty": _num(o.qty_on_hand),
                "min": _num(o.product_min_qty),
                "short": _num(o.product_min_qty - o.qty_on_hand),
                "uom": o.product_uom.name or "",
            }
            for o in low_ops[:LIMIT]
        ]
        negative = [
            {
                "id": q.id,
                "product_id": q.product_id.id,
                "product": q.product_id.display_name,
                "location": q.location_id.display_name,
                "lot": q.lot_id.name or "",
                "qty": _num(q.quantity),
                "uom": q.product_uom_id.name or "",
            }
            for q in Quant.search(d_negative, limit=LIMIT, order="quantity asc")
        ]
        to_count = [
            {
                "id": q.id,
                "product_id": q.product_id.id,
                "product": q.product_id.display_name,
                "location": q.location_id.display_name,
                "lot": q.lot_id.name or "",
                "qty": _num(q.quantity),
                "due": fields.Date.to_string(q.inventory_date) if q.inventory_date else "",
                "uom": q.product_uom_id.name or "",
            }
            for q in Quant.search(d_to_count, limit=LIMIT, order="inventory_date asc, id")
        ]
        pending = [
            {
                "id": q.id,
                "product_id": q.product_id.id,
                "product": q.product_id.display_name,
                "location": q.location_id.display_name,
                "lot": q.lot_id.name or "",
                "qty": _num(q.quantity),
                "counted": _num(q.inventory_quantity),
                "diff": _num(q.inventory_diff_quantity),
                "counter": q.user_id.name or "",
                "requester": q.toruq_requester_id.name or "",
                "uom": q.product_uom_id.name or "",
            }
            for q in Quant.search(d_pending, limit=LIMIT, order="write_date desc, id")
        ]

        Log = env["toruq.count.log"]
        labels = dict(Log._fields["event"]._description_selection(env))
        log_domain = [("warehouse_id", "=", wh)] if wh else []
        start = fields.Datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        applied_today = Log.search_count(
            log_domain + [("event", "=", "applied"), ("date", ">=", start)]
        )
        events = [
            {
                "id": e.id,
                "date": fields.Datetime.to_string(e.date),
                "event": e.event,
                "label": labels.get(e.event, e.event),
                "product_id": e.product_id.id,
                "product": e.product_id.display_name or "",
                "location": e.location_id.display_name or "",
                "user": e.user_id.name or "",
                "counted": _num(e.counted_qty),
                "diff": _num(e.diff_qty),
            }
            for e in Log.search(log_domain, limit=30)
        ]

        return {
            "kpis": {
                "low": len(low_ops),
                "negative": Quant.search_count(d_negative),
                "to_count": Quant.search_count(d_to_count),
                "pending": Quant.search_count(d_pending),
                "applied_today": applied_today,
            },
            "low": low,
            "low_op_ids": low_ops.ids,
            "negative": negative,
            "to_count": to_count,
            "pending": pending,
            "events": events,
            "domains": {"negative": d_negative, "to_count": d_to_count, "pending": d_pending},
            "warehouses": env["stock.warehouse"].search_read([], ["name"]),
        }

    @http.route("/toruq/count_saved", type="json", auth="user")
    def count_saved(self):
        """Number of distinct products with a saved (not yet applied) count for the current user."""
        env = request.env
        user = env.user
        restricted = user.has_group(COUNT_ONLY_GROUP) and not user.has_group(MANAGER_GROUP)
        domain = [("inventory_quantity_set", "=", True), ("location_id.usage", "=", "internal")]
        domain.append(("user_id", "=", user.id) if restricted else ("write_uid", "=", user.id))
        try:
            groups = env["stock.quant"]._read_group(domain, ["product_id"], ["__count"])
        except AccessError:
            return {}
        return {"products": len(groups)}
