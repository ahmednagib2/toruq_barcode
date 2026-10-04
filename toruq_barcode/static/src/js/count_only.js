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

    const isArabic = (root.lang || "").toLowerCase().startsWith("ar");
    const LABEL = isArabic ? "ابدأ عمل الجرد الآن" : "Start counting now";

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

    const sync = () => {
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
        let mine = menu.querySelector(".o_toruq_guided_btn");
        if (!mine) {
            mine = document.createElement("button");
            mine.type = "button";
            mine.className = "btn btn-info o_toruq_guided_btn w-100";
            const num = document.createElement("span");
            num.className = "o_toruq_guided_num badge rounded-pill bg-white text-info";
            const label = document.createElement("span");
            label.className = "o_toruq_guided_label";
            label.textContent = LABEL;
            mine.appendChild(num);
            mine.appendChild(label);
            mine.addEventListener("click", () => {
                const current = findOriginal(menu);
                if (current) {
                    current.click();
                }
            });
            const scan = menu.querySelector(".o_barcode_tap_to_scan");
            const anchor = (scan && scan.parentElement) || orig;
            anchor.insertAdjacentElement("beforebegin", mine);
        }
        const numEl = mine.querySelector(".o_toruq_guided_num");
        const count = extractCount(orig);
        if (numEl.textContent !== count) {
            numEl.textContent = count;
        }
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
