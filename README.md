# toruq_barcode (Odoo 18)

Three groups (tick them in the user form, Technical section):

| Group | Effect |
|---|---|
| Barcode: Count Only (Toruq) | Scanning from the home screen is refused server-side; "Operations" hidden. Inventory Count still works. |
| Barcode: Hide Scanner Graphic (Toruq) | Hides the barcode picture and "Scan or tap" text. Can be used alone. |
| Barcode: Guided Count Mode (Toruq) | Implies both groups above. Home screen shows a small table (scanned products | required products) and one large Arabic button "ابدأ الجرد الآن". Brand colour #ff3d00. |

Guided mode details:
- Required = number on the original Inventory Count button (hidden, clicked programmatically).
- Scanned = number inside the "Apply (N)" button (`button.o_apply_page`) on the count screen. That button exists only there, so the last seen value is stored in browser localStorage (per host and user) and shown on the home screen. It can be stale after applying/clearing on another device.

Optional: activate record rule `rule_quant_count_only_read` (inactive by default).

## Install / upgrade (test DB first)
1. Replace `toruq_barcode/` in the addons path; rebuild/restart.
2. Upgrade the module. Users must log out and in.
3. Inventory > Settings > Barcode: untick "Show Quantity to Count".

## Not verified
stock_barcode is Enterprise; source not available. Selectors are based on HTML supplied by the user.
