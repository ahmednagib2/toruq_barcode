{
    "name": "Toruq Barcode - Count Only",
    "version": "18.0.1.2.0",
    "summary": "Restrict selected users in the Barcode app to inventory counting only",
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
