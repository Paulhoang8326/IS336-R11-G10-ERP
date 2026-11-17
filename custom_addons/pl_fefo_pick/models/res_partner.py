from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    pl_min_shelf_life_pct = fields.Integer(
        "Min. Shelf Life at Delivery (%)",
        default=0,
        help="Lots delivered to this customer must still have at least this share of the product's "
             "expiration time left on the scheduled delivery date. 0 means no requirement. "
             "Delivery addresses use the value of their company.",
    )

    @api.constrains("pl_min_shelf_life_pct")
    def _check_pl_min_shelf_life_pct(self):
        for partner in self:
            if not 0 <= partner.pl_min_shelf_life_pct <= 100:
                raise ValidationError(_("Min. Shelf Life at Delivery must be between 0 and 100%."))

    @api.model
    def _commercial_fields(self):
        # Địa chỉ con luôn dùng mức của công ty mẹ, Odoo tự đồng bộ trường này xuống con.
        return super()._commercial_fields() + ["pl_min_shelf_life_pct"]
