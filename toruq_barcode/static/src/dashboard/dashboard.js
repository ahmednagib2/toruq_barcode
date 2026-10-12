/** @odoo-module **/
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

const TABS = [
    { key: "low", label: "ناقصة عن الحد الأدنى" },
    { key: "negative", label: "رصيد سالب" },
    { key: "to_count", label: "تحتاج جرد" },
    { key: "pending", label: "بانتظار الاعتماد" },
    { key: "events", label: "سجل الجرد" },
];

const errText = (e) => String((e && e.data && e.data.message) || (e && e.message) || e);

export class ToruqCountDashboard extends Component {
    static template = "toruq_barcode.CountDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            error: "",
            data: null,
            tab: "low",
            warehouse: "",
            busy: false,
        });
        onWillStart(() => this.load());
    }

    get tabs() {
        return TABS;
    }

    get kpis() {
        const k = (this.state.data && this.state.data.kpis) || {};
        return [
            { key: "low", label: "ناقصة عن الحد الأدنى", value: k.low || 0, cls: "is-danger" },
            { key: "negative", label: "رصيد سالب", value: k.negative || 0, cls: "is-danger" },
            { key: "to_count", label: "تحتاج جرد", value: k.to_count || 0, cls: "is-warning" },
            { key: "pending", label: "بانتظار الاعتماد", value: k.pending || 0, cls: "is-info" },
            { key: "events", label: "اعتُمد اليوم", value: k.applied_today || 0, cls: "is-success" },
        ];
    }

    fmtDate(value) {
        if (!value) {
            return "";
        }
        const d = new Date(String(value).replace(" ", "T") + "Z");
        if (isNaN(d.getTime())) {
            return String(value);
        }
        return d.toLocaleString([], {
            year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
        });
    }

    async load() {
        this.state.loading = true;
        this.state.error = "";
        try {
            const data = await rpc("/toruq/count_dashboard", {
                warehouse_id: this.state.warehouse ? parseInt(this.state.warehouse, 10) : false,
            });
            if (data.error) {
                this.state.error = "هذه اللوحة للمديرين فقط.";
                this.state.data = null;
            } else {
                this.state.data = data;
            }
        } catch (e) {
            this.state.error = errText(e);
        } finally {
            this.state.loading = false;
        }
    }

    onWarehouse(ev) {
        this.state.warehouse = ev.target.value;
        this.load();
    }

    setTab(key) {
        this.state.tab = key;
    }

    openProduct(productId) {
        if (!productId) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "product.product",
            res_id: productId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openList() {
        const d = this.state.data;
        const tab = this.state.tab;
        const common = {
            type: "ir.actions.act_window",
            target: "current",
            views: [[false, "list"], [false, "form"]],
        };
        if (tab === "low") {
            return this.action.doAction({
                ...common,
                name: "ناقصة عن الحد الأدنى",
                res_model: "stock.warehouse.orderpoint",
                domain: [["id", "in", d.low_op_ids]],
            });
        }
        if (tab === "events") {
            return this.action.doAction({ ...common, name: "سجل الجرد", res_model: "toruq.count.log", domain: [] });
        }
        const names = { negative: "رصيد سالب", to_count: "تحتاج جرد", pending: "بانتظار الاعتماد" };
        return this.action.doAction({
            ...common,
            name: names[tab],
            res_model: "stock.quant",
            domain: d.domains[tab],
            context: { inventory_mode: true },
        });
    }

    async approve(row) {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            const res = await this.orm.call("stock.quant", "action_apply_inventory", [[row.id]], {
                context: { inventory_mode: true },
            });
            if (res && res.type) {
                await this.action.doAction(res, { onClose: () => this.load() });
            } else {
                this.notification.add("تم اعتماد الجرد وتطبيقه.", { type: "success" });
                await this.load();
            }
        } catch (e) {
            this.notification.add(errText(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async reject(row) {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            await this.orm.call("stock.quant", "action_clear_inventory_quantity", [[row.id]], {
                context: { inventory_mode: true, toruq_reject: true },
            });
            this.notification.add("تم رفض الجرد وتصفير الكمية المعدودة.", { type: "warning" });
            await this.load();
        } catch (e) {
            this.notification.add(errText(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
}

registry.category("actions").add("toruq_count_dashboard", ToruqCountDashboard);
