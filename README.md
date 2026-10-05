# toruq_barcode (Odoo 18)

Three groups (tick them in the user form, Technical section):

| Group | Effect |
|---|---|
| Barcode: Count Only (Toruq) | Scanning from the home screen is refused server-side; "Operations" hidden; **cannot apply inventory adjustments**. |
| Barcode: Hide Scanner Graphic (Toruq) | Hides the barcode picture and "Scan or tap" text. Can be used alone. |
| Barcode: Guided Count Mode (Toruq) | Implies both groups above. Table (scanned | required) + one large Arabic button "ابدأ الجرد الآن". Brand colour #ff3d00. |

## Approval flow (v18.0.1.2.0)
- Odoo does not store who requested a count. The module adds `stock.quant.toruq_requester_id`: whenever a user who is NOT Count Only sets the counter (`user_id`) on a line (Request a Count wizard or editing the User column), that user is recorded as the requester. Lines requested BEFORE this version have no requester.
- A Count Only user (not Inventory Administrator) who presses Apply gets an error; nothing is applied.
- The requester receives a sticky pop-up (bus `simple_notification`): "<name> أرسل جرد N منتج ويحتاج موافقتك", plus an inbox message. If no requester is recorded, all Inventory Administrators are notified instead.
- The pop-up only reaches users who are online; the inbox message is the persistent copy (depends on the user's notification preference: "Handle in Odoo").
- The requester reviews Inventory > Operations > Physical Inventory (on hand, counted, difference) and presses Apply.

## Install / upgrade (test DB first)
1. Replace `toruq_barcode/`; rebuild/restart, then Upgrade the module (adds a new column).
2. Users log out and in.
3. IMPORTANT: create the count request again (Request a Count) after the upgrade so the requester is recorded.

## Test matrix
- Manager A requests a count for the cashier; cashier counts and presses Apply -> error for cashier, pop-up for A (A must be online).
- Line with no requester -> all Inventory Administrators are notified.
- Manager presses Apply -> works, move appears in Moves History.
- Normal user: unchanged.

## Not verified
stock_barcode is Enterprise; source not available. Whether the Barcode Apply button reaches `action_apply_inventory`/`_apply_inventory`, and that setting the counter always goes through `stock.quant.write`, must be tested.
