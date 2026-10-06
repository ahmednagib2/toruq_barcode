{
    "name": "Toruq Branch Transfers",
    "version": "18.0.1.0.0",
    "summary": "Branch-to-branch stock transfers from Barcode with routes, e-signatures, receiver confirmation and dashboards",
    "category": "Inventory",
    "author": "Toruq",
    "license": "LGPL-3",
    "depends": ["stock_barcode"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/brt_route_views.xml",
        "views/stock_picking_views.xml",
        "views/brt_wizard_views.xml",
        "views/brt_dashboard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "toruq_branch_transfer/static/src/js/transfer.js",
            "toruq_branch_transfer/static/src/css/transfer.css",
        ],
    },
    "installable": True,
    "application": False,
}
