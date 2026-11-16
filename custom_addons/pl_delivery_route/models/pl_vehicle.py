from odoo import api, fields, models


class PlVehicle(models.Model):
    _name = "pl.vehicle"
    _description = "Xe giao hàng"
    _order = "code"

    code = fields.Char("Mã xe", required=True)
    name = fields.Char("Loại xe", required=True)
    capacity_kg = fields.Float("Tải trọng (kg)", required=True, digits=(16, 2))
    warehouse_id = fields.Many2one("stock.warehouse", "Kho xuất phát", required=True, check_company=True,
                                   default=lambda self: self.env["stock.warehouse"].search(
                                       [("company_id", "=", self.env.company.id)], limit=1))
    company_id = fields.Many2one(related="warehouse_id.company_id", store=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("code_uniq", "unique(code)", "Mã xe đã tồn tại."),
        ("capacity_positive", "CHECK(capacity_kg > 0)", "Tải trọng phải lớn hơn 0."),
    ]

    @api.depends("code", "name")
    def _compute_display_name(self):
        for xe in self:
            xe.display_name = f"{xe.code} - {xe.name}" if xe.name else xe.code
