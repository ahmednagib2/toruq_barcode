/** @odoo-module **/
import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";
import { onWillDestroy } from "@odoo/owl";

const flags = session.toruq_barcode_flags || {};
const LINE = ".o_barcode_client_action .o_barcode_line";
const isSmall = () => window.matchMedia("(max-width: 767.98px)").matches;
const toLatin = (s) => s.replace(/[\u0660-\u0669]/g, (d) => String(d.charCodeAt(0) - 0x660));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const T = {
    title: "الكمية الفعلية",
    ok: "موافق",
    cancel: "إلغاء",
    fail: "تعذر تحديث الكمية، استخدم الأزرار +1 / -1.",
    noModel: "تعذر الوصول لنموذج الباركود، أعد تحميل الصفحة.",
    saved: "✓ تم حفظ الكمية",
    saveFail: "تعذر حفظ الكمية: ",
};

if (flags.count_only || session.toruq_barcode_count_only) {
    let activeComp = null;
    let saveTimer = null;
    const patched = new Set();
    const patchActions = () => {
        for (const [key, C] of registry.category("actions").getEntries()) {
            if (!String(key).startsWith("stock_barcode")) {
                continue;
            }
            if (typeof C !== "function" || !C.prototype || patched.has(C)) {
                continue;
            }
            patched.add(C);
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
                console.warn("toruq mobile count patch skipped", key, e);
            }
        }
    };
    const getModel = () => {
        const m = activeComp && activeComp.env && activeComp.env.model;
        return m && typeof m.updateLineQty === "function" ? m : null;
    };
    const findRec = (model, vid) =>
        (model.pageLines || []).find((l) => String(l.virtual_id) === String(vid));
    const readQty = (line) => {
        const el = line && line.querySelector(".o_barcode_scanner_qty");
        const m = toLatin((el && el.textContent) || "").match(/\d+(?:[.,]\d+)?/);
        return m ? parseFloat(m[0].replace(",", ".")) : 0;
    };
    const findLine = (vid) => document.querySelector(`${LINE}[data-virtual-id="${vid}"]`);

    // same effect as pencil form + "تأكيد": write the counted quantity to the server
    const persist = async (model, vid, notify) => {
        const rec = findRec(model, vid);
        if (rec && rec.inventory_quantity_set === false) {
            rec.inventory_quantity_set = true;
        }
        if (typeof model.save !== "function") {
            return;
        }
        try {
            await model.save();
            notify(T.saved, "success");
        } catch (e) {
            notify(T.saveFail + ((e && e.message) || ""), "danger");
        }
    };

    // set an exact quantity; re-checks the screen and corrects (works whether the model adds or sets)
    const applyQty = async (vid, target, notify) => {
        const model = getModel();
        if (!model) {
            notify(T.noModel, "warning");
            return;
        }
        const rec = findRec(model, vid);
        const id = rec ? rec.virtual_id : vid;
        let done = false;
        for (let i = 0; i < 3; i++) {
            const current = readQty(findLine(vid));
            const delta = Math.round((target - current) * 1000) / 1000;
            if (!delta) {
                done = true;
                break;
            }
            try {
                await model.updateLineQty(id, delta);
            } catch (e) {
                notify(T.fail, "warning");
                return;
            }
            await sleep(350);
        }
        if (!done) {
            done = readQty(findLine(vid)) === target;
        }
        if (!done) {
            notify(T.fail, "warning");
            return;
        }
        clearTimeout(saveTimer);
        await persist(model, vid, notify);
    };

    const openEditor = (lineEl, notify) => {
        if (document.querySelector(".o_tqm_overlay")) {
            return;
        }
        const vid = lineEl.dataset.virtualId;
        const label = lineEl.querySelector(".o_product_label");
        const overlay = document.createElement("div");
        overlay.className = "o_tqm_overlay";
        const box = document.createElement("div");
        box.className = "o_tqm_box";
        const title = document.createElement("div");
        title.className = "o_tqm_title";
        title.textContent = ((label && label.textContent.trim()) || "") || T.title;
        const input = document.createElement("input");
        input.className = "o_tqm_input";
        input.type = "number";
        input.min = "0";
        input.step = "any";
        input.setAttribute("inputmode", "decimal");
        input.setAttribute("enterkeyhint", "done");
        input.setAttribute("autocomplete", "off");
        input.placeholder = T.title;
        input.value = String(readQty(lineEl));
        const actions = document.createElement("div");
        actions.className = "o_tqm_actions";
        const ok = document.createElement("button");
        ok.type = "button";
        ok.className = "o_tqm_btn o_tqm_ok";
        ok.textContent = T.ok;
        const cancel = document.createElement("button");
        cancel.type = "button";
        cancel.className = "o_tqm_btn o_tqm_cancel";
        cancel.textContent = T.cancel;
        actions.append(ok, cancel);
        box.append(title, input, actions);
        overlay.appendChild(box);
        document.body.appendChild(overlay);

        const close = () => overlay.remove();
        const submit = () => {
            const raw = toLatin(input.value || "").replace(",", ".");
            const target = parseFloat(raw);
            close();
            if (!isNaN(target) && target >= 0) {
                applyQty(vid, target, notify);
            }
        };
        ok.addEventListener("click", submit);
        cancel.addEventListener("click", close);
        overlay.addEventListener("click", (ev) => {
            if (ev.target === overlay) {
                close();
            }
        });
        input.addEventListener("keydown", (ev) => {
            if (ev.key === "Enter") {
                ev.preventDefault();
                submit();
            } else if (ev.key === "Escape") {
                close();
            }
        });
        setTimeout(() => {
            input.focus();
            input.select();
        }, 50);
    };

    const reveal = () => {
        const line = document.querySelector(LINE + ".o_selected");
        if (line) {
            line.scrollIntoView({ block: "nearest", inline: "nearest" });
        }
    };

    // +1 / -1 taps are also written to the server shortly after the last tap
    const scheduleSave = () => {
        clearTimeout(saveTimer);
        saveTimer = setTimeout(async () => {
            const model = getModel();
            if (model && typeof model.save === "function") {
                try {
                    await model.save();
                } catch (e) {
                    console.warn("toruq auto-save failed", e);
                }
            }
        }, 900);
    };

    registry.category("services").add("toruq_mobile_count", {
        dependencies: ["notification"],
        start(env, { notification }) {
            const notify = (msg, type = "info") => notification.add(msg, { type });
            patchActions();
            registry.category("actions").addEventListener("UPDATE", patchActions);
            document.addEventListener(
                "click",
                (ev) => {
                    const line = ev.target.closest && ev.target.closest(LINE);
                    if (!line) {
                        return;
                    }
                    const qty = ev.target.closest('[name="quantity"]');
                    if (qty && isSmall()) {
                        ev.preventDefault();
                        ev.stopPropagation();
                        openEditor(line, notify);
                        return;
                    }
                    if (ev.target.closest(".o_add_quantity, .o_remove_unit")) {
                        scheduleSave();
                    }
                    [60, 250, 600].forEach((ms) => setTimeout(reveal, ms));
                },
                true
            );
            return {};
        },
    });
}
