{
    "name": "Toruq Barcode - Inventory Count",
    "version": "18.0.5.0.0",
    "summary": "Count-only, hide-scanner and guided-count modes, count confirmation, audit log and manager dashboard for inventory",
    "category": "Inventory/Barcode",
    "author": "Toruq",
    "license": "LGPL-3",
    "depends": ["stock_barcode", "mail"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/toruq_count_log_views.xml",
        "views/toruq_count_dashboard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "toruq_barcode/static/src/js/count_only.js",
            "toruq_barcode/static/src/css/count_only.css",
            "toruq_barcode/static/src/js/count_tools.js",
            "toruq_barcode/static/src/css/count_tools.css",
            "toruq_barcode/static/src/dashboard/dashboard.js",
            "toruq_barcode/static/src/dashboard/dashboard.xml",
            "toruq_barcode/static/src/dashboard/dashboard.css",
        ],
        "stock_barcode.assets_stock_barcode": [
            "toruq_barcode/static/src/js/count_tools.js",
            "toruq_barcode/static/src/css/count_tools.css",
        ],
    },
    "installable": True,
    "application": False,
}
