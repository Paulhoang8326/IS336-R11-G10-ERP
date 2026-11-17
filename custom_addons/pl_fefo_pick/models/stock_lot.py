from odoo import api, fields, models

from ..services import shelf_life


class StockLot(models.Model):
    _inherit = "stock.lot"

    pl_remaining_shelf_life_pct = fields.Float(
        "Remaining Shelf Life (%)",
        compute="_compute_pl_remaining_shelf_life_pct",
        digits=(16, 1),
        help="Share of the product's expiration time left today, negative once expired. "
             "Only shown when the lot has an expiration date.",
    )

    @api.depends("expiration_date", "product_id.expiration_time")
    @api.depends_context("uid")
    def _compute_pl_remaining_shelf_life_pct(self):
        now = fields.Datetime.now()
        for lot in self:
            pct = shelf_life.remaining_pct(lot.expiration_date, now, lot.product_id.expiration_time)
            lot.pl_remaining_shelf_life_pct = pct if pct is not None else False
