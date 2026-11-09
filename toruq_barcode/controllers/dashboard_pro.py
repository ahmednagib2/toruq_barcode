import io
import logging
from collections import defaultdict
from datetime import datetime, timedelta

import pytz

from odoo import fields, http
from odoo.http import content_disposition, request

from . import dashboard as base
from .dashboard import (
    EPS,
    MANAGER_GROUP,
    ToruqCountDashboard,
    _bucket_key,
    _bucket_keys,
    _bucket_kind,
    _bucket_label,
    _period_range,
    _r,
    _utc_bounds,
)

_logger = logging.getLogger(__name__)
EXPORT_ROWS = 5000
FILTERS = ("warehouse_id", "category_id", "user_id", "location_id")


def _int(value):
    try:
        return int(value) if value else False
    except (TypeError, ValueError):
        return False


def _pct(part, whole):
    return round(part * 100.0 / whole, 1) if whole else 0.0


def _prev_range(period, offset, start, end, today):
    if period == "custom":
        days = (end - start).days + 1
        return start - timedelta(days=days), start - timedelta(days=1)
    return _period_range(period, (_int(offset) or 0) + 1, today)


class ToruqCountDashboardPro(ToruqCountDashboard):

    @staticmethod
    def _log_domain(f, start_dt, end_dt):
        domain = [("date", ">=", start_dt), ("date", "<=", end_dt)]
        if f["warehouse_id"]:
            domain.append(("warehouse_id", "=", f["warehouse_id"]))
        if f["location_id"]:
            domain.append(("location_id", "child_of", f["location_id"]))
        if f["category_id"]:
            domain.append(("product_id.categ_id", "child_of", f["category_id"]))
        if f["user_id"]:
            domain.append(("user_id", "=", f["user_id"]))
        return domain

    @staticmethod
    def _abc(rows, total_value, total_products):
        cum, acc = 0.0, {"A": [0, 0.0], "B": [0, 0.0], "C": [0, 0.0]}
        for r in rows:
            share = cum / total_value if total_value > 0 else 1.0
            cls = "A" if share < 0.8 else "B" if share < 0.95 else "C"
            r["abc"] = cls
            value = max(r["value"], 0.0)
            cum += value
            acc[cls][0] += 1
            acc[cls][1] += value
        acc["C"][0] += max(total_products - len(rows), 0)
        return [
            {"k": k, "count": v[0], "value": _r(v[1]), "pct": _pct(v[1], total_value)}
            for k, v in acc.items()
        ]

    def _aging(self, env, base_d, days, rows):
        now = datetime.utcnow()
        cutoff = now - timedelta(days=days)
        last = {
            p.id: d
            for p, d in env["toruq.count.log"]._read_group(
                [("event", "=", "applied"), ("product_id", "!=", False)],
                ["product_id"],
                ["date:max"],
            )
        }
        groups = env["stock.quant"]._read_group(
            base_d + [("quantity", ">", 0)], ["product_id"], ["quantity:sum"]
        )
        out = []
        for prod, qty in groups:
            seen = last.get(prod.id)
            if seen and seen >= cutoff:
                continue
            out.append({
                "product_id": prod.id,
                "product": prod.display_name,
                "category": prod.categ_id.complete_name or "",
                "on_hand": _r(qty),
                "value": _r((qty or 0.0) * (prod.standard_price or 0.0)),
                "last": fields.Datetime.to_string(seen) if seen else "",
                "days": (now - seen).days if seen else None,
            })
        out.sort(key=lambda r: -r["value"])
        return {"total": len(out), "value": _r(sum(r["value"] for r in out)), "rows": out[:rows]}

    def _adjust(self, env, start_dt, end_dt, f, costs):
        domain = [
            ("is_inventory", "=", True),
            ("state", "=", "done"),
            ("date", ">=", start_dt),
            ("date", "<=", end_dt),
        ]
        if f["warehouse_id"]:
            wid = f["warehouse_id"]
            domain += ["|", ("location_id.warehouse_id", "=", wid), ("location_dest_id.warehouse_id", "=", wid)]
        if f["category_id"]:
            domain.append(("product_id.categ_id", "child_of", f["category_id"]))

        def total(extra):
            groups = env["stock.move"]._read_group(domain + extra, ["product_id"], ["quantity:sum"])
            for p, _q in groups:
                costs.setdefault(p.id, p.standard_price or 0.0)
            return _r(sum((q or 0.0) * costs[p.id] for p, q in groups))

        return (
            total([("location_id.usage", "=", "inventory")]),
            total([("location_dest_id.usage", "=", "inventory")]),
        )

    def _prev(self, env, start_dt, end_dt, f, costs):
        Log = env["toruq.count.log"]
        domain = self._log_domain(f, start_dt, end_dt) + [("event", "=", "applied")]
        applied = Log.search_count(domain)
        matched = Log.search_count(domain + [("diff_qty", "=", 0)])
        gain, loss = self._adjust(env, start_dt, end_dt, f, costs)
        return {"applied": applied, "accuracy": _pct(matched, applied), "net": _r(gain - loss)}

    def _logs(self, env, tz, start, end, start_dt, end_dt, f, costs, rows):
        Log = env["toruq.count.log"]
        labels = dict(Log._fields["event"]._description_selection(env))
        logs = Log.search(self._log_domain(f, start_dt, end_dt), limit=20000, order="date asc")
        missing = list({l.product_id.id for l in logs if l.product_id} - set(costs))
        for p in env["product.product"].browse(missing):
            costs[p.id] = p.standard_price or 0.0
        kind = _bucket_kind(start, end)
        trend = {k: {"requested": 0, "submitted": 0, "applied": 0} for k in _bucket_keys(start, end, kind)}
        users = defaultdict(
            lambda: {"requested": 0, "submitted": 0, "applied": 0, "rejected": 0, "diff": 0.0, "matched": 0}
        )
        whs = defaultdict(lambda: [0, 0])
        shrink = {}
        events = defaultdict(int)
        applied_rows, log_rows = [], []
        for l in logs:
            events[l.event] += 1
            key = _bucket_key(pytz.utc.localize(l.date).astimezone(tz).date(), kind)
            if key in trend and l.event in trend[key]:
                trend[key][l.event] += 1
            u = users[l.user_id.name or "-"]
            u[l.event] += 1
            diff = l.diff_qty or 0.0
            value = diff * costs.get(l.product_id.id, 0.0)
            row = {
                "product_id": l.product_id.id,
                "date": fields.Datetime.to_string(l.date),
                "label": labels.get(l.event, l.event),
                "product": l.product_id.display_name or "",
                "location": l.location_id.complete_name or l.location_id.display_name or "",
                "user": l.user_id.name or "",
                "system": _r(l.system_qty),
                "counted": _r(l.counted_qty),
                "diff": _r(diff),
                "value": _r(value),
                "note": l.note or "",
            }
            log_rows.append(row)
            if l.event != "applied":
                continue
            wh_name = l.warehouse_id.name or "بدون فرع"
            whs[wh_name][0] += 1
            u["diff"] += abs(diff)
            applied_rows.append(row)
            if abs(diff) < EPS:
                u["matched"] += 1
                whs[wh_name][1] += 1
            elif diff < 0:
                s = shrink.setdefault(
                    l.product_id.id, {"product": l.product_id.display_name or "", "qty": 0.0, "value": 0.0}
                )
                s["qty"] += diff
                s["value"] += value
        applied = sum(w[0] for w in whs.values())
        matched = sum(w[1] for w in whs.values())
        return {
            "applied": applied,
            "matched": matched,
            "events": dict(events),
            "trend": [dict(label=_bucket_label(k, kind), **v) for k, v in trend.items()],
            "users": sorted(
                (
                    {"user": n, **v, "diff": _r(v["diff"]), "pct": _pct(v["matched"], v["applied"])}
                    for n, v in users.items()
                ),
                key=lambda r: -r["applied"],
            ),
            "wh_accuracy": [
                {"name": n, "applied": a, "matched": m, "pct": _pct(m, a)}
                for n, (a, m) in sorted(whs.items())
            ],
            "done_by_wh": {n: a for n, (a, _m) in whs.items()},
            "shrink": [
                {"product_id": pid, "product": s["product"], "qty": _r(s["qty"]), "value": _r(s["value"])}
                for pid, s in sorted(shrink.items(), key=lambda kv: kv[1]["value"])[:10]
            ],
            "applied_rows": list(reversed(applied_rows))[:rows],
            "diff_rows": sorted(
                (r for r in applied_rows if abs(r["diff"]) > EPS), key=lambda r: -abs(r["value"])
            )[:rows],
            "log_rows": list(reversed(log_rows))[:rows],
        }

    def _build(self, env, p, rows):
        f = {k: _int(p.get(k)) for k in FILTERS}
        days = _int(p.get("aging_days")) or 90
        tz = pytz.timezone(env.user.tz or "UTC")
        today = fields.Date.context_today(env["stock.quant"])
        period = p.get("period") or "month"
        start, end = _period_range(period, p.get("offset"), today, p.get("date_from"), p.get("date_to"))
        start_dt, end_dt = _utc_bounds(tz, start, end)
        pstart, pend = _prev_range(period, p.get("offset"), start, end, today)
        pstart_dt, pend_dt = _utc_bounds(tz, pstart, pend)
        wh = f["warehouse_id"]
        stock_base = [("location_id.usage", "=", "internal")]
        if wh:
            stock_base.append(("location_id.warehouse_id", "=", wh))
        if f["location_id"]:
            stock_base.append(("location_id", "child_of", f["location_id"]))
        if f["category_id"]:
            stock_base.append(("product_id.categ_id", "child_of", f["category_id"]))
        count_base = stock_base + ([("user_id", "=", f["user_id"])] if f["user_id"] else [])
        warnings, costs = [], {}

        def guarded(label, func, fallback, *args):
            try:
                return func(*args)
            except Exception as exc:  # keep the page usable, report the failing block
                _logger.exception("toruq_barcode dashboard: %s failed", label)
                warnings.append("%s: %s" % (label, exc))
                return fallback

        zero = {"products": 0, "on_hand": 0, "reserved": 0, "available": 0, "value": 0, "low": 0, "negative": 0}
        stock = guarded(
            "المخزون", self._stock_section,
            {"totals": zero, "stock": {"warehouse": [], "location": [], "category": [], "product": []},
             "shortage": [], "pinfo_cost": {}},
            env, stock_base, wh,
        )
        costs.update(stock.pop("pinfo_cost"))
        count = guarded(
            "الجرد المطلوب", self._count_section,
            {"due_total": 0, "overdue": 0, "pending": 0, "pending_value": 0,
             "due_rows": [], "pending_rows": [], "due_by_wh": {}},
            env, count_base, end, today, costs,
        )
        logs = guarded(
            "سجل الجرد", self._logs,
            {"applied": 0, "matched": 0, "events": {}, "trend": [], "users": [], "wh_accuracy": [],
             "done_by_wh": {}, "shrink": [], "applied_rows": [], "diff_rows": [], "log_rows": []},
            env, tz, start, end, start_dt, end_dt, f, costs, rows,
        )
        gain, loss = guarded("تسويات الجرد", self._adjust, (0, 0), env, start_dt, end_dt, f, costs)
        prev = guarded(
            "الفترة السابقة", self._prev, {"applied": 0, "accuracy": 0, "net": 0},
            env, pstart_dt, pend_dt, f, costs,
        )
        aging = guarded(
            "الأصناف غير المجرودة", self._aging, {"total": 0, "value": 0, "rows": []},
            env, stock_base, days, rows,
        )

        totals = stock["totals"]
        products = stock["stock"]["product"]
        abc = self._abc(products, totals["value"], totals["products"])
        for r in count["pending_rows"]:
            r["diff_pct"] = _pct(abs(r["diff"]), abs(r["qty"])) if r["qty"] else (100.0 if r["diff"] else 0.0)
        applied = logs["applied"]
        required = applied + count["due_total"]
        accuracy = _pct(logs["matched"], applied)
        progress_wh = []
        for name in sorted(set(count["due_by_wh"]) | set(logs["done_by_wh"])):
            due, done = count["due_by_wh"].get(name, 0), logs["done_by_wh"].get(name, 0)
            progress_wh.append({"name": name, "due": due, "done": done, "pct": round(_pct(done, due + done))})
        cats = [
            {"name": r["name"], "value": r["value"], "pct": _pct(r["value"], totals["value"])}
            for r in stock["stock"]["category"][:8]
        ]
        lists = (count["due_rows"], count["pending_rows"], logs["applied_rows"], logs["log_rows"], products, aging["rows"])
        if any(len(x) >= rows for x in lists):
            warnings.append("تم عرض أول %d صف فقط في بعض الجداول؛ استخدم تصدير Excel للحصول على كل البيانات." % rows)

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
            "range": {"from": fields.Date.to_string(start), "to": fields.Date.to_string(end), "period": period},
            "kpis": {
                "products": totals["products"], "on_hand": totals["on_hand"], "reserved": totals["reserved"],
                "available": totals["available"], "value": totals["value"], "low": totals["low"],
                "negative": totals["negative"], "due_total": count["due_total"], "overdue": count["overdue"],
                "pending": count["pending"], "pending_value": count["pending_value"], "applied": applied,
                "matched": logs["matched"], "progress": _pct(applied, required), "accuracy": accuracy,
                "gain_value": gain, "loss_value": loss, "aging_total": aging["total"],
                "aging_value": aging["value"], "aging_days": days, "prev": prev,
            },
            "overview": {"trend": logs["trend"], "users": logs["users"], "progress_wh": progress_wh, "categories": cats},
            "analytics": {"shrink": logs["shrink"], "users": logs["users"], "wh_accuracy": logs["wh_accuracy"], "abc": abc},
            "due": count["due_rows"],
            "counted": count["pending_rows"],
            "applied": logs["applied_rows"],
            "diffs": logs["diff_rows"],
            "stock": stock["stock"],
            "shortage": stock["shortage"],
            "aging": aging["rows"],
            "log": logs["log_rows"],
            "warehouses": env["stock.warehouse"].search_read([], ["name"]),
            "categories": [
                {"id": c.id, "name": c.complete_name}
                for c in env["product.category"].search([], limit=500, order="complete_name")
            ],
            "locations": [
                {"id": l.id, "name": l.complete_name}
                for l in env["stock.location"].search([("usage", "=", "internal")], limit=500, order="complete_name")
            ],
            "users": [
                {"id": u.id, "name": u.name}
                for u in env["res.users"].search([("share", "=", False)], limit=300, order="name")
            ],
            "warnings": warnings,
        }

    @http.route("/toruq/count_dashboard/pro", type="json", auth="user")
    def dashboard_pro(self, **params):
        env = request.env
        if not env.user.has_group(MANAGER_GROUP):
            return {"error": "forbidden"}
        return self._build(env, params, base.ROWS)

    @http.route("/toruq/count_dashboard/bulk", type="json", auth="user")
    def dashboard_bulk(self, ids=None, action="approve", reason=""):
        env = request.env
        if not env.user.has_group(MANAGER_GROUP):
            return {"error": "forbidden"}
        reason = (reason or "").strip()
        if action == "reject" and not reason:
            return {"error": "reason"}
        wanted = [int(i) for i in (ids or []) if str(i).isdigit()][:300]
        quants = env["stock.quant"].browse(wanted).exists().filtered("inventory_quantity_set")
        res = {"ok": 0, "manual": [], "failed": []}
        for q in quants:
            name = q.product_id.display_name
            try:
                with env.cr.savepoint():
                    if action == "approve":
                        out = q.with_context(inventory_mode=True).action_apply_inventory()
                        if isinstance(out, dict) and out.get("type"):
                            res["manual"].append(name)
                            continue
                    else:
                        q.with_context(inventory_mode=True, toruq_reject=True).action_clear_inventory_quantity()
                        env["toruq.count.log"].sudo().search(
                            [
                                ("event", "=", "rejected"),
                                ("product_id", "=", q.product_id.id),
                                ("location_id", "=", q.location_id.id),
                            ],
                            limit=1,
                            order="id desc",
                        ).write({"note": reason})
                    res["ok"] += 1
            except Exception as exc:
                res["failed"].append({"product": name, "error": str(exc)})
        return res

    @staticmethod
    def _sheets(d):
        P, L, U = ("product", "المنتج"), ("location", "الموقع"), ("user", "المنفذ")
        DATE, LOT = ("date", "التاريخ"), ("lot", "الدفعة")
        SYS, CNT, DIFF, VAL = ("system", "كمية النظام"), ("counted", "المعدود"), ("diff", "الفرق"), ("value", "قيمة الفرق")
        STOCK = [("products", "عدد المنتجات"), ("on_hand", "المتوفر"), ("reserved", "المحجوز"), ("available", "المتاح"), ("value", "القيمة")]
        k = d["kpis"]
        summary = [
            {"k": a, "v": b}
            for a, b in (
                ("المخزون الحالي", k["on_hand"]), ("قيمة المخزون", k["value"]), ("المحجوز", k["reserved"]),
                ("المتاح", k["available"]), ("الجرد المطلوب", k["due_total"]), ("متأخر", k["overdue"]),
                ("بانتظار الاعتماد", k["pending"]), ("تم جرده", k["applied"]), ("نسبة الإنجاز %", k["progress"]),
                ("دقة الجرد %", k["accuracy"]), ("زيادة التسويات", k["gain_value"]), ("عجز التسويات", k["loss_value"]),
                ("أصناف ناقصة", k["low"]), ("رصيد سالب", k["negative"]), ("أصناف لم تُجرد", k["aging_total"]),
            )
        ]
        return [
            ("ملخص", summary, [("k", "البند"), ("v", "القيمة")]),
            ("الجرد المطلوب", d["due"], [P, L, LOT, ("qty", "كمية النظام"), ("due", "موعد الجرد"), ("overdue", "متأخر (يوم)")]),
            ("بانتظار الاعتماد", d["counted"], [P, L, LOT, ("qty", "كمية النظام"), CNT, DIFF, ("diff_pct", "الفرق %"), VAL, ("counter", "العدّاد"), ("requester", "الطالب")]),
            ("الجرد الفعلي", d["applied"], [DATE, P, L, U, SYS, CNT, DIFF, VAL]),
            ("الفروقات", d["diffs"], [P, L, U, SYS, CNT, DIFF, VAL]),
            ("المخزون حسب الفرع", d["stock"]["warehouse"], [("name", "الفرع")] + STOCK),
            ("المخزون حسب الفئة", d["stock"]["category"], [("name", "الفئة")] + STOCK),
            ("المخزون حسب المنتج", d["stock"]["product"], [P, ("category", "الفئة"), ("abc", "ABC")] + STOCK[1:] + [("min", "الحد الأدنى"), ("status_label", "الحالة")]),
            ("النواقص والسالب", d["shortage"], [("kind", "النوع"), P, ("where", "الفرع / الموقع"), ("qty", "المتوفر"), ("min", "الحد الأدنى"), ("short", "العجز")]),
            ("لم تُجرد", d["aging"], [P, ("category", "الفئة"), ("on_hand", "المتوفر"), ("value", "القيمة"), ("last", "آخر جرد"), ("days", "منذ (يوم)")]),
            ("السجل", d["log"], [DATE, ("label", "الحدث"), P, L, U, CNT, DIFF, ("note", "ملاحظة")]),
        ]

    @http.route("/toruq/count_dashboard/export", type="http", auth="user")
    def dashboard_export(self, **kw):
        env = request.env
        if not env.user.has_group(MANAGER_GROUP):
            return request.not_found()
        old = base.ROWS
        base.ROWS = EXPORT_ROWS
        try:
            data = self._build(env, kw, EXPORT_ROWS)
        finally:
            base.ROWS = old
        import xlsxwriter

        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {"in_memory": True})
        head = wb.add_format({"bold": True, "font_color": "#ffffff", "bg_color": "#2b2b2b", "border": 1, "align": "center"})
        text = wb.add_format({"border": 1})
        number = wb.add_format({"border": 1, "num_format": "#,##0.00"})
        for title, rows, cols in self._sheets(data):
            ws = wb.add_worksheet(title[:31])
            ws.right_to_left()
            ws.freeze_panes(1, 0)
            for i, (_k, label) in enumerate(cols):
                ws.write(0, i, label, head)
                ws.set_column(i, i, 34 if i == 0 else 18)
            for n, row in enumerate(rows, 1):
                for i, (key, _label) in enumerate(cols):
                    value = row.get(key)
                    if value is None:
                        value = ""
                    ws.write(n, i, value, number if isinstance(value, (int, float)) else text)
        wb.close()
        return request.make_response(
            buf.getvalue(),
            headers=[
                ("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                ("Content-Disposition", content_disposition("toruq_count_dashboard.xlsx")),
            ],
        )
