# Toruq Odoo 18 modules

- `toruq_barcode` (v18.0.5.0.0): inventory / count only. Count Only, Hide Scanner Graphic and Guided Count groups; apply blocking with approval pop-up; confirm + save dialog on the count screen with product counter; audit log (`toruq.count.log`); manager-only dashboard (Inventory > Reporting > لوحة الجرد) with low stock vs reorder rules, negative stock, products due for count, pending approvals (approve / reject) and recent events.
- `toruq_branch_transfer`: branch-to-branch transfers with routes, e-signatures, receiver confirmation and dashboards. See its README.

Upgrade `toruq_barcode` after pulling this version (new model, access rights and menus). Leftover files of the old transfer code inside `toruq_barcode/` (controllers/transfer.py, models/stock_picking.py, models/toruq_transfer.py, models/toruq_notify.py, models/res_users.py, views/stock_picking_views.xml, views/toruq_transfer_views.xml, views/res_users_views.xml, static/src/js/transfer.js, static/src/css/transfer.css) are not loaded and can be deleted.
