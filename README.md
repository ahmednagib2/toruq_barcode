# toruq_barcode (Odoo 18)

Three groups (tick them in the user form, Technical section):

| Group | Effect |
|---|---|
| Barcode: Count Only (Toruq) | Scanning from the home screen is refused server-side; "Operations" hidden; **cannot apply inventory adjustments** (see below). |
| Barcode: Hide Scanner Graphic (Toruq) | Hides the barcode picture and "Scan or tap" text. Can be used alone. |
| Barcode: Guided Count Mode (Toruq) | Implies both groups above. Home screen shows a table (scanned | required) and one large Arabic button "ابدأ الجرد الآن". Brand colour #ff3d00. |

## Approval flow (v18.0.1.1.0)
- A user in Count Only who is NOT Inventory Administrator (`stock.group_stock_manager`) cannot apply an inventory adjustment: `stock.quant.action_apply_inventory` and `_apply_inventory` raise a UserError.
- When such a user presses Apply, every inventory manager gets an inbox notification ("جرد بانتظار الاعتماد") with the user name and number of lines. It is sent from a separate cursor so it is kept despite the rollback.
- The manager reviews Inventory > Operations > Physical Inventory (on hand, counted, difference) and presses Apply.

## Install / upgrade (test DB first)
1. Replace `toruq_barcode/` in the addons path; rebuild/restart, then Upgrade the module.
2. Users must log out and in.
3. Inventory > Settings > Barcode: untick "Show Quantity to Count".

## Test matrix
- Cashier (Count Only): count a product, press Apply -> error message, on-hand unchanged, managers get a notification.
- Check Physical Inventory as manager: is the cashier's counted quantity still on the line? (depends on when the Barcode app saves counts)
- Manager: Apply works, a move appears in Inventory > Reporting > Moves History.
- Normal user: unchanged.

## Not verified
stock_barcode is Enterprise; source not available. Whether the Barcode Apply button reaches `action_apply_inventory`/`_apply_inventory`, and whether counts are saved before Apply, must be tested.
