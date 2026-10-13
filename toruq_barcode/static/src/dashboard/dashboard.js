/** @odoo-module **/
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

const PERIODS = [
    { k: "day", l: "يوم" },
    { k: "week", l: "أسبوع" },
    { k: "month", l: "شهر" },
    { k: "quarter", l: "ربع سنة" },
    { k: "half", l: "نصف سنة" },
    { k: "year", l: "سنة" },
    { k: "custom", l: "مخصص" },
];
const TABS = [
    { k: "overview", l: "نظرة عامة" },
    { k: "due", l: "الجرد المطلوب" },
    { k: "counted", l: "بانتظار الاعتماد" },
    { k: "applied", l: "الجرد الفعلي" },
    { k: "diffs", l: "الفروقات" },
    { k: "stock", l: "المخزون التفصيلي" },
    { k: "shortage", l: "النواقص والسالب" },
    { k: "log", l: "السجل" },
];
const STOCK_VIEWS = [
    { k: "warehouse", l: "حسب الفرع" },
    { k: "location", l: "حسب الموقع" },
    { k: "category", l: "حسب الفئة" },
    { k: "product", l: "حسب المنتج" },
];

const C = {
    product: { k: "product", l: "المنتج" },
    location: { k: "location", l: "الموقع" },
    lot: { k: "lot", l: "الدفعة" },
    user: { k: "user", l: "المنفذ" },
    date: { k: "date", l: "التاريخ", t: "date" },
    system: { k: "system", l: "كمية النظام", t: "num" },
    counted: { k: "counted", l: "المعدود", t: "num" },
    diff: { k: "diff", l: "الفرق", t: "diff" },
    value: { k: "value", l: "قيمة الفرق", t: "diff" },
    products: { k: "products", l: "عدد المنتجات", t: "num" },
    on_hand: { k: "on_hand", l: "المتوفر", t: "num" },
    reserved: { k: "reserved", l: "المحجوز", t: "num" },
    available: { k: "available", l: "المتاح", t: "num" },
    money: { k: "value", l: "القيمة", t: "num" },
};
const TABLES = {
    due: {
        cols: [C.product, C.location, C.lot, { k: "qty", l: "كمية النظام", t: "num" }, { k: "due", l: "موعد الجرد" }, { k: "overdue", l: "متأخر (يوم)", t: "num" }],
        rows: (d) => d.due,
        empty: "لا توجد منتجات مطلوب جردها حتى نهاية الفترة.",
    },
    counted: {
        cols: [C.product, C.location, C.lot, { k: "qty", l: "كمية النظام", t: "num" }, C.counted, C.diff, C.value, { k: "counter", l: "العدّاد" }, { k: "requester", l: "الطالب" }],
        rows: (d) => d.counted,
        actions: true,
        empty: "لا توجد جرود بانتظار الاعتماد.",
    },
    applied: {
        cols: [C.date, C.product, C.location, C.user, C.system, C.counted, C.diff, C.value],
        rows: (d) => d.applied,
        empty: "لا توجد عمليات جرد منفذة في هذه الفترة (السجل يبدأ من تثبيت هذا الإصدار).",
    },
    diffs: {
        cols: [C.product, C.location, C.user, C.system, C.counted, C.diff, C.value],
        rows: (d) => d.diffs,
        empty: "لا توجد فروقات في هذه الفترة.",
    },
    shortage: {
        cols: [{ k: "kind", l: "النوع" }, C.product, { k: "where", l: "الفرع / الموقع" }, { k: "qty", l: "المتوفر", t: "num" }, { k: "min", l: "الحد الأدنى", t: "num" }, { k: "short", l: "العجز", t: "num" }],
        rows: (d) => d.shortage,
        empty: "لا توجد نواقص أو أرصدة سالبة (النواقص تعتمد على قواعد إعادة التخزين).",
    },
    log: {
        cols: [C.date, { k: "label", l: "الحدث" }, C.product, C.location, C.user, C.counted, C.diff],
        rows: (d) => d.log,
        empty: "لا توجد أحداث في هذه الفترة.",
    },
    stock_warehouse: {
        cols: [{ k: "name", l: "الفرع" }, C.products, C.on_hand, C.reserved, C.available, C.money],
        rows: (d) => d.stock.warehouse,
        empty: "لا توجد أرصدة.",
    },
    stock_location: {
        cols: [{ k: "name", l: "الموقع" }, { k: "warehouse", l: "الفرع" }, C.products, C.on_hand, C.reserved, C.available, C.money],
        rows: (d) => d.stock.location,
        empty: "لا توجد أرصدة.",
    },
    stock_category: {
        cols: [{ k: "name", l: "الفئة" }, C.products, C.on_hand, C.reserved, C.available, C.money],
        rows: (d) => d.stock.category,
        empty: "لا توجد أرصدة.",
    },
    stock_product: {
        cols: [C.product, { k: "category", l: "الفئة" }, C.on_hand, C.reserved, C.available, C.money, { k: "min", l: "الحد الأدنى", t: "num" }, { k: "status_label", l: "الحالة" }],
        rows: (d) => d.stock.product,
        empty: "لا توجد أرصدة.",
    },
};

const errText = (e) => String((e && e.data && e.data.message) || (e && e.message) || e);

export class ToruqCountDashboard extends Component {
    static template = "toruq_barcode.CountDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.periods = PERIODS;
        this.tabs = TABS;
        this.stockViews = STOCK_VIEWS;
        this.state = useState({
            loading: true,
            error: "",
            data: null,
            period: "month",
            offset: 0,
            dateFrom: "",
            dateTo: "",
            warehouse: "",
            tab: "overview",
            stockView: "warehouse",
            search: "",
            busy: false,
        });
        onWillStart(() => this.load());
    }

    // ---------------------------------------------------------------- data
    async load() {
        this.state.loading = true;
        this.state.error = "";
        try {
            const data = await rpc("/toruq/count_dashboard", {
                period: this.state.period,
                offset: this.state.offset,
                warehouse_id: this.state.warehouse ? parseInt(this.state.warehouse, 10) : false,
                date_from: this.state.dateFrom || false,
                date_to: this.state.dateTo || false,
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

    // ------------------------------------------------------------- getters
    get hasData() {
        return !!this.state.data;
    }
    get rootStyle() {
        const c = (this.state.data && this.state.data.company) || {};
        return `--tq-brand:${c.primary || "#ff3d00"};--tq-dark:${c.secondary || "#2b2b2b"};`;
    }
    get company() {
        return (this.state.data && this.state.data.company) || {};
    }
    get subtitle() {
        const d = this.state.data;
        return d ? `${d.company.name} • ${d.range.from} ← ${d.range.to}` : "";
    }
    get rangeLabel() {
        const d = this.state.data;
        return d ? `${d.range.from} ← ${d.range.to}` : "";
    }
    get isCustom() {
        return this.state.period === "custom";
    }
    get cannotGoForward() {
        return this.state.offset === 0;
    }
    get isStock() {
        return this.state.tab === "stock";
    }
    get isOverview() {
        return this.state.tab === "overview";
    }
    get showCounted() {
        return this.state.tab === "counted";
    }
    get warnings() {
        return (this.state.data && this.state.data.warnings) || [];
    }
    get progressText() {
        return this.state.data ? `${this.state.data.kpis.progress}%` : "";
    }
    get donutStyle() {
        const p = this.state.data ? this.state.data.kpis.progress : 0;
        return `background: conic-gradient(var(--tq-brand) ${p}%, #e9ecef 0);`;
    }
    get trend() {
        return (this.state.data && this.state.data.overview.trend) || [];
    }
    get trendMax() {
        let max = 1;
        for (const b of this.trend) {
            max = Math.max(max, b.applied, b.submitted, b.requested);
        }
        return max;
    }
    get usersRows() {
        return (this.state.data && this.state.data.overview.users) || [];
    }
    get progressWh() {
        return (this.state.data && this.state.data.overview.progress_wh) || [];
    }
    get kpis() {
        const k = this.state.data ? this.state.data.kpis : {};
        const cur = this.company.currency || "";
        return [
            { key: "stock", tab: "stock", label: "المخزون الحالي", value: this.fmt(k.on_hand), sub: `القيمة ${this.fmt(k.value)} ${cur}`, tone: "dark" },
            { key: "reserved", tab: "stock", label: "المحجوز", value: this.fmt(k.reserved), sub: `المتاح ${this.fmt(k.available)}`, tone: "info" },
            { key: "due", tab: "due", label: "الجرد المطلوب", value: this.fmt(k.due_total), sub: `متأخر ${this.fmt(k.overdue)}`, tone: "warn" },
            { key: "applied", tab: "applied", label: "تم جرده فعلياً", value: this.fmt(k.applied), sub: `الدقة ${k.accuracy || 0}%`, tone: "good" },
            { key: "pending", tab: "counted", label: "بانتظار الاعتماد", value: this.fmt(k.pending), sub: `فرق ${this.fmt(k.pending_value)} ${cur}`, tone: "info" },
            { key: "progress", tab: "overview", label: "نسبة الإنجاز", value: `${k.progress || 0}%`, sub: "المنجز مقابل المطلوب", tone: "good" },
            { key: "adjust", tab: "diffs", label: "قيمة التسويات", value: this.fmt((k.gain_value || 0) - (k.loss_value || 0)), sub: `زيادة ${this.fmt(k.gain_value)} / عجز ${this.fmt(k.loss_value)}`, tone: "warn" },
            { key: "low", tab: "shortage", label: "أصناف ناقصة", value: this.fmt(k.low), sub: "أقل من الحد الأدنى", tone: "bad" },
            { key: "negative", tab: "shortage", label: "رصيد سالب", value: this.fmt(k.negative), sub: "يحتاج جرداً تصحيحياً", tone: "bad" },
        ];
    }
    get table() {
        const d = this.state.data;
        if (!d) {
            return { cols: [], rows: [], total: 0, empty: "" };
        }
        const key = this.state.tab === "stock" ? `stock_${this.state.stockView}` : this.state.tab;
        const cfg = TABLES[key];
        if (!cfg) {
            return { cols: [], rows: [], total: 0, empty: "" };
        }
        const all = cfg.rows(d) || [];
        const q = this.state.search.trim().toLowerCase();
        const rows = q
            ? all.filter((r) => cfg.cols.some((c) => String(r[c.k] === undefined ? "" : r[c.k]).toLowerCase().includes(q)))
            : all;
        return { cols: cfg.cols, rows, total: all.length, empty: cfg.empty, actions: !!cfg.actions };
    }

    // ------------------------------------------------------------- helpers
    fmt(n) {
        return Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 2 });
    }
    fmtDate(value) {
        if (!value) {
            return "";
        }
        const d = new Date(String(value).replace(" ", "T") + "Z");
        if (isNaN(d.getTime())) {
            return String(value);
        }
        return d.toLocaleString([], { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
    }
    cellText(row, col) {
        const v = row[col.k];
        if (v === undefined || v === null) {
            return "";
        }
        if (col.t === "num") {
            return this.fmt(v);
        }
        if (col.t === "diff") {
            return (v > 0 ? "+" : "") + this.fmt(v);
        }
        if (col.t === "date") {
            return this.fmtDate(v);
        }
        return String(v);
    }
    cellClass(row, col) {
        const v = row[col.k];
        if (col.t === "diff") {
            return v < 0 ? "text-danger fw-bold" : v > 0 ? "text-success fw-bold" : "";
        }
        if (col.k === "status_label") {
            return `o_tq_status is-${row.status}`;
        }
        if (col.k === "overdue" && v > 0) {
            return "text-danger fw-bold";
        }
        return col.t ? "o_tq_num" : "";
    }
    barStyle(value, max) {
        const pct = max ? Math.round((value * 100) / max) : 0;
        return `height:${Math.max(pct, value ? 4 : 0)}%`;
    }
    widthStyle(pct) {
        return `width:${pct || 0}%`;
    }
    kpiClass(kpi) {
        return `o_tq_kpi is-${kpi.tone}`;
    }
    periodClass(key) {
        return `o_tq_chip ${this.state.period === key ? "is-active" : ""}`;
    }
    tabClass(key) {
        return `o_tq_tab ${this.state.tab === key ? "is-active" : ""}`;
    }
    stockViewClass(key) {
        return `o_tq_chip ${this.state.stockView === key ? "is-active" : ""}`;
    }
    isSelectedWarehouse(id) {
        return `${id}` === this.state.warehouse;
    }

    // ------------------------------------------------------------- actions
    setPeriod(key) {
        this.state.period = key;
        this.state.offset = 0;
        if (key !== "custom") {
            this.load();
        }
    }
    shift(delta) {
        const next = this.state.offset + delta;
        if (next < 0) {
            return;
        }
        this.state.offset = next;
        this.load();
    }
    onCustom(field, ev) {
        this.state[field] = ev.target.value;
        if (this.state.dateFrom && this.state.dateTo) {
            this.load();
        }
    }
    onWarehouse(ev) {
        this.state.warehouse = ev.target.value;
        this.load();
    }
    onSearch(ev) {
        this.state.search = ev.target.value;
    }
    setTab(key) {
        this.state.tab = key;
        this.state.search = "";
    }
    setStockView(key) {
        this.state.stockView = key;
        this.state.search = "";
    }
    print() {
        window.print();
    }
    exportCsv() {
        const t = this.table;
        if (!t.cols.length) {
            return;
        }
        const esc = (s) => `"${String(s).replace(/"/g, '""')}"`;
        const lines = [t.cols.map((c) => esc(c.l)).join(",")];
        for (const r of t.rows) {
            lines.push(t.cols.map((c) => esc(this.cellText(r, c))).join(","));
        }
        const blob = new Blob(["\ufeff" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `toruq_count_${this.state.tab}.csv`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
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
