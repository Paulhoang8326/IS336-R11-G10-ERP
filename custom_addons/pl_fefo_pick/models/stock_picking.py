from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_date

from ..services import shelf_life


class StockPicking(models.Model):
    _inherit = "stock.picking"

    pl_min_shelf_life_pct = fields.Integer(
        "Min. Shelf Life at Delivery (%)",
        related="sale_id.partner_id.commercial_partner_id.pl_min_shelf_life_pct",
    )

    def button_validate(self):
        # App Barcodes (OCA stock_barcodes) cũng validate qua button_validate.
        self._pl_check_min_shelf_life()
        return super().button_validate()

    def _pl_check_min_shelf_life(self):
        """Chặn validate khi một dòng lấy hàng của đơn bán có lô không đạt hạn dùng tối thiểu của khách.

        Lô được giữ tự động đã đạt; dòng này bắt lô chọn tay hoặc quét barcode. Chỉ xét hàng rời vị trí
        nội bộ (Pick, Pack, Out), không xét hàng khách trả về.
        """
        lines = []
        for ml in self.move_ids.move_line_ids:
            move = ml.move_id
            if (move.state in ("done", "cancel") or not ml.lot_id.expiration_date or ml.quantity <= 0
                    or ml.location_id.usage != "internal"):
                continue
            min_date = move._pl_min_expiration_date()
            if not min_date or ml.lot_id.expiration_date >= min_date:
                continue
            remaining = shelf_life.remaining_pct(ml.lot_id.expiration_date, move.date, ml.product_id.expiration_time)
            lines.append(_(
                "%(product)s, lot %(lot)s: %(remaining)s%% shelf life left on %(date)s, customer requires %(required)s%%",
                product=ml.product_id.display_name,
                lot=ml.lot_id.name,
                remaining=f"{remaining:.1f}",
                date=format_date(self.env, fields.Datetime.context_timestamp(self, move.date)),
                required=move._pl_shelf_life_customer().pl_min_shelf_life_pct,
            ))
        if lines:
            raise UserError(_(
                "These lots do not meet the customer's minimum shelf life at delivery. "
                "Pick other lots or unreserve and check availability again:\n%s",
                "\n".join(f"- {line}" for line in lines),
            ))
