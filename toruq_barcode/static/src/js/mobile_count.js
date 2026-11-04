/** @odoo-module **/
import { session } from "@web/session";

const flags = session.toruq_barcode_flags || {};

if (flags.count_only || session.toruq_barcode_count_only) {
    const LINE = ".o_barcode_client_action .o_barcode_line";
    const reveal = () => {
        const line = document.querySelector(LINE + ".o_selected");
        if (line) {
            line.scrollIntoView({ block: "nearest", inline: "nearest" });
        }
    };
    // keep the selected card (and its +1 / -1 buttons) in view after it expands
    document.addEventListener(
        "click",
        (ev) => {
            const line = ev.target.closest && ev.target.closest(LINE);
            if (!line) {
                return;
            }
            [60, 250, 600].forEach((ms) => setTimeout(reveal, ms));
        },
        true
    );
}
