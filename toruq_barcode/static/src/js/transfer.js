/** @odoo-module **/
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { session } from "@web/session";

const flags = session.toruq_barcode_flags || {};

const T = {
    send: "ابدأ بتحويل المخزون",
    receive: "استلام تحويل وارد",
    sendTitle: "بيانات التحويل",
    from: "من فرع:",
    toBranch: "فرع المخزون:",
    receiver: "المستلم:",
    courier: "اسم المندوب (الذي سيوصّل البضاعة)",
    start: "ابدأ مسح المنتجات",
    cancel: "إلغاء",
    noReceiver: "لا يوجد مستلم لهذا الفرع",
    inTitle: "تحويلات واردة بانتظار استلامك",
    noIncoming: "لا توجد تحويلات واردة.",
};

const toruqTransferService = {
    dependencies: ["action", "notification"],
    start(env, { action, notification }) {
        const isSender = !!flags.transfer_operator;
        const isReceiver = !!flags.transfer_receiver;
        if (!isSender && !isReceiver) {
            return {};
        }
        const root = document.documentElement;
        if (isSender) {
            root.classList.add("o_toruq_transfer_operator");
        }
        if (isReceiver) {
            root.classList.add("o_toruq_transfer_receiver");
        }

        const notify = (message) => notification.add(message, { type: "danger" });
        const errText = (e) => String((e && e.data && e.data.message) || (e && e.message) || e);
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
        const closeModal = () => {
            const modal = document.querySelector(".o_toruq_modal");
            if (modal) {
                modal.remove();
            }
        };
        const makeModal = (title) => {
            closeModal();
            const overlay = el("div", "o_toruq_modal");
            const box = el("div", "o_toruq_modal_box");
            box.appendChild(el("h4", "", title));
            overlay.appendChild(box);
            document.body.appendChild(overlay);
            return box;
        };
        const cancelButton = () => {
            const cancel = el("button", "o_toruq_cancel_btn btn w-100", T.cancel);
            cancel.type = "button";
            cancel.addEventListener("click", closeModal);
            return cancel;
        };

        const openSender = async () => {
            let data;
            try {
                data = await rpc("/toruq_barcode/transfer/destinations", {});
            } catch (e) {
                notify(errText(e));
                return;
            }
            if (data.error) {
                notify(data.error);
                return;
            }
            const box = makeModal(T.sendTitle);
            box.appendChild(el("p", "o_toruq_modal_from", `${T.from} ${data.source.name}`));

            box.appendChild(el("label", "o_toruq_label", T.toBranch));
            const branchSel = el("select", "o_toruq_input");
            data.destinations.forEach((d, i) => branchSel.appendChild(new Option(d.name, i)));
            box.appendChild(branchSel);

            box.appendChild(el("label", "o_toruq_label", T.receiver));
            const recvSel = el("select", "o_toruq_input");
            box.appendChild(recvSel);

            const summary = el("p", "o_toruq_summary");
            box.appendChild(summary);

            box.appendChild(el("label", "o_toruq_label", T.courier));
            const courier = el("input", "o_toruq_input");
            courier.type = "text";
            box.appendChild(courier);

            const startBtn = el("button", "o_toruq_start_btn btn w-100", T.start);
            startBtn.type = "button";

            const refresh = () => {
                recvSel.innerHTML = "";
                const dest = data.destinations[branchSel.value];
                if (!dest || !dest.receivers.length) {
                    recvSel.appendChild(new Option(T.noReceiver, ""));
                    startBtn.disabled = true;
                    summary.textContent = "";
                    return;
                }
                dest.receivers.forEach((r) => recvSel.appendChild(new Option(r.name, r.id)));
                startBtn.disabled = false;
                const upd = () => {
                    summary.textContent = `${T.receiver} ${recvSel.selectedOptions[0].text} | ${T.toBranch} ${dest.name}`;
                };
                recvSel.onchange = upd;
                upd();
            };
            branchSel.addEventListener("change", refresh);
            refresh();

            startBtn.addEventListener("click", async () => {
                const dest = data.destinations[branchSel.value];
                startBtn.disabled = true;
                try {
                    const res = await rpc("/toruq_barcode/transfer/create", {
                        destination_id: dest.id,
                        receiver_id: parseInt(recvSel.value, 10),
                        courier: courier.value,
                    });
                    if (res.error) {
                        notify(res.error);
                        startBtn.disabled = false;
                        return;
                    }
                    closeModal();
                    await action.doAction(res.action);
                } catch (e) {
                    notify(errText(e));
                    startBtn.disabled = false;
                }
            });
            box.appendChild(startBtn);
            box.appendChild(cancelButton());
        };

        const openReceiver = async () => {
            let data;
            try {
                data = await rpc("/toruq_barcode/transfer/incoming", {});
            } catch (e) {
                notify(errText(e));
                return;
            }
            if (data.error) {
                notify(data.error);
                return;
            }
            const box = makeModal(T.inTitle);
            if (!data.pickings.length) {
                box.appendChild(el("p", "", T.noIncoming));
            }
            for (const p of data.pickings) {
                const btn = el(
                    "button",
                    "o_toruq_dest_btn btn w-100",
                    `${p.name} | من ${p.from} | المرسل: ${p.sender} | المندوب: ${p.courier || "-"} | ${p.lines} منتج`
                );
                btn.type = "button";
                btn.addEventListener("click", async () => {
                    try {
                        const res = await rpc("/toruq_barcode/transfer/open", { picking_id: p.id });
                        if (res.error) {
                            notify(res.error);
                            return;
                        }
                        closeModal();
                        await action.doAction(res.action);
                    } catch (e) {
                        notify(errText(e));
                    }
                });
                box.appendChild(btn);
            }
            box.appendChild(cancelButton());
        };

        const addButton = (footer, cls, text, handler) => {
            if (footer.querySelector("." + cls)) {
                return;
            }
            const btn = el("button", `${cls} o_toruq_transfer_btn btn btn-block mb-3 p-3 w-100`, text);
            btn.type = "button";
            btn.addEventListener("click", handler);
            footer.insertBefore(btn, footer.firstChild);
        };
        const inject = () => {
            const footer = document.querySelector(".o_stock_barcode_main_menu footer");
            if (!footer) {
                return;
            }
            if (isReceiver) {
                addButton(footer, "o_toruq_receive_btn", T.receive, openReceiver);
            }
            if (isSender) {
                addButton(footer, "o_toruq_send_btn", T.send, openSender);
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
                inject();
            });
        };
        const begin = () => {
            new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true });
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
