{
    "name": "Toruq Barcode - Count Only & Branch Transfers",
    "version": "18.0.3.0.0",
    "summary": "Count-only Barcode users, and branch-to-branch transfers with receiver confirmation",
    "category": "Inventory/Barcode",
    "author": "Toruq",
    "license": "LGPL-3",
    "depends": ["stock_barcode"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/res_users_views.xml",
        "views/stock_picking_views.xml",
        "views/toruq_transfer_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "toruq_barcode/static/src/js/count_only.js",
            "toruq_barcode/static/src/js/transfer.js",
            "toruq_barcode/static/src/css/count_only.css",
            "toruq_barcode/static/src/css/transfer.css",
        ],
    },
    "installable": True,
    "application": False,
}
