/** @odoo-module **/
import { session } from "@web/session";

if (session.toruq_barcode_count_only) {
    document.documentElement.classList.add("o_toruq_count_only");
}
