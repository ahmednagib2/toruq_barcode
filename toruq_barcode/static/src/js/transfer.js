/** @odoo-module **/
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { session } from "@web/session";

const flags = session.toruq_barcode_flags || {};

const T = {
    start: "ابدأ بتحويل المخزون",
    title: "اختر الفرع المستلم",
    from: "من:",
    cancel: "إلغاء",
    none: "لا توجد فروع أخرى.",
};

const toruqTransferService = {
    dependencies: ["action", "notification"],
    start(env, { action, notification }) {
        if (!flags.transfer_operator) {
            return {};
        }
        document.documentElement.classList.add("o_toruq_transfer_operator");

        const notify = (message) => notification.add(message, { type: "danger" });
        const closeModal = () => {
            const modal = document.querySelector(".o_toruq_modal");
            if (modal) {
                modal.remove();
            }
        };

        const openModal = async () => {
            closeModal();
            let data;
            try {
                data = await rpc("/toruq_barcode/transfer/destinations", {});
            } catch (e) {
                notify(String((e && e.data && e.data.message) || e.message || e));
                return;
            }
            if (data.error) {
                notify(data.error);
                return;
            }
            const overlay = document.createElement("div");
            overlay.className = "o_toruq_modal";
            const box = document.createElement("div");
            box.className = "o_toruq_modal_box";
            const title = document.createElement("h4");
            title.textContent = T.title;
            const from = document.createElement("p");
            from.className = "o_toruq_modal_from";
            from.textContent = `${T.from} ${data.source.name}`;
            box.appendChild(title);
            box.appendChild(from);
            if (!data.destinations.length) {
                const empty = document.createElement("p");
                empty.textContent = T.none;
                box.appendChild(empty);
            }
            for (const dest of data.destinations) {
                const btn = document.createElement("button");
                btn.type = "button";
                btn.className = "o_toruq_dest_btn btn w-100";
                btn.textContent = dest.name;
                btn.addEventListener("click", async () => {
                    box.querySelectorAll("button").forEach((b) => (b.disabled = true));
                    try {
                        const res = await rpc("/toruq_barcode/transfer/create", {
                            destination_id: dest.id,
                        });
                        if (res.error) {
                            notify(res.error);
                            box.querySelectorAll("button").forEach((b) => (b.disabled = false));
                            return;
                        }
                        closeModal();
                        await action.doAction(res.action);
                    } catch (e) {
                        notify(String((e && e.data && e.data.message) || e.message || e));
                        box.querySelectorAll("button").forEach((b) => (b.disabled = false));
                    }
                });
                box.appendChild(btn);
            }
            const cancel = document.createElement("button");
            cancel.type = "button";
            cancel.className = "o_toruq_cancel_btn btn w-100";
            cancel.textContent = T.cancel;
            cancel.addEventListener("click", closeModal);
            box.appendChild(cancel);
            overlay.appendChild(box);
            document.body.appendChild(overlay);
        };

        const inject = () => {
            const footer = document.querySelector(".o_stock_barcode_main_menu footer");
            if (!footer || footer.querySelector(".o_toruq_transfer_btn")) {
                return;
            }
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "o_toruq_transfer_btn btn btn-block mb-3 p-3 w-100";
            btn.textContent = T.start;
            btn.addEventListener("click", openModal);
            footer.insertBefore(btn, footer.firstChild);
        };

        let scheduled = false;
        const schedule = () => {
            if (scheduled) {
                return;
            }
            scheduled = true;
            requestAnimationFrame(() => {
                scheduled = false;
                inject();
            });
        };
        const begin = () => {
            new MutationObserver(schedule).observe(document.body, {
                childList: true,
                subtree: true,
            });
            schedule();
        };
        if (document.body) {
            begin();
        } else {
            document.addEventListener("DOMContentLoaded", begin);
        }
        return {};
    },
};

registry.category("services").add("toruq_barcode_transfer", toruqTransferService);
