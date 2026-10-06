# toruq_barcode (Odoo 18)

Every feature has its own switch in the user form (Technical section) and is independent.

## Count features
| Group | Effect |
|---|---|
| Barcode: Count Only (Toruq) | Home-screen scan refused server-side; Operations hidden; cannot apply inventory adjustments; requester gets a pop-up when the user presses Apply. |
| Barcode: Hide Scanner Graphic (Toruq) | Hides the barcode picture. |
| Barcode: Guided Count Mode (Toruq) | Implies both; table + "ابدأ الجرد الآن". |

## Transfers with approval (v18.0.2.0.0)
| Item | Effect |
|---|---|
| User field "مخزن الفرع" | Source warehouse of the user (Odoo has no such link). Set it in the user form (bottom of the form). |
| Barcode: Transfer Operator (Toruq) | Barcode home shows "ابدأ بتحويل المخزون" (Operations hidden). Choose destination warehouse -> an internal transfer (source stock -> destination stock) is created and opened in Barcode. Pressing Validate sends it for approval instead of validating. |
| Barcode: Transfer Approver (Toruq) | Give it to ONE person (the accountant). Gets a pop-up + inbox message, sees Inventory > "طلبات التحويل", opens the transfer, presses "موافق وتنفيذ التحويل" (validates it with the standard Odoo mechanism) or "رفض". |

Operators cannot set the approval fields (guarded in `write`), and cannot validate internal transfers. Inventory Administrators can also approve.

## Install / upgrade (test DB first)
1. Replace `toruq_barcode/`; rebuild/restart, Upgrade the module. Users log out and in.
2. Set "مخزن الفرع" for each operator; tick the groups.

## Not verified (Enterprise source not available)
- Opening the new transfer in Barcode (`action_open_picking_client_action`, fallback client action tag).
- Whether Barcode saves scanned quantities before Validate, and whether the Validate button class is `.o_validate_page`.
- Approval of a draft transfer created from scratch in Barcode (confirm + validate with skip flags).
Test: operator -> create transfer -> scan -> Validate -> approver gets pop-up -> approve -> stock moves (Moves History).
