# toruq_barcode (Odoo 18)

Three groups (tick them in the user form, Technical section):

| Group | Effect |
|---|---|
| Barcode: Count Only (Toruq) | Scanning from the home screen is refused server-side; "Operations" hidden. Inventory Count still works. |
| Barcode: Hide Scanner Graphic (Toruq) | Hides the barcode picture and "Scan or tap" text. Can be used alone. |
| Barcode: Guided Count Mode (Toruq) | Implies both groups above. Replaces the scanner block with one large "Start counting now" button showing the number of products to count (the number is read from the original Inventory Count button). |

Optional: activate record rule `rule_quant_count_only_read` (inactive by default) to restrict reading stock.quant to quants assigned to the user.

## Install / upgrade (test DB first)
1. Put `toruq_barcode/` in the addons path of the project/branch Odoo builds from; rebuild/restart.
2. Update Apps List, install or upgrade the module.
3. Users > open user > tick the group(s). User must log out and in.
4. Inventory > Settings > Barcode: untick "Show Quantity to Count".

## Test matrix
- Count-only user: scan any code on home screen -> warning.
- Hide-scanner user: picture and "Scan or tap" gone; other buttons unchanged.
- Guided user: one big button, label "ابدأ عمل الجرد الآن", number equals the old Inventory Count badge; click opens Inventory Count; count it and save.
- Normal user: unchanged.

## Not verified
stock_barcode is Enterprise; its source was not available. `scan_from_main_menu` and the selectors `.o_stock_barcode_main_menu`, `.btn-info`, `.badge`, `ul` are based on Odoo conventions and on HTML supplied by the user; verify in DevTools.
