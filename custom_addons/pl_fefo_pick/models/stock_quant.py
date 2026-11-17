from odoo import models
from odoo.osv import expression


class StockQuant(models.Model):
    _inherit = "stock.quant"

    def _get_gather_domain(self, product_id, location_id, lot_id=None, package_id=None, owner_id=None,
                           strict=False):
        """Cùng chỗ product_expiry loại lô hết hạn (context `with_expiration`), thêm điều kiện hạn tối thiểu.

        stock.move đặt `pl_min_expiration_date` vào context khi move thuộc đơn bán có yêu cầu hạn dùng.
        Thứ tự FEFO (removal_date) giữ nguyên, chỉ bớt các lô không đạt khỏi tập quant.
        """
        domain = super()._get_gather_domain(product_id, location_id, lot_id, package_id, owner_id, strict)
        min_date = self.env.context.get("pl_min_expiration_date")
        if min_date:
            domain = expression.AND([
                ["|", ("expiration_date", ">=", min_date), ("expiration_date", "=", False)], domain])
        return domain
