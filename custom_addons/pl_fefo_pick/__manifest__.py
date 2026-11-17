{
    "name": "Phan Lam FEFO Pick",
    "summary": "Giữ hàng cho đơn bán chỉ từ các lô còn đủ hạn dùng tối thiểu của khách, vẫn FEFO",
    "version": "18.0.1.0.0",
    "category": "Inventory/Inventory",
    "depends": ["sale_stock", "product_expiry"],
    "license": "LGPL-3",
    "data": [
        "views/res_partner_views.xml",
        "views/sale_order_views.xml",
        "views/stock_picking_views.xml",
        "views/stock_lot_views.xml",
    ],
    "installable": True,
    "application": False,
}
