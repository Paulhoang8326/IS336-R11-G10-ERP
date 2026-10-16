{
    "name": "Phan Lam Barcode Camera",
    "summary": "Quét mã vạch bằng camera máy tính trong app Barcodes (stock_barcodes)",
    "version": "18.0.1.0.0",
    "depends": ["stock_barcodes"],
    "license": "AGPL-3",
    "data": [
        "views/stock_barcodes_read_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "pl_barcode_camera/static/src/**/*",
        ],
    },
}
