from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    pl_trip_id = fields.Many2one("pl.delivery.trip", "Delivery Trip", readonly=True, copy=False, index=True)
    pl_stop_sequence = fields.Integer("Stop Sequence", readonly=True, copy=False)

    def _pl_weight_kg(self):
        """Tải của từng phiếu (kg): tổng số lượng × cân nặng sản phẩm của các move.

        move.product_qty là số lượng đã quy về đơn vị tính của sản phẩm (dòng bán theo thùng vẫn lưu số
        đơn vị lẻ), còn product.weight là cân nặng một đơn vị tính đó. Cân nặng đổi về kg nếu database
        dùng pound.
        """
        uom_can = self.env["product.template"]._get_weight_uom_id_from_ir_config_parameter()
        kg = self.env.ref("uom.product_uom_kgm")
        ket_qua = {}
        for picking in self:
            tong = sum(m.product_qty * m.product_id.weight for m in picking.move_ids if m.state != "cancel")
            ket_qua[picking.id] = uom_can._compute_quantity(tong, kg, round=False) if uom_can != kg else tong
        return ket_qua
