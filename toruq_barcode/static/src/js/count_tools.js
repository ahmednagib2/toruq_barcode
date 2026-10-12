/** @odoo-module **/
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { session } from "@web/session";
import { patch } from "@web/core/utils/patch";
import { onWillDestroy } from "@odoo/owl";

const CLIENT_SEL = ".o_barcode_client_action";
const APPLY_SEL = ".o_apply_page";
const OWN_SEL = ".o_tqx_overlay, .o_tqx_count";
const flags = session.toruq_barcode_flags || {};
const restricted = !!flags.count_only && !flags.manager;

const T = {
    count: "عدد المنتجات: ",
    title: "تأكيد المنتجات وتصديق الجرد",
    products: "عدد المنتجات:",
    validate: restricted ? "إرسال للاعتماد" : "تصديق",
    back: "رجوع",
    note: "سيتم إرسال الجرد للمدير للاعتماد.",
    disabled: "زر التصديق غير متاح حاليًا.",
    missing: "تعذر العثور على زر التصديق في الشاشة.",
    saving: "جاري حفظ المنتجات الممسوحة…",
    saved: "✓ تم حفظ المنتجات الممسوحة",
    savedN: (n) => `✓ تم حفظ المنتجات الممسوحة (${n})`,
    savedLess: (a, b) => `⚠ المحفوظ ${a} والممسوح ${b}. راجع الأسطر قبل التصديق.`,
    saveFail: "تعذر حفظ المنتجات: ",
    noModel: "تعذر الوصول لنموذج الباركود، أعد تحميل الصفحة.",
};

const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) {
        n.className = cls;
    }
    if (text !== undefined) {
        n.textContent = text;
    }
    return n;
};
const toLatin = (s) => s.replace(/[\u0660-\u0669]/g, (d) => String(d.charCodeAt(0) - 0x660));

let activeComp = null;
const patchedClasses = new Set();
const patchBarcodeActions = () => {
    const actions = registry.category("actions");
    for (const [key, C] of actions.getEntries()) {
        if (!String(key).startsWith("stock_barcode")) {
            continue;
        }
        if (typeof C !== "function" || !C.prototype || patchedClasses.has(C)) {
            continue;
        }
        patchedClasses.add(C);
        try {
            patch(C.prototype, {
                setup() {
                    super.setup(...arguments);
                    const comp = this;
                    activeComp = comp;
                    onWillDestroy(() => {
                        if (activeComp === comp) {
                            activeComp = null;
                        }
                    });
                },
            });
        } catch (e) {
            console.warn("toruq count patch skipped", key, e);
        }
    }
};
const getModel = () => {
    const m = activeComp && activeComp.env && activeComp.env.model;
    return m && typeof m.save === "function" ? m : null;
};

const toruqCountTools = {
    dependencies: ["notification"],
    start(env, { notification }) {
        const notify = (msg, type = "info") => notification.add(msg, { type });
        patchBarcodeActions();
        registry.category("actions").addEventListener("UPDATE", patchBarcodeActions);

        const closeOverlay = () => document.querySelector(".o_tqx_overlay")?.remove();

        // distinct products with a counted quantity on screen (never a sum of quantities)
        const countProducts = () => {
            const seen = new Set();
            document.querySelectorAll(CLIENT_SEL + " .o_barcode_line").forEach((line, i) => {
                const qtyEl = line.querySelector(".o_barcode_scanner_qty") || line.querySelector('[name="quantity"]');
                const m = toLatin((qtyEl && qtyEl.textContent) || "").match(/\d+(?:[.,]\d+)?/);
                const done = m ? parseFloat(m[0].replace(",", ".")) : 0;
                if (done > 0) {
                    const title = line.querySelector(".o_barcode_line_title");
                    const key = (title && title.textContent.trim().replace(/\s+/g, " ")) || line.dataset.virtualId || String(i);
                    seen.add(key);
                }
            });
            return seen.size;
        };
        const ensureCount = () => {
            const msg = document.querySelector(CLIENT_SEL + " .o_scan_message");
            const own = document.querySelector(".o_tqx_count");
            // toruq_branch_transfer shows the same counter; do not duplicate it
            if (!msg || document.querySelector(".o_brtx_count")) {
                own?.remove();
                return;
            }
            const text = T.count + countProducts();
            if (own && msg.nextElementSibling === own) {
                if (own.textContent !== text) {
                    own.textContent = text;
                }
                return;
            }
            own?.remove();
            msg.insertAdjacentElement("afterend", el("div", "o_tqx_count", text));
        };

        let bypass = false;
        const openConfirm = () => {
            if (document.querySelector(".o_tqx_overlay")) {
                return;
            }
            const count = countProducts();
            const model = getModel();
            const overlay = el("div", "o_tqx_overlay");
            const box = el("div", "o_tqx_box");
            overlay.appendChild(box);
            overlay.addEventListener("click", (ev) => {
                if (ev.target === overlay) {
                    closeOverlay();
                }
            });
            box.appendChild(el("h4", "", T.title));
            const row = el("div", "o_tqx_row");
            row.append(el("span", "o_tqx_label", T.products), el("span", "o_tqx_value", String(count)));
            box.appendChild(row);
            if (restricted) {
                box.appendChild(el("div", "o_tqx_note", T.note));
            }
            const status = el("div", "o_tqx_status is-saving", T.saving);
            const ok = el("button", "o_tqx_btn o_tqx_btn_primary", T.validate);
            ok.type = "button";
            ok.disabled = true;
            const back = el("button", "o_tqx_btn o_tqx_btn_secondary", T.back);
            back.type = "button";
            back.addEventListener("click", closeOverlay);
            ok.addEventListener("click", () => {
                if (ok.disabled) {
                    return;
                }
                ok.disabled = true;
                back.disabled = true;
                const target = document.querySelector(APPLY_SEL);
                closeOverlay();
                if (!target) {
                    notify(T.missing, "warning");
                    return;
                }
                if (target.disabled) {
                    notify(T.disabled, "warning");
                    return;
                }
                bypass = true;
                try {
                    target.click();
                } finally {
                    bypass = false;
                }
            });
            box.append(status, ok, back);
            document.body.appendChild(overlay);

            const setStatus = (kind, text) => {
                status.className = "o_tqx_status is-" + kind;
                status.textContent = text;
            };
            (async () => {
                let saveErr = null;
                if (model) {
                    try {
                        await model.save();
                    } catch (e) {
                        saveErr = e;
                    }
                } else {
                    saveErr = new Error(T.noModel);
                }
                if (!box.isConnected) {
                    return;
                }
                if (saveErr) {
                    setStatus("error", T.saveFail + ((saveErr && saveErr.message) || saveErr));
                    ok.disabled = false;
                    return;
                }
                try {
                    const res = (await rpc("/toruq/count_saved", {})) || {};
                    if (!box.isConnected) {
                        return;
                    }
                    if (typeof res.products !== "number") {
                        setStatus("saved", T.saved);
                    } else if (res.products >= count) {
                        setStatus("saved", T.savedN(res.products));
                    } else {
                        setStatus("warn", T.savedLess(res.products, count));
                    }
                } catch (e) {
                    if (box.isConnected) {
                        setStatus("saved", T.saved);
                    }
                }
                if (box.isConnected) {
                    ok.disabled = false;
                }
            })();
        };
        document.addEventListener(
            "click",
            (ev) => {
                const btn = ev.target.closest && ev.target.closest(APPLY_SEL);
                if (!btn || bypass || !btn.closest(CLIENT_SEL)) {
                    return;
                }
                ev.preventDefault();
                ev.stopImmediatePropagation();
                if (btn.disabled) {
                    notify(T.disabled, "warning");
                    return;
                }
                openConfirm();
            },
            true
        );

        let queued = false;
        const sync = () => {
            if (queued) {
                return;
            }
            queued = true;
            requestAnimationFrame(() => {
                queued = false;
                ensureCount();
            });
        };
        const isOwn = (m) => {
            const t = m.target.nodeType === 1 ? m.target : m.target.parentElement;
            return !!(t && t.closest && t.closest(OWN_SEL));
        };
        const begin = () => {
            new MutationObserver((list) => {
                if (!list.every(isOwn)) {
                    sync();
                }
            }).observe(document.body, { childList: true, subtree: true, characterData: true });
            sync();
        };
        if (document.body) {
            begin();
        } else {
            document.addEventListener("DOMContentLoaded", begin);
        }
        return {};
    },
};
registry.category("services").add("toruq_count_tools", toruqCountTools);
