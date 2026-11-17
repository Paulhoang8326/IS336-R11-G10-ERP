{
    "name": "Phan Lam Delivery Route",
    "summary": "Lập kế hoạch giao hàng trong ngày: xếp phiếu xuất lên xe, sắp thứ tự điểm giao, link Google Maps",
    "version": "18.0.1.0.0",
    "category": "Inventory/Delivery",
    "depends": ["stock", "stock_picking_batch"],
    "license": "LGPL-3",
    "data": [
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "views/pl_vehicle_views.xml",
        "views/pl_delivery_plan_views.xml",
        "views/stock_picking_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": False,
}
