/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { ToruqCountDashboard } from "./dashboard";

const TOTAL_COLS = [
    { k: "total", l: "إجمالي العدّ", t: "num" },
    { k: "breakdown", l: "التفصيل (كل موظف / جهاز)" },
];

patch(ToruqCountDashboard.prototype, {
    get table() {
        const table = super.table;
        if (this.state.tab !== "counted" || !table.cols.length) {
            return table;
        }
        const cols = [];
        for (const col of table.cols) {
            if (col.k === "requester") {
                cols.push(...TOTAL_COLS);
            } else {
                cols.push(col);
            }
        }
        return { ...table, cols };
    },
});
