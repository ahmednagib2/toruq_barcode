{
    "name": "Toruq Barcode - Count Only & Transfers",
    "version": "18.0.2.0.0",
    "summary": "Count-only Barcode users, and inter-warehouse transfers with accountant approval",
    "category": "Inventory/Barcode",
    "author": "Toruq",
    "license": "LGPL-3",
    "depends": ["stock_barcode"],
    "data": [
        "security/security.xml",
        "views/res_users_views.xml",
        "views/stock_picking_views.xml",
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
