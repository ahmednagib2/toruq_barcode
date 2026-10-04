# toruq_barcode (Odoo 18)

Adds group **Barcode: Count Only (Toruq)**. Members:
- Cannot scan product/location/operation codes from the Barcode home screen (server-side block on `scan_from_main_menu`).
- "Operations" button hidden (CSS, convenience only).
- Can still open **Inventory Count** and count normally.

Optional: activate record rule `rule_quant_count_only_read` (inactive by default) to restrict reading stock.quant to quants assigned to the user.

## Install (test DB first)
1. Copy `toruq_barcode/` into addons path, update apps list, install.
2. Settings > Users > open user > tick the group in Technical section.
3. Inventory > Settings > Barcode: untick "Show Quantity to Count".

## Test matrix
- Count-only user: scan any code on home screen -> warning, no quantities shown.
- Count-only user: Inventory Count -> scan location/product, enter counted qty, save.
- Normal user: behaviour unchanged.
- Direct URL /odoo/barcode/stock.quant as count-only user (enable the rule to restrict).

## Not verified
stock_barcode is Enterprise; source was not available to inspect. Controller method name and CSS selector are based on Odoo 17/18 conventions and must be tested.
