import logging
from collections import defaultdict
from datetime import datetime, time, timedelta

import pytz
from dateutil.relativedelta import relativedelta

from odoo import fields, http
from odoo.exceptions import AccessError
from odoo.http import request

_logger = logging.getLogger(__name__)

MANAGER_GROUP = "stock.group_stock_manager"
COUNT_ONLY_GROUP = "toruq_barcode.group_barcode_count_only"
ROWS = 300
EPS = 1e-9


def _r(value, digits=2):
    return round(value or 0.0, digits)


def _period_range(period, offset, today, date_from=None, date_to=None):
    """Inclusive (start, end) dates of the requested period. Weeks start on Sunday."""
    try:
        offset = max(int(offset or 0), 0)
    except (TypeError, ValueError):
        offset = 0
    if period == "custom" and date_from and date_to:
        start, end = fields.Date.to_date(date_from), fields.Date.to_date(date_to)
        return (end, start) if end < start else (start, end)
    if period == "day":
        start = today - timedelta(days=offset)
        return start, start
    if period == "week":
        first = today - timedelta(days=(today.weekday() + 1) % 7)
        start = first - timedelta(weeks=offset)
        return start, start + timedelta(days=6)
    if period == "month":
        start = today.replace(day=1) - relativedelta(months=offset)
        return start, start + relativedelta(months=1) - timedelta(days=1)
    if period == "quarter":
        first = today.replace(day=1, month=3 * ((today.month - 1) // 3) + 1)
        start = first - relativedelta(months=3 * offset)
        return start, start + relativedelta(months=3) - timedelta(days=1)
    if period == "half":
        first = today.replace(day=1, month=1 if today.month <= 6 else 7)
        start = first - relativedelta(months=6 * offset)
        return start, start + relativedelta(months=6) - timedelta(days=1)
    start = today.replace(month=1, day=1) - relativedelta(years=offset)
    return start, start + relativedelta(years=1) - timedelta(days=1)


def _utc_bounds(tz, start, end):
    lo = tz.localize(datetime.combine(start, time.min)).astimezone(pytz.utc).replace(tzinfo=None)
    hi = tz.localize(datetime.combine(end, time.max)).astimezone(pytz.utc).replace(tzinfo=None)
    return lo, hi


def _bucket_kind(start, end):
    days = (end - start).days + 1
    if days <= 31:
        return "day"
    return "week" if days <= 190 else "month"


def _bucket_key(day, kind):
    if kind == "day":
        return day
    if kind == "week":
        return day - timedelta(days=(day.weekday() + 1) % 7)
    return day.replace(day=1)


def _bucket_keys(start, end, kind):
    keys, cur = [], _bucket_key(start, kind)
    while cur <= end:
        keys.append(cur)
        if kind == "day":
            cur += timedelta(days=1)
        elif kind == "week":
            cur += timedelta(weeks=1)
        else:
            cur += relativedelta(months=1)
    return keys


def _bucket_label(key, kind):
    return key.strftime("%m/%Y") if kind == "month" else key.strftime("%d/%m")


class ToruqCountDashboard(http.Controller):

    # ------------------------------------------------------------------ stock
    def _stock_section(self, env, base, wh):
        Quant = env["stock.quant"]
        groups = Quant._read_group(
            base, ["location_id", "product_id"], ["quantity:sum", "reserved_quantity:sum"]
        )
        products = env["product.product"].browse(list({g[1].id for g in groups}))
        pinfo = {
            p.id: {
                "name": p.display_name,
                "cat_id": p.categ_id.id,
                "cat": p.categ_id.complete_name or "",
                "cost": p.standard_price or 0.0,
            }
            for p in products
        }

        def bucket():
            return {"products": set(), "on_hand": 0.0, "reserved": 0.0, "value": 0.0}

        per_wh, per_loc, per_cat, per_prod = (defaultdict(bucket) for _i in range(4))
        names = {}
        wh_prod = defaultdict(float)
        totals = bucket()
        for loc, prod, qty, reserved in groups:
            qty, reserved = qty or 0.0, reserved or 0.0
            info = pinfo[prod.id]
            value = qty * info["cost"]
            wid = loc.warehouse_id.id or 0
            names[("wh", wid)] = loc.warehouse_id.name or "بدون فرع"
            names[("loc", loc.id)] = (loc.complete_name or loc.display_name, names[("wh", wid)])
            names[("cat", info["cat_id"])] = info["cat"] or "بدون فئة"
            wh_prod[(wid, prod.id)] += qty
            for agg in (
                totals, per_wh[wid], per_loc[loc.id], per_cat[info["cat_id"]], per_prod[prod.id]
            ):
                agg["products"].add(prod.id)
                agg["on_hand"] += qty
                agg["reserved"] += reserved
                agg["value"] += value

        def row(name, agg, **extra):
            res = {
                "name": name,
                "products": len(agg["products"]),
                "on_hand": _r(agg["on_hand"]),
                "reserved": _r(agg["reserved"]),
                "available": _r(agg["on_hand"] - agg["reserved"]),
                "value": _r(agg["value"]),
            }
            res.update(extra)
            return res

        by_wh = sorted((row(names[("wh", k)], v) for k, v in per_wh.items()), key=lambda r: -r["value"])
        by_loc = sorted(
            (row(names[("loc", k)][0], v, warehouse=names[("loc", k)][1]) for k, v in per_loc.items()),
            key=lambda r: -r["value"],
        )[:ROWS]
        by_cat = sorted((row(names[("cat", k)], v) for k, v in per_cat.items()), key=lambda r: -r["value"])[:ROWS]

        # reorder rules -> minimum quantity per (warehouse, product)
        domain = [("active", "=", True)] + ([("warehouse_id", "=", wh)] if wh else [])
        ops = env["stock.warehouse.orderpoint"].search_read(
            domain, ["warehouse_id", "product_id", "product_min_qty"], limit=5000
        )
        min_map, min_by_prod = defaultdict(float), defaultdict(float)
        for o in ops:
            if o["warehouse_id"] and o["product_id"]:
                min_map[(o["warehouse_id"][0], o["product_id"][0])] += o["product_min_qty"] or 0.0
                min_by_prod[o["product_id"][0]] += o["product_min_qty"] or 0.0
        wh_names = {w.id: w.name for w in env["stock.warehouse"].search([])}
        extra_products = env["product.product"].browse(
            [pid for (_w, pid) in min_map if pid not in pinfo]
        )
        low_rows = []
        for (wid, pid), minimum in min_map.items():
            on_hand = wh_prod.get((wid, pid), 0.0)
            if minimum > 0 and on_hand < minimum:
                name = pinfo[pid]["name"] if pid in pinfo else extra_products.browse(pid).display_name
                low_rows.append({
                    "product_id": pid,
                    "kind": "نقص عن الحد الأدنى",
                    "product": name,
                    "where": wh_names.get(wid, ""),
                    "qty": _r(on_hand),
                    "min": _r(minimum),
                    "short": _r(minimum - on_hand),
                })
        low_rows.sort(key=lambda r: -r["short"])

        neg_domain = base + [("quantity", "<", 0)]
        negative_count = Quant.search_count(neg_domain)
        neg_rows = [
            {
                "product_id": q.product_id.id,
                "kind": "رصيد سالب",
                "product": q.product_id.display_name,
                "where": q.location_id.complete_name or q.location_id.display_name,
                "qty": _r(q.quantity),
                "min": 0.0,
                "short": _r(-q.quantity),
            }
            for q in Quant.search(neg_domain, limit=ROWS, order="quantity asc")
        ]

        prod_rows = []
        for pid, agg in per_prod.items():
            on_hand, reserved = agg["on_hand"], agg["reserved"]
            minimum = min_by_prod.get(pid, 0.0)
            if on_hand < -EPS:
                status, label = "negative", "سالب"
            elif on_hand <= EPS:
                status, label = "out", "نفد"
            elif minimum and on_hand < minimum:
                status, label = "low", "ناقص"
            else:
                status, label = "ok", "كافٍ"
            prod_rows.append({
                "product_id": pid,
                "product": pinfo[pid]["name"],
                "category": pinfo[pid]["cat"],
                "on_hand": _r(on_hand),
                "reserved": _r(reserved),
                "available": _r(on_hand - reserved),
                "value": _r(agg["value"]),
                "min": _r(minimum),
                "status": status,
                "status_label": label,
            })
        prod_rows.sort(key=lambda r: -r["value"])

        return {
            "totals": {
                "products": len(totals["products"]),
                "on_hand": _r(totals["on_hand"]),
                "reserved": _r(totals["reserved"]),
                "available": _r(totals["on_hand"] - totals["reserved"]),
                "value": _r(totals["value"]),
                "low": len(low_rows),
                "negative": negative_count,
            },
            "stock": {"warehouse": by_wh, "location": by_loc, "category": by_cat, "product": prod_rows[:ROWS]},
            "shortage": (low_rows + neg_rows)[:ROWS],
            "pinfo_cost": {pid: info["cost"] for pid, info in pinfo.items()},
        }

    # ------------------------------------------------------------------ count
    def _count_section(self, env, base, end, today, costs):
        Quant = env["stock.quant"]
        d_pending = base + [("inventory_quantity_set", "=", True)]
        d_due = base + [
            ("inventory_quantity_set", "=", False),
            ("inventory_date", "<=", fields.Date.to_string(end)),
        ]

        def cost_of(product_ids):
            missing = [pid for pid in product_ids if pid not in costs]
            for p in env["product.product"].browse(missing):
                costs[p.id] = p.standard_price or 0.0

        due_total = Quant.search_count(d_due)
        due_rows = [
            {
                "id": q.id,
                "product_id": q.product_id.id,
                "product": q.product_id.display_name,
                "location": q.location_id.complete_name or q.location_id.display_name,
                "lot": q.lot_id.name or "",
                "qty": _r(q.quantity),
                "due": fields.Date.to_string(q.inventory_date) if q.inventory_date else "",
                "overdue": max((today - q.inventory_date).days, 0) if q.inventory_date else 0,
            }
            for q in Quant.search(d_due, limit=ROWS, order="inventory_date asc, id")
        ]
        overdue_total = Quant.search_count(d_due + [("inventory_date", "<", fields.Date.to_string(today))])
        due_by_loc = Quant._read_group(d_due, ["location_id"], ["__count"])
        due_by_wh = defaultdict(int)
        for loc, cnt in due_by_loc:
            due_by_wh[loc.warehouse_id.name or "بدون فرع"] += cnt

        pending_total = Quant.search_count(d_pending)
        pend_groups = Quant._read_group(d_pending, ["product_id"], ["inventory_diff_quantity:sum"])
        cost_of([p.id for p, _d in pend_groups])
        pending_value = sum((d or 0.0) * costs.get(p.id, 0.0) for p, d in pend_groups)
        pending_rows = []
        quants = Quant.search(d_pending, limit=ROWS, order="write_date desc, id")
        cost_of([q.product_id.id for q in quants])
        for q in quants:
            pending_rows.append({
                "id": q.id,
                "product_id": q.product_id.id,
                "product": q.product_id.display_name,
                "location": q.location_id.complete_name or q.location_id.display_name,
                "lot": q.lot_id.name or "",
                "qty": _r(q.quantity),
                "counted": _r(q.inventory_quantity),
                "diff": _r(q.inventory_diff_quantity),
                "value": _r(q.inventory_diff_quantity * costs.get(q.product_id.id, 0.0)),
                "counter": q.user_id.name or "",
                "requester": q.toruq_requester_id.name or "",
            })
        return {
            "due_total": due_total,
            "overdue": overdue_total,
            "pending": pending_total,
            "pending_value": _r(pending_value),
            "due_rows": due_rows,
            "pending_rows": pending_rows,
            "due_by_wh": dict(due_by_wh),
        }

    # ------------------------------------------------------------------- logs
    def _log_section(self, env, tz, start, end, start_dt, end_dt, wh, costs):
        Log = env["toruq.count.log"]
        labels = dict(Log._fields["event"]._description_selection(env))
        domain = [("date", ">=", start_dt), ("date", "<=", end_dt)]
        if wh:
            domain.append(("warehouse_id", "=", wh))
        logs = Log.search(domain, limit=20000, order="date asc")
        missing = list({l.product_id.id for l in logs if l.product_id} - set(costs))
        for p in env["product.product"].browse(missing):
            costs[p.id] = p.standard_price or 0.0

        kind = _bucket_kind(start, end)
        trend = {k: {"requested": 0, "submitted": 0, "applied": 0} for k in _bucket_keys(start, end, kind)}
        users = defaultdict(lambda: {"requested": 0, "submitted": 0, "applied": 0, "diff": 0.0})
        done_by_wh = defaultdict(int)
        applied = matched = 0
        applied_rows, log_rows = [], []
        for l in logs:
            day = pytz.utc.localize(l.date).astimezone(tz).date()
            key = _bucket_key(day, kind)
            if key in trend:
                trend[key][l.event] += 1
            u = users[l.user_id.name or "-"]
            u[l.event] += 1
            value = (l.diff_qty or 0.0) * costs.get(l.product_id.id, 0.0)
            row = {
                "product_id": l.product_id.id,
                "date": fields.Datetime.to_string(l.date),
                "label": labels.get(l.event, l.event),
                "product": l.product_id.display_name or "",
                "location": l.location_id.complete_name or l.location_id.display_name or "",
                "user": l.user_id.name or "",
                "system": _r(l.system_qty),
                "counted": _r(l.counted_qty),
                "diff": _r(l.diff_qty),
                "value": _r(value),
            }
            log_rows.append(row)
            if l.event == "applied":
                applied += 1
                done_by_wh[l.warehouse_id.name or "بدون فرع"] += 1
                u["diff"] += abs(l.diff_qty or 0.0)
                if abs(l.diff_qty or 0.0) < EPS:
                    matched += 1
                applied_rows.append(row)
        diffs = sorted(
            (r for r in applied_rows if abs(r["diff"]) > EPS), key=lambda r: -abs(r["value"])
        )[:ROWS]
        return {
            "applied": applied,
            "matched": matched,
            "events": {e: sum(1 for l in logs if l.event == e) for e in labels},
            "trend": [
                dict(label=_bucket_label(k, kind), **v) for k, v in trend.items()
            ],
            "users": sorted(
                ({"user": n, **v, "diff": _r(v["diff"])} for n, v in users.items()),
                key=lambda r: -r["applied"],
            ),
            "done_by_wh": dict(done_by_wh),
            "applied_rows": list(reversed(applied_rows))[:ROWS],
            "diff_rows": diffs,
            "log_rows": list(reversed(log_rows))[:ROWS],
        }

    # ------------------------------------------------------------ adjustments
    def _adjust_section(self, env, start_dt, end_dt, wh, costs):
        Move = env["stock.move"]
        domain = [
            ("is_inventory", "=", True),
            ("state", "=", "done"),
            ("date", ">=", start_dt),
            ("date", "<=", end_dt),
        ]
        if wh:
            domain += ["|", ("location_id.warehouse_id", "=", wh), ("location_dest_id.warehouse_id", "=", wh)]
        gain = Move._read_group(
            domain + [("location_id.usage", "=", "inventory")], ["product_id"], ["quantity:sum"]
        )
        loss = Move._read_group(
            domain + [("location_dest_id.usage", "=", "inventory")], ["product_id"], ["quantity:sum"]
        )
        missing = list({p.id for p, _q in gain + loss} - set(costs))
        for p in env["product.product"].browse(missing):
            costs[p.id] = p.standard_price or 0.0
        return {
            "gain_value": _r(sum((q or 0.0) * costs.get(p.id, 0.0) for p, q in gain)),
            "loss_value": _r(sum((q or 0.0) * costs.get(p.id, 0.0) for p, q in loss)),
            "gain_products": len(gain),
            "loss_products": len(loss),
        }

    # --------------------------------------------------------------- endpoint
    @http.route("/toruq/count_dashboard", type="json", auth="user")
    def dashboard(self, period="month", offset=0, warehouse_id=None, date_from=None, date_to=None):
        """Manager-only data for the inventory dashboard. Runs as the current user (no sudo)."""
        env = request.env
        if not env.user.has_group(MANAGER_GROUP):
            return {"error": "forbidden"}
        try:
            wh = int(warehouse_id) if warehouse_id else False
        except (TypeError, ValueError):
            wh = False
        tz = pytz.timezone(env.user.tz or "UTC")
        today = fields.Date.context_today(env["stock.quant"])
        start, end = _period_range(period, offset, today, date_from, date_to)
        start_dt, end_dt = _utc_bounds(tz, start, end)
        base = [("location_id.usage", "=", "internal")]
        if wh:
            base.append(("location_id.warehouse_id", "=", wh))

        warnings, costs = [], {}
        empty_stock = {
            "totals": {"products": 0, "on_hand": 0, "reserved": 0, "available": 0, "value": 0, "low": 0, "negative": 0},
            "stock": {"warehouse": [], "location": [], "category": [], "product": []},
            "shortage": [], "pinfo_cost": {},
        }
        empty_count = {
            "due_total": 0, "overdue": 0, "pending": 0, "pending_value": 0,
            "due_rows": [], "pending_rows": [], "due_by_wh": {},
        }
        empty_log = {
            "applied": 0, "matched": 0, "events": {}, "trend": [], "users": [], "done_by_wh": {},
            "applied_rows": [], "diff_rows": [], "log_rows": [],
        }
        empty_adjust = {"gain_value": 0, "loss_value": 0, "gain_products": 0, "loss_products": 0}

        def guarded(label, func, fallback, *args):
            try:
                return func(*args)
            except Exception as exc:  # keep the page usable, report the failing block
                _logger.exception("toruq_barcode dashboard: %s failed", label)
                warnings.append("%s: %s" % (label, exc))
                return fallback

        stock = guarded("المخزون", self._stock_section, empty_stock, env, base, wh)
        costs.update(stock.pop("pinfo_cost"))
        count = guarded("الجرد المطلوب", self._count_section, empty_count, env, base, end, today, costs)
        logs = guarded("سجل الجرد", self._log_section, empty_log, env, tz, start, end, start_dt, end_dt, wh, costs)
        adjust = guarded("تسويات الجرد", self._adjust_section, empty_adjust, env, start_dt, end_dt, wh, costs)

        totals = stock["totals"]
        applied = logs["applied"]
        required = applied + count["due_total"]
        progress = round(applied * 100.0 / required, 1) if required else 0.0
        accuracy = round(logs["matched"] * 100.0 / applied, 1) if applied else 0.0

        progress_wh = []
        for name in sorted(set(count["due_by_wh"]) | set(logs["done_by_wh"])):
            due, done = count["due_by_wh"].get(name, 0), logs["done_by_wh"].get(name, 0)
            total = due + done
            progress_wh.append({
                "name": name, "due": due, "done": done,
                "pct": round(done * 100.0 / total) if total else 0,
            })

        company = env.company
        return {
            "company": {
                "id": company.id,
                "name": company.name,
                "primary": company.primary_color or "#ff3d00",
                "secondary": company.secondary_color or "#2b2b2b",
                "currency": company.currency_id.symbol or "",
                "logo": "/web/image/res.company/%d/logo" % company.id if company.logo else "",
            },
            "range": {
                "from": fields.Date.to_string(start),
                "to": fields.Date.to_string(end),
                "period": period,
                "offset": offset,
            },
            "kpis": {
                "products": totals["products"],
                "on_hand": totals["on_hand"],
                "reserved": totals["reserved"],
                "available": totals["available"],
                "value": totals["value"],
                "low": totals["low"],
                "negative": totals["negative"],
                "due_total": count["due_total"],
                "overdue": count["overdue"],
                "pending": count["pending"],
                "pending_value": count["pending_value"],
                "applied": applied,
                "matched": logs["matched"],
                "progress": progress,
                "accuracy": accuracy,
                "gain_value": adjust["gain_value"],
                "loss_value": adjust["loss_value"],
                "requested": logs["events"].get("requested", 0),
                "submitted": logs["events"].get("submitted", 0),
                "rejected": logs["events"].get("rejected", 0),
            },
            "overview": {"trend": logs["trend"], "users": logs["users"], "progress_wh": progress_wh},
            "due": count["due_rows"],
            "counted": count["pending_rows"],
            "applied": logs["applied_rows"],
            "diffs": logs["diff_rows"],
            "stock": stock["stock"],
            "shortage": stock["shortage"],
            "log": logs["log_rows"],
            "warehouses": env["stock.warehouse"].search_read([], ["name"]),
            "warnings": warnings,
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
