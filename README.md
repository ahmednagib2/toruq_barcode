# Toruq Odoo 18 modules

- `toruq_barcode` (v18.0.4.0.0): count features only (Count Only, Hide Scanner Graphic, Guided Count Mode, apply blocking, requester pop-up).
- `toruq_branch_transfer` (v18.0.1.0.0): branch-to-branch transfers with routes, e-signatures, receiver confirmation and dashboards. See its README.

Upgrade order: upgrade `toruq_barcode` first (it drops the transfer test data/fields of v3), then install `toruq_branch_transfer`.
Leftover files of the old transfer code inside `toruq_barcode/` (controllers/transfer.py, models/stock_picking.py, models/toruq_transfer.py, models/res_users.py, views/*, static transfer.*) are no longer loaded and can be deleted.
