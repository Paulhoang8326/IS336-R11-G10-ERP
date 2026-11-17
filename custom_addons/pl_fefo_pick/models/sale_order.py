from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    pl_min_shelf_life_pct = fields.Integer(
        "Min. Shelf Life at Delivery (%)",
        related="partner_id.commercial_partner_id.pl_min_shelf_life_pct",
    )
