{
    "name": "Toruq Barcode - Count Only",
    "version": "18.0.4.0.0",
    "summary": "Count-only, hide-scanner and guided-count modes for the Barcode app",
    "category": "Inventory/Barcode",
    "author": "Toruq",
    "license": "LGPL-3",
    "depends": ["stock_barcode"],
    "data": ["security/security.xml"],
    "assets": {
        "web.assets_backend": [
            "toruq_barcode/static/src/js/count_only.js",
            "toruq_barcode/static/src/css/count_only.css",
        ],
    },
    "installable": True,
    "application": False,
}
