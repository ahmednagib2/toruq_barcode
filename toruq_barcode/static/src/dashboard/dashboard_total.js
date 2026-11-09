/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { ToruqCountDashboard } from "./dashboard";

const TOTAL_COLS = [
    { k: "total", l: "إجمالي العدّ", t: "num", sum: 1 },
    { k: "breakdown", l: "التفصيل (كل موظف / جهاز)" },
];
const DROP = new Set(["counter", "counted"]);

patch(ToruqCountDashboard.prototype, {
    get table() {
        const table = super.table;
        if (this.state.tab !== "counted" || !table.cols.length) {
            return table;
        }
        const all = (this.state.data && this.state.data.counted) || [];
        const hasLot = all.some((r) => r.lot);
        const cols = [];
        for (const col of table.cols) {
            if (col.k === "requester") {
                cols.push(...TOTAL_COLS);
            } else if (DROP.has(col.k) || (col.k === "lot" && !hasLot)) {
                continue;
            } else {
                cols.push(col);
            }
        }
        const totals = {
            ...table.totals,
            total: table.rows.reduce((acc, r) => acc + (Number(r.total) || 0), 0),
        };
        return { ...table, cols, totals, hasTotals: table.rows.length > 0 };
    },
});
