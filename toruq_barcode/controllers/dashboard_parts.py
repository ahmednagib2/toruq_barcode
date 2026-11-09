from collections import defaultdict

from .dashboard_pro import ToruqCountDashboardPro


def _num(value):
    return "%g" % (value or 0.0)


class ToruqCountDashboardParts(ToruqCountDashboardPro):

    def _count_section(self, env, base, end, today, costs):
        res = super()._count_section(env, base, end, today, costs)
        rows = res.get("pending_rows") or []
        ids = [r["id"] for r in rows if r.get("id")]
        parts = defaultdict(list)
        if ids:
            for part in env["toruq.count.part"].sudo().search([("quant_id", "in", ids)], order="id"):
                parts[part.quant_id.id].append({"user": part.user_id.name or "-", "qty": part.qty})
        for r in rows:
            items = parts.get(r["id"])
            if not items and r.get("counter"):
                items = [{"user": r["counter"], "qty": r["counted"]}]
            r["total"] = r["counted"]
            r["breakdown"] = " + ".join("%s %s" % (i["user"], _num(i["qty"])) for i in (items or []))
        return res

    @staticmethod
    def _sheets(d):
        out = []
        for title, rows, cols in ToruqCountDashboardPro._sheets(d):
            if title == "بانتظار الاعتماد":
                cols = [c for c in cols if c[0] != "requester"] + [
                    ("total", "إجمالي العدّ"),
                    ("breakdown", "التفصيل"),
                ]
            out.append((title, rows, cols))
        return out
