/** @odoo-module **/
import { registry } from '@web/core/registry';
import { rpc } from '@web/core/network/rpc';
import { useService } from '@web/core/utils/hooks';
import { Component, onWillStart, onWillUnmount, useState } from '@odoo/owl';

const PREF_KEY = 'toruq_dash_prefs_v2';
const PERIODS = [
    { k: 'day', l: 'يوم' },
    { k: 'week', l: 'أسبوع' },
    { k: 'month', l: 'شهر' },
    { k: 'quarter', l: 'ربع سنة' },
    { k: 'half', l: 'نصف سنة' },
    { k: 'year', l: 'سنة' },
    { k: 'custom', l: 'مخصص' },
];
const TABS = [
    { k: 'overview', l: 'نظرة عامة' },
    { k: 'analytics', l: 'تحليلات' },
    { k: 'due', l: 'الجرد المطلوب' },
    { k: 'counted', l: 'بانتظار الاعتماد' },
    { k: 'applied', l: 'الجرد الفعلي' },
    { k: 'diffs', l: 'الفروقات' },
    { k: 'stock', l: 'المخزون التفصيلي' },
    { k: 'shortage', l: 'النواقص والسالب' },
    { k: 'aging', l: 'لم تُجرد' },
    { k: 'log', l: 'السجل' },
];
const STOCK_VIEWS = [
    { k: 'warehouse', l: 'حسب الفرع' },
    { k: 'location', l: 'حسب الموقع' },
    { k: 'category', l: 'حسب الفئة' },
    { k: 'product', l: 'حسب المنتج' },
];
const STATUSES = [
    { k: '', l: 'كل الحالات' },
    { k: 'ok', l: 'كافٍ' },
    { k: 'low', l: 'ناقص' },
    { k: 'out', l: 'نفد' },
    { k: 'negative', l: 'سالب' },
];
const AGING_DAYS = [30, 60, 90, 180, 365];
const PAGE_SIZES = [25, 50, 100, 250];

const n = (k, l, extra = {}) => ({ k, l, t: 'num', ...extra });
const C = {
    product: { k: 'product', l: 'المنتج' },
    location: { k: 'location', l: 'الموقع' },
    lot: { k: 'lot', l: 'الدفعة' },
    user: { k: 'user', l: 'المنفذ' },
    date: { k: 'date', l: 'التاريخ', t: 'date' },
    system: n('system', 'كمية النظام', { sum: 1 }),
    counted: n('counted', 'المعدود', { sum: 1 }),
    diff: { k: 'diff', l: 'الفرق', t: 'diff', sum: 1 },
    value: { k: 'value', l: 'قيمة الفرق', t: 'diff', sum: 1 },
    products: n('products', 'عدد المنتجات', { sum: 1 }),
    on_hand: n('on_hand', 'المتوفر', { sum: 1 }),
    reserved: n('reserved', 'المحجوز', { sum: 1 }),
    available: n('available', 'المتاح', { sum: 1 }),
    money: n('value', 'القيمة', { sum: 1 }),
};
const TABLES = {
    due: {
        cols: [C.product, C.location, C.lot, n('qty', 'كمية النظام', { sum: 1 }), { k: 'due', l: 'موعد الجرد' }, n('overdue', 'متأخر (يوم)')],
        rows: (d) => d.due,
        empty: 'لا توجد منتجات مطلوب جردها حتى نهاية الفترة.',
    },
    counted: {
        cols: [C.product, C.location, C.lot, n('qty', 'كمية النظام', { sum: 1 }), C.counted, C.diff, n('diff_pct', 'الفرق %'), C.value, { k: 'counter', l: 'العدّاد' }, { k: 'requester', l: 'الطالب' }],
        rows: (d) => d.counted,
        actions: true,
        empty: 'لا توجد جرود بانتظار الاعتماد.',
    },
    applied: {
        cols: [C.date, C.product, C.location, C.user, C.system, C.counted, C.diff, C.value],
        rows: (d) => d.applied,
        empty: 'لا توجد عمليات جرد منفذة في هذه الفترة.',
    },
    diffs: {
        cols: [C.product, C.location, C.user, C.system, C.counted, C.diff, C.value],
        rows: (d) => d.diffs,
        empty: 'لا توجد فروقات في هذه الفترة.',
    },
    shortage: {
        cols: [{ k: 'kind', l: 'النوع' }, C.product, { k: 'where', l: 'الفرع / الموقع' }, n('qty', 'المتوفر', { sum: 1 }), n('min', 'الحد الأدنى'), n('short', 'العجز', { sum: 1 })],
        rows: (d) => d.shortage,
        empty: 'لا توجد نواقص أو أرصدة سالبة (النواقص تعتمد على قواعد إعادة التخزين).',
    },
    aging: {
        cols: [C.product, { k: 'category', l: 'الفئة' }, C.on_hand, C.money, { k: 'last', l: 'آخر جرد', t: 'date' }, n('days', 'منذ (يوم)')],
        rows: (d) => d.aging,
        empty: 'كل الأصناف جُردت خلال المدة المحددة.',
    },
    log: {
        cols: [C.date, { k: 'label', l: 'الحدث' }, C.product, C.location, C.user, C.counted, C.diff, { k: 'note', l: 'ملاحظة' }],
        rows: (d) => d.log,
        empty: 'لا توجد أحداث في هذه الفترة.',
    },
    stock_warehouse: {
        cols: [{ k: 'name', l: 'الفرع' }, C.products, C.on_hand, C.reserved, C.available, C.money],
        rows: (d) => d.stock.warehouse,
        empty: 'لا توجد أرصدة.',
    },
    stock_location: {
        cols: [{ k: 'name', l: 'الموقع' }, { k: 'warehouse', l: 'الفرع' }, C.products, C.on_hand, C.reserved, C.available, C.money],
        rows: (d) => d.stock.location,
        empty: 'لا توجد أرصدة.',
    },
    stock_category: {
        cols: [{ k: 'name', l: 'الفئة' }, C.products, C.on_hand, C.reserved, C.available, C.money],
        rows: (d) => d.stock.category,
        empty: 'لا توجد أرصدة.',
    },
    stock_product: {
        cols: [C.product, { k: 'category', l: 'الفئة' }, { k: 'abc', l: 'ABC' }, C.on_hand, C.reserved, C.available, C.money, n('min', 'الحد الأدنى'), { k: 'status_label', l: 'الحالة' }],
        rows: (d) => d.stock.product,
        empty: 'لا توجد أرصدة.',
    },
};

const errText = (e) => String((e && e.data && e.data.message) || (e && e.message) || e);
const loadPrefs = () => {
    try {
        return JSON.parse(localStorage.getItem(PREF_KEY) || '{}') || {};
    } catch (e) {
        return {};
    }
};

export class ToruqCountDashboard extends Component {
    static template = 'toruq_barcode.CountDashboard';
    static props = ['*'];

    setup() {
        this.action = useService('action');
        this.notification = useService('notification');
        this.periods = PERIODS;
        this.tabs = TABS;
        this.stockViews = STOCK_VIEWS;
        this.statuses = STATUSES;
        this.agingOptions = AGING_DAYS;
        this.pageSizes = PAGE_SIZES;
        const pr = loadPrefs();
        this.state = useState({
            loading: true,
            error: '',
            data: null,
            period: pr.period && pr.period !== 'custom' ? pr.period : 'month',
            offset: 0,
            dateFrom: '',
            dateTo: '',
            warehouse: pr.warehouse || '',
            category: pr.category || '',
            user: pr.user || '',
            location: pr.location || '',
            agingDays: pr.agingDays || 90,
            tab: pr.tab || 'overview',
            stockView: pr.stockView || 'warehouse',
            status: '',
            search: '',
            page: 1,
            pageSize: pr.pageSize || 50,
            sortKey: '',
            sortDir: 1,
            selected: {},
            pctLimit: pr.pctLimit || 10,
            valLimit: pr.valLimit || 500,
            auto: !!pr.auto,
            busy: false,
            modal: null,
            printing: false,
        });
        this.timer = null;
        onWillStart(async () => {
            await this.load();
            this.applyAuto();
        });
        onWillUnmount(() => clearInterval(this.timer));
    }

    // ---------------------------------------------------------------- data
    params() {
        const s = this.state;
        return {
            period: s.period,
            offset: s.offset,
            warehouse_id: s.warehouse,
            category_id: s.category,
            user_id: s.user,
            location_id: s.location,
            aging_days: s.agingDays,
            date_from: s.dateFrom || false,
            date_to: s.dateTo || false,
        };
    }
    async load() {
        this.state.loading = true;
        this.state.error = '';
        try {
            const data = await rpc('/toruq/count_dashboard/pro', this.params());
            if (data.error) {
                this.state.error = 'هذه اللوحة للمديرين فقط.';
                this.state.data = null;
            } else {
                this.state.data = data;
                this.state.selected = {};
            }
        } catch (e) {
            this.state.error = errText(e);
        } finally {
            this.state.loading = false;
        }
    }
    savePrefs() {
        const s = this.state;
        try {
            localStorage.setItem(
                PREF_KEY,
                JSON.stringify({
                    period: s.period,
                    warehouse: s.warehouse,
                    category: s.category,
                    user: s.user,
                    location: s.location,
                    agingDays: s.agingDays,
                    tab: s.tab,
                    stockView: s.stockView,
                    pageSize: s.pageSize,
                    pctLimit: s.pctLimit,
                    valLimit: s.valLimit,
                    auto: s.auto,
                })
            );
        } catch (e) {
            /* storage unavailable */
        }
    }
    applyAuto() {
        clearInterval(this.timer);
        if (this.state.auto) {
            this.timer = setInterval(() => {
                if (!this.state.busy && !this.state.modal && !this.state.loading) {
                    this.load();
                }
            }, 300000);
        }
    }
    toggleAuto() {
        this.state.auto = !this.state.auto;
        this.applyAuto();
        this.savePrefs();
    }

    // ------------------------------------------------------------- getters
    get hasData() {
        return !!this.state.data;
    }
    get rootStyle() {
        const c = this.company;
        return `--tq-brand:${c.primary || '#ff3d00'};--tq-dark:${c.secondary || '#2b2b2b'};`;
    }
    get company() {
        return (this.state.data && this.state.data.company) || {};
    }
    get subtitle() {
        const d = this.state.data;
        return d ? `${d.company.name} • ${d.range.from} ← ${d.range.to}` : '';
    }
    get rangeLabel() {
        const d = this.state.data;
        return d ? `${d.range.from} ← ${d.range.to}` : '';
    }
    get isCustom() {
        return this.state.period === 'custom';
    }
    get cannotGoForward() {
        return this.state.offset === 0;
    }
    get isOverview() {
        return this.state.tab === 'overview';
    }
    get isAnalytics() {
        return this.state.tab === 'analytics';
    }
    get isTable() {
        return !this.isOverview && !this.isAnalytics;
    }
    get isStock() {
        return this.state.tab === 'stock';
    }
    get isStockProduct() {
        return this.isStock && this.state.stockView === 'product';
    }
    get isCounted() {
        return this.state.tab === 'counted';
    }
    get isAging() {
        return this.state.tab === 'aging';
    }
    get warnings() {
        return (this.state.data && this.state.data.warnings) || [];
    }
    get filterOptions() {
        const d = this.state.data || {};
        return {
            warehouse: d.warehouses || [],
            category: d.categories || [],
            user: d.users || [],
            location: d.locations || [],
        };
    }
    get progressText() {
        return this.state.data ? `${this.state.data.kpis.progress}%` : '';
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
    get categoriesBars() {
        return (this.state.data && this.state.data.overview.categories) || [];
    }
    get analytics() {
        return (this.state.data && this.state.data.analytics) || { shrink: [], users: [], wh_accuracy: [], abc: [] };
    }
    delta(cur, prev, points) {
        if (prev === undefined || prev === null) {
            return null;
        }
        if (points) {
            const d = Math.round((cur - prev) * 10) / 10;
            return d ? { txt: `${d > 0 ? '▲' : '▼'} ${Math.abs(d)} نقطة`, up: d > 0 } : null;
        }
        if (!prev) {
            return cur ? { txt: 'جديد', up: true } : null;
        }
        const d = Math.round(((cur - prev) * 1000) / Math.abs(prev)) / 10;
        return d ? { txt: `${d > 0 ? '▲' : '▼'} ${Math.abs(d)}%`, up: d > 0 } : null;
    }
    get kpis() {
        const k = this.state.data ? this.state.data.kpis : {};
        const pv = k.prev || {};
        const cur = this.company.currency || '';
        const net = (k.gain_value || 0) - (k.loss_value || 0);
        return [
            { key: 'stock', tab: 'stock', label: 'المخزون الحالي', value: this.fmt(k.on_hand), sub: `القيمة ${this.fmt(k.value)} ${cur}`, tone: 'dark' },
            { key: 'reserved', tab: 'stock', label: 'المحجوز', value: this.fmt(k.reserved), sub: `المتاح ${this.fmt(k.available)}`, tone: 'info' },
            { key: 'due', tab: 'due', label: 'الجرد المطلوب', value: this.fmt(k.due_total), sub: `متأخر ${this.fmt(k.overdue)}`, tone: 'warn' },
            { key: 'applied', tab: 'applied', label: 'تم جرده فعلياً', value: this.fmt(k.applied), sub: `الدقة ${k.accuracy || 0}%`, tone: 'good', delta: this.delta(k.applied, pv.applied) },
            { key: 'pending', tab: 'counted', label: 'بانتظار الاعتماد', value: this.fmt(k.pending), sub: `فرق ${this.fmt(k.pending_value)} ${cur}`, tone: 'info' },
            { key: 'progress', tab: 'overview', label: 'نسبة الإنجاز', value: `${k.progress || 0}%`, sub: 'المنجز مقابل المطلوب', tone: 'good' },
            { key: 'accuracy', tab: 'analytics', label: 'دقة الجرد', value: `${k.accuracy || 0}%`, sub: 'مطابق للنظام', tone: 'good', delta: this.delta(k.accuracy, pv.accuracy, true) },
            { key: 'adjust', tab: 'diffs', label: 'قيمة التسويات', value: this.fmt(net), sub: `زيادة ${this.fmt(k.gain_value)} / عجز ${this.fmt(k.loss_value)}`, tone: 'warn', delta: this.delta(net, pv.net) },
            { key: 'low', tab: 'shortage', label: 'أصناف ناقصة', value: this.fmt(k.low), sub: 'أقل من الحد الأدنى', tone: 'bad' },
            { key: 'negative', tab: 'shortage', label: 'رصيد سالب', value: this.fmt(k.negative), sub: 'يحتاج جرداً تصحيحياً', tone: 'bad' },
            { key: 'aging', tab: 'aging', label: 'لم تُجرد', value: this.fmt(k.aging_total), sub: `منذ ${k.aging_days || ''} يوم • ${this.fmt(k.aging_value)} ${cur}`, tone: 'warn' },
        ];
    }
    get table() {
        const d = this.state.data;
        const empty = { cols: [], rows: [], pageRows: [], total: 0, filtered: 0, totals: {}, hasTotals: false, pages: 1, page: 1, empty: '', actions: false };
        if (!d) {
            return empty;
        }
        const s = this.state;
        const key = s.tab === 'stock' ? `stock_${s.stockView}` : s.tab;
        const cfg = TABLES[key];
        if (!cfg) {
            return empty;
        }
        let rows = cfg.rows(d) || [];
        const total = rows.length;
        const q = s.search.trim().toLowerCase();
        if (q) {
            rows = rows.filter((r) => cfg.cols.some((c) => String(r[c.k] === undefined ? '' : r[c.k]).toLowerCase().includes(q)));
        }
        if (key === 'stock_product' && s.status) {
            rows = rows.filter((r) => r.status === s.status);
        }
        if (s.sortKey) {
            const dir = s.sortDir;
            rows = [...rows].sort((a, b) => {
                const x = a[s.sortKey];
                const y = b[s.sortKey];
                if (typeof x === 'number' && typeof y === 'number') {
                    return (x - y) * dir;
                }
                return String(x === undefined || x === null ? '' : x).localeCompare(String(y === undefined || y === null ? '' : y), 'ar') * dir;
            });
        }
        const totals = {};
        for (const c of cfg.cols) {
            if (c.sum) {
                totals[c.k] = rows.reduce((acc, r) => acc + (Number(r[c.k]) || 0), 0);
            }
        }
        const size = s.printing ? Math.max(rows.length, 1) : s.pageSize;
        const pages = Math.max(1, Math.ceil(rows.length / size));
        const page = Math.min(s.page, pages);
        return {
            cols: cfg.cols,
            rows,
            pageRows: rows.slice((page - 1) * size, page * size),
            total,
            filtered: rows.length,
            totals,
            hasTotals: Object.keys(totals).length > 0 && rows.length > 0,
            pages,
            page,
            empty: cfg.empty,
            actions: !!cfg.actions,
        };
    }
    get showPager() {
        return this.table.filtered > 0;
    }
    get allSelected() {
        const rows = this.table.pageRows;
        return rows.length > 0 && rows.every((r) => this.state.selected[r.id]);
    }
    get selectedCount() {
        return Object.keys(this.state.selected).length;
    }
    get isRejectModal() {
        return !!this.state.modal && this.state.modal.type === 'reject';
    }
    get modalTitle() {
        return this.isRejectModal ? 'رفض الجرد' : 'اعتماد الجرد';
    }
    get modalText() {
        const m = this.state.modal;
        if (!m) {
            return '';
        }
        const what = m.type === 'reject' ? 'رفض وتصفير الكمية المعدودة لـ' : 'اعتماد وتطبيق جرد';
        return `سيتم ${what} ${m.ids.length} سطر.`;
    }

    // ------------------------------------------------------------- helpers
    fmt(v) {
        return Number(v || 0).toLocaleString('en-US', { maximumFractionDigits: 2 });
    }
    fmtDate(value) {
        if (!value) {
            return '';
        }
        const d = new Date(String(value).replace(' ', 'T') + 'Z');
        if (isNaN(d.getTime())) {
            return String(value);
        }
        return d.toLocaleString([], { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
    }
    cellText(row, col) {
        const v = row[col.k];
        if (col.k === 'last' && !v) {
            return 'لم يُجرد';
        }
        if (v === undefined || v === null) {
            return '';
        }
        if (col.t === 'num') {
            return this.fmt(v);
        }
        if (col.t === 'diff') {
            return (v > 0 ? '+' : '') + this.fmt(v);
        }
        if (col.t === 'date') {
            return this.fmtDate(v);
        }
        return String(v);
    }
    cellClass(row, col) {
        const v = row[col.k];
        if (col.t === 'diff') {
            return v < 0 ? 'text-danger fw-bold' : v > 0 ? 'text-success fw-bold' : '';
        }
        if (col.k === 'status_label') {
            return `o_tq_status is-${row.status}`;
        }
        if (col.k === 'abc' && v) {
            return `o_tq_abc is-${v}`;
        }
        if (col.k === 'overdue' && v > 0) {
            return 'text-danger fw-bold';
        }
        return col.t ? 'o_tq_num' : '';
    }
    totalText(col, index) {
        if (col.sum) {
            const v = this.table.totals[col.k];
            return (col.t === 'diff' && v > 0 ? '+' : '') + this.fmt(v);
        }
        return index === 0 ? `الإجمالي (${this.table.filtered})` : '';
    }
    isBig(row) {
        return this.isCounted && (Math.abs(row.diff_pct || 0) >= this.state.pctLimit || Math.abs(row.value || 0) >= this.state.valLimit);
    }
    rowClass(row) {
        return `o_tq_row ${this.isBig(row) ? 'is-big' : ''} ${this.state.selected[row.id] ? 'is-sel' : ''}`;
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
        return `o_tq_chip ${this.state.period === key ? 'is-active' : ''}`;
    }
    tabClass(key) {
        return `o_tq_tab ${this.state.tab === key ? 'is-active' : ''}`;
    }
    stockViewClass(key) {
        return `o_tq_chip ${this.state.stockView === key ? 'is-active' : ''}`;
    }
    isChosen(field, id) {
        return `${id}` === `${this.state[field]}`;
    }
    sortMark(key) {
        return this.state.sortKey === key ? (this.state.sortDir > 0 ? '▲' : '▼') : '';
    }
    noop() {}

    // ------------------------------------------------------------- actions
    setPeriod(key) {
        this.state.period = key;
        this.state.offset = 0;
        this.state.page = 1;
        this.savePrefs();
        if (key !== 'custom') {
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
    onFilter(field, ev) {
        this.state[field] = ev.target.value;
        this.state.page = 1;
        this.savePrefs();
        this.load();
    }
    onAging(ev) {
        this.state.agingDays = parseInt(ev.target.value, 10) || 90;
        this.savePrefs();
        this.load();
    }
    onStatus(ev) {
        this.state.status = ev.target.value;
        this.state.page = 1;
    }
    onSearch(ev) {
        this.state.search = ev.target.value;
        this.state.page = 1;
    }
    onLimit(field, ev) {
        this.state[field] = Number(ev.target.value) || 0;
        this.savePrefs();
    }
    setPageSize(ev) {
        this.state.pageSize = parseInt(ev.target.value, 10) || 50;
        this.state.page = 1;
        this.savePrefs();
    }
    goPage(delta) {
        const t = this.table;
        this.state.page = Math.min(Math.max(t.page + delta, 1), t.pages);
    }
    setTab(key) {
        this.state.tab = key;
        this.state.search = '';
        this.state.status = '';
        this.state.sortKey = '';
        this.state.page = 1;
        this.savePrefs();
    }
    setStockView(key) {
        this.state.stockView = key;
        this.state.search = '';
        this.state.status = '';
        this.state.sortKey = '';
        this.state.page = 1;
        this.savePrefs();
    }
    sortBy(key) {
        if (this.state.sortKey === key) {
            this.state.sortDir = -this.state.sortDir;
        } else {
            this.state.sortKey = key;
            this.state.sortDir = 1;
        }
        this.state.page = 1;
    }
    async print() {
        this.state.printing = true;
        await new Promise((resolve) => setTimeout(resolve, 80));
        window.print();
        this.state.printing = false;
    }
    exportXlsx() {
        const q = new URLSearchParams();
        for (const [k, v] of Object.entries(this.params())) {
            if (v !== false && v !== '' && v !== null && v !== undefined) {
                q.set(k, v);
            }
        }
        window.open(`/toruq/count_dashboard/export?${q.toString()}`, '_blank');
    }
    exportCsv() {
        const t = this.table;
        if (!t.cols.length) {
            return;
        }
        const esc = (s) => `"${String(s).replace(/"/g, '""')}"`;
        const lines = [t.cols.map((c) => esc(c.l)).join(',')];
        for (const r of t.rows) {
            lines.push(t.cols.map((c) => esc(this.cellText(r, c))).join(','));
        }
        const blob = new Blob(['\ufeff' + lines.join('\n')], { type: 'text/csv;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
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
            type: 'ir.actions.act_window',
            res_model: 'product.product',
            res_id: productId,
            views: [[false, 'form']],
            target: 'current',
        });
    }

    // ----------------------------------------------------------- selection
    toggleSel(row) {
        const s = { ...this.state.selected };
        if (s[row.id]) {
            delete s[row.id];
        } else {
            s[row.id] = true;
        }
        this.state.selected = s;
    }
    toggleAll() {
        const s = { ...this.state.selected };
        const on = !this.allSelected;
        for (const r of this.table.pageRows) {
            if (on) {
                s[r.id] = true;
            } else {
                delete s[r.id];
            }
        }
        this.state.selected = s;
    }
    selectMatching() {
        const s = {};
        for (const r of this.table.rows) {
            if (!r.diff) {
                s[r.id] = true;
            }
        }
        this.state.selected = s;
    }
    bulkSelected(type) {
        this.askBulk(type, this.table.rows.filter((r) => this.state.selected[r.id]));
    }

    // --------------------------------------------------------- bulk modal
    askBulk(type, rows) {
        const ids = rows.map((r) => r.id).filter(Boolean);
        if (!ids.length) {
            this.notification.add('حدّد سطراً واحداً على الأقل.', { type: 'warning' });
            return;
        }
        this.state.modal = { type, ids, reason: '', error: '', result: null };
    }
    closeModal() {
        if (!this.state.busy) {
            this.state.modal = null;
        }
    }
    onReason(ev) {
        this.state.modal.reason = ev.target.value;
    }
    async confirmModal() {
        const m = this.state.modal;
        if (!m || this.state.busy || m.result) {
            return;
        }
        if (m.type === 'reject' && !m.reason.trim()) {
            m.error = 'اكتب سبب الرفض.';
            return;
        }
        this.state.busy = true;
        m.error = '';
        try {
            const res = await rpc('/toruq/count_dashboard/bulk', { ids: m.ids, action: m.type, reason: m.reason });
            if (res.error) {
                m.error = res.error === 'reason' ? 'اكتب سبب الرفض.' : 'غير مسموح.';
            } else {
                m.result = res;
                await this.load();
            }
        } catch (e) {
            m.error = errText(e);
        } finally {
            this.state.busy = false;
        }
    }
}

registry.category('actions').add('toruq_count_dashboard', ToruqCountDashboard);
