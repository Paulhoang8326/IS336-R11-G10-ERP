from odoo import models

from ..services import shelf_life


class StockMove(models.Model):
    _inherit = "stock.move"

    def _pl_shelf_life_customer(self):
        """Khách của đơn bán: qua dòng bán, hoặc qua procurement group (bước Pick, Pack của kho nhiều bước)."""
        self.ensure_one()
        order = self.sale_line_id.order_id or self.group_id.sale_id
        return order.partner_id.commercial_partner_id

    def _pl_min_expiration_date(self):
        """Hạn dùng sớm nhất giao được cho khách, tính từ ngày giao dự kiến của move. False khi không áp."""
        self.ensure_one()
        product = self.product_id
        if not product.use_expiration_date or not self.date:
            return False
        pct = self._pl_shelf_life_customer().pl_min_shelf_life_pct
        return shelf_life.min_expiration_date(self.date, pct, product.expiration_time) or False

    def _pl_with_min_expiration(self):
        min_date = self._pl_min_expiration_date()
        return self.with_context(pl_min_expiration_date=min_date) if min_date else self

    def _update_reserved_quantity(self, need, location_id, lot_id=None, package_id=None, owner_id=None,
                                  strict=True):
        return super(StockMove, self._pl_with_min_expiration())._update_reserved_quantity(
            need, location_id, lot_id, package_id, owner_id, strict)

    def _get_available_quantity(self, location_id, lot_id=None, package_id=None, owner_id=None, strict=False,
                                allow_negative=False):
        return super(StockMove, self._pl_with_min_expiration())._get_available_quantity(
            location_id, lot_id, package_id, owner_id, strict, allow_negative)
