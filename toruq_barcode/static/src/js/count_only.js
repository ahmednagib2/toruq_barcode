/** @odoo-module **/
import { session } from "@web/session";

const root = document.documentElement;
const flags = session.toruq_barcode_flags || {};

if (flags.count_only || session.toruq_barcode_count_only) {
    root.classList.add("o_toruq_count_only");
}
if (flags.hide_scanner) {
    root.classList.add("o_toruq_hide_scanner");
}
if (flags.guided) {
    root.classList.add("o_toruq_guided_count");

    const L = {
        start: "ابدأ الجرد الآن",
        scanned: "المنتجات الممسوحة",
        required: "المنتجات المطلوبة",
    };
    const STORE_KEY = `toruq_barcode_scanned:${location.host}:${flags.uid || 0}`;

    const readStored = () => {
        try {
            return localStorage.getItem(STORE_KEY) || "0";
        } catch (e) {
            return "0";
        }
    };
    const writeStored = (value) => {
        try {
            if (localStorage.getItem(STORE_KEY) !== value) {
                localStorage.setItem(STORE_KEY, value);
            }
        } catch (e) {
            /* storage unavailable */
        }
    };

    // On the count screen, read the number inside the "Apply (N)" button.
    const trackApply = () => {
        const apply = document.querySelector("button.o_apply_page");
        if (!apply) {
            return;
        }
        const muted = apply.querySelector(".text-muted");
        const match = ((muted && muted.textContent) || "").match(/\d+/);
        writeStored(match ? match[0] : "0");
    };

    const el = (tag, cls, text) => {
        const node = document.createElement(tag);
        if (cls) {
            node.className = cls;
        }
        if (text !== undefined) {
            node.textContent = text;
        }
        return node;
    };

    const findOriginal = (menu) => {
        const buttons = [...menu.querySelectorAll("button")].filter(
            (b) => !b.classList.contains("o_toruq_guided_btn")
        );
        return (
            buttons.find((b) => b.querySelector(".badge")) ||
            buttons.find((b) => b.classList.contains("btn-info"))
        );
    };

    const extractCount = (btn) => {
        const badge = btn.querySelector(".badge");
        const match = ((badge ? badge.textContent : btn.textContent) || "").match(/\d+/);
        return match ? match[0] : "0";
    };

    const setText = (node, value) => {
        if (node.textContent !== value) {
            node.textContent = value;
        }
    };

    const sync = () => {
        trackApply();
        const menu = document.querySelector(".o_stock_barcode_main_menu");
        if (!menu) {
            return;
        }
        const orig = findOriginal(menu);
        if (!orig) {
            return;
        }
        if (orig.style.display !== "none") {
            orig.style.setProperty("display", "none", "important");
        }
        let box = menu.querySelector(".o_toruq_guided_box");
        if (!box) {
            box = el("div", "o_toruq_guided_box");
            const table = el("table", "o_toruq_guided_table");
            const head = el("tr");
            head.appendChild(el("th", "", L.scanned));
            head.appendChild(el("th", "", L.required));
            const row = el("tr");
            row.appendChild(el("td", "o_toruq_scanned", "0"));
            row.appendChild(el("td", "o_toruq_required", "0"));
            table.appendChild(head);
            table.appendChild(row);
            const button = el("button", "btn o_toruq_guided_btn", L.start);
            button.type = "button";
            button.addEventListener("click", () => {
                const current = findOriginal(menu);
                if (current) {
                    current.click();
                }
            });
            box.appendChild(table);
            box.appendChild(button);
            const scan = menu.querySelector(".o_barcode_tap_to_scan");
            const anchor = (scan && scan.parentElement) || orig;
            anchor.insertAdjacentElement("beforebegin", box);
        }
        setText(box.querySelector(".o_toruq_scanned"), readStored());
        setText(box.querySelector(".o_toruq_required"), extractCount(orig));
    };

    let scheduled = false;
    const schedule = () => {
        if (scheduled) {
            return;
        }
        scheduled = true;
        requestAnimationFrame(() => {
            scheduled = false;
            sync();
        });
    };
    const start = () => {
        new MutationObserver(schedule).observe(document.body, {
            childList: true,
            subtree: true,
            characterData: true,
        });
        schedule();
    };
    if (document.body) {
        start();
    } else {
        document.addEventListener("DOMContentLoaded", start);
    }
}
