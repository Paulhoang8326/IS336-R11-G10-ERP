from datetime import datetime, time

import pytz
from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..services import maps, vrp

MUI_GIO_MAC_DINH = "Asia/Ho_Chi_Minh"


class PlDeliveryPlan(models.Model):
    _name = "pl.delivery.plan"
    _description = "Kế hoạch giao hàng"
    _order = "date desc, id desc"

    name = fields.Char("Số kế hoạch", required=True, readonly=True, copy=False, default=lambda self: _("Mới"))
    date = fields.Date("Ngày giao", required=True, default=fields.Date.context_today)
    warehouse_id = fields.Many2one("stock.warehouse", "Kho", required=True, check_company=True,
                                   default=lambda self: self.env["stock.warehouse"].search(
                                       [("company_id", "=", self.env.company.id)], limit=1))
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    state = fields.Selection([("draft", "Nháp"), ("routed", "Đã lập tuyến"), ("confirmed", "Đã xác nhận")],
                             "Trạng thái", default="draft", required=True, readonly=True, copy=False)
    road_factor = fields.Float("Hệ số đường đi", default=vrp.HE_SO_DUONG_MAC_DINH, digits=(4, 2),
                               help="Quãng đường = khoảng cách chim bay (haversine) × hệ số này.")
    trip_ids = fields.One2many("pl.delivery.trip", "plan_id", "Chuyến", readonly=True, copy=False)
    unassigned_ids = fields.One2many("pl.delivery.unassigned", "plan_id", "Phiếu chưa xếp", readonly=True,
                                     copy=False)
    total_km = fields.Float("Tổng km", compute="_compute_totals", store=True, digits=(16, 1))
    total_weight = fields.Float("Tổng tải đã xếp (kg)", compute="_compute_totals", store=True, digits=(16, 1))
    trip_count = fields.Integer("Số chuyến", compute="_compute_totals", store=True)
    unassigned_count = fields.Integer("Số phiếu chưa xếp", compute="_compute_unassigned_count", store=True)

    _sql_constraints = [
        ("road_factor_positive", "CHECK(road_factor >= 1)", "Hệ số đường đi phải từ 1 trở lên."),
    ]

    @api.depends("trip_ids.total_km", "trip_ids.weight")
    def _compute_totals(self):
        for plan in self:
            plan.total_km = sum(plan.trip_ids.mapped("total_km"))
            plan.total_weight = sum(plan.trip_ids.mapped("weight"))
            plan.trip_count = len(plan.trip_ids)

    @api.depends("unassigned_ids")
    def _compute_unassigned_count(self):
        for plan in self:
            plan.unassigned_count = len(plan.unassigned_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Mới")) == _("Mới"):
                vals["name"] = self.env["ir.sequence"].next_by_code("pl.delivery.plan") or _("Mới")
        return super().create(vals_list)

    def unlink(self):
        if any(p.state == "confirmed" for p in self):
            raise UserError(_("Không xóa được kế hoạch đã xác nhận."))
        return super().unlink()

    # ------------------------------------------------------------------ chọn phiếu

    def _cuoi_ngay_utc(self):
        """23:59:59 của ngày giao theo múi giờ người dùng (mặc định giờ Việt Nam), đổi sang UTC như Odoo lưu."""
        tz = pytz.timezone(self.env.user.tz or MUI_GIO_MAC_DINH)
        cuoi = tz.localize(datetime.combine(self.date, time.max))
        return cuoi.astimezone(pytz.utc).replace(tzinfo=None)

    def _get_candidate_pickings(self):
        """Phiếu xuất của kho, đang Ready, ngày dự kiến không sau ngày giao, chưa thuộc kế hoạch đã xác nhận.

        Chuyến chỉ được ghi vào phiếu khi xác nhận kế hoạch, nên "chưa thuộc kế hoạch đã xác nhận" là
        pl_trip_id trống.
        """
        self.ensure_one()
        return self.env["stock.picking"].search([
            ("picking_type_id.code", "=", "outgoing"),
            ("picking_type_id.warehouse_id", "=", self.warehouse_id.id),
            ("state", "=", "assigned"),
            ("scheduled_date", "<=", self._cuoi_ngay_utc()),
            ("pl_trip_id", "=", False),
        ], order="id")

    @staticmethod
    def _toa_do(partner):
        """Tọa độ của địa chỉ giao; địa chỉ con không có thì lấy của công ty mẹ. (0, 0) coi như chưa có."""
        for p in (partner, partner.commercial_partner_id):
            if p and (p.partner_latitude or p.partner_longitude):
                return p.partner_latitude, p.partner_longitude
        return None, None

    # ------------------------------------------------------------------ nút

    def action_compute_routes(self):
        """Nút Lập tuyến: xóa kết quả cũ, chọn phiếu, chạy vrp.lap_tuyen rồi ghi chuyến, điểm dừng, chưa xếp."""
        for plan in self:
            if plan.state == "confirmed":
                raise UserError(_("Kế hoạch %s đã xác nhận, không lập lại tuyến được.", plan.name))
            kho_lat, kho_lng = plan._toa_do(plan.warehouse_id.partner_id)
            if kho_lat is None:
                raise UserError(_("Địa chỉ kho %s chưa có tọa độ (vĩ độ, kinh độ).", plan.warehouse_id.name))
            xe = self.env["pl.vehicle"].search([("warehouse_id", "=", plan.warehouse_id.id)])
            if not xe:
                raise UserError(_("Kho %s chưa có xe giao hàng (Inventory > Configuration > Xe giao hàng).",
                                  plan.warehouse_id.name))

            plan.trip_ids.unlink()
            plan.unassigned_ids.unlink()

            pickings = plan._get_candidate_pickings()
            tai = pickings._pl_weight_kg()
            phieu = []
            for pk in pickings:
                lat, lng = plan._toa_do(pk.partner_id)
                phieu.append({"khach": pk.partner_id.id, "vi_do": lat, "kinh_do": lng, "tai_kg": tai[pk.id],
                              "phieu": pk.id})
            diem = {d.id: d for d in vrp.gop_theo_khach(phieu)}
            kq = vrp.lap_tuyen((kho_lat, kho_lng), list(diem.values()),
                               [vrp.Xe(x.id, x.capacity_kg) for x in xe], plan.road_factor)

            trip_vals = []
            for t in kq.tuyen:
                stops = []
                for thu_tu, (khach, km) in enumerate(zip(t.diem, t.chang_km), start=1):
                    d = diem[khach]
                    stops.append((0, 0, {
                        "sequence": thu_tu,
                        "partner_id": khach,
                        "picking_ids": [(6, 0, list(d.phieu))],
                        "weight": d.tai_kg,
                        "leg_km": km,
                        "latitude": d.vi_do,
                        "longitude": d.kinh_do,
                    }))
                trip_vals.append({"plan_id": plan.id, "vehicle_id": t.xe, "weight": t.tai_kg,
                                  "return_km": t.chang_km[-1], "total_km": t.tong_km, "stop_ids": stops})
            self.env["pl.delivery.trip"].create(trip_vals)
            self.env["pl.delivery.unassigned"].create([
                {"plan_id": plan.id, "partner_id": c.id, "picking_id": pk_id, "weight": tai[pk_id],
                 "reason": c.ly_do}
                for c in kq.chua_xep for pk_id in diem[c.id].phieu])
            plan.state = "routed"
        return True

    def action_confirm(self):
        """Nút Xác nhận: ghi chuyến và thứ tự điểm dừng vào phiếu xuất, khóa kế hoạch."""
        for plan in self:
            if plan.state != "routed":
                raise UserError(_("Phải lập tuyến trước khi xác nhận."))
            pickings = plan.trip_ids.stop_ids.picking_ids
            da_xep = pickings.filtered("pl_trip_id")
            if da_xep:
                raise UserError(_("Các phiếu sau đã thuộc kế hoạch khác đã xác nhận, hãy lập tuyến lại: %s",
                                  ", ".join(da_xep.mapped("name"))))
            for stop in plan.trip_ids.stop_ids:
                stop.picking_ids.write({"pl_trip_id": stop.trip_id.id, "pl_stop_sequence": stop.sequence})
            plan.state = "confirmed"
        return True

    def action_draft(self):
        """Nút Về nháp: chỉ khi chưa xác nhận; xóa kết quả lập tuyến."""
        for plan in self:
            if plan.state == "confirmed":
                raise UserError(_("Kế hoạch đã xác nhận, không về nháp được."))
            plan.trip_ids.unlink()
            plan.unassigned_ids.unlink()
            plan.state = "draft"
        return True


class PlDeliveryTrip(models.Model):
    _name = "pl.delivery.trip"
    _description = "Chuyến giao hàng"
    _order = "plan_id, vehicle_id"

    plan_id = fields.Many2one("pl.delivery.plan", "Kế hoạch", required=True, ondelete="cascade", index=True)
    date = fields.Date(related="plan_id.date", store=True)
    state = fields.Selection(related="plan_id.state")
    vehicle_id = fields.Many2one("pl.vehicle", "Xe", required=True, ondelete="restrict")
    capacity_kg = fields.Float(related="vehicle_id.capacity_kg")
    stop_ids = fields.One2many("pl.delivery.stop", "trip_id", "Điểm dừng")
    stop_count = fields.Integer("Số điểm", compute="_compute_stop_count", store=True)
    weight = fields.Float("Tải (kg)", digits=(16, 1))
    load_pct = fields.Float("% tải trọng", compute="_compute_load_pct", store=True, digits=(16, 1))
    return_km = fields.Float("Km về kho", digits=(16, 2))
    total_km = fields.Float("Tổng km", digits=(16, 1))
    maps_url = fields.Char("Google Maps", compute="_compute_maps",
                           help="Link chỉ đường của đoạn đầu tiên; chuyến dài xem tất cả các đoạn bên dưới.")
    maps_segment_count = fields.Integer("Số đoạn Maps", compute="_compute_maps")
    maps_links = fields.Html("Link Google Maps", compute="_compute_maps", sanitize=False)

    @api.depends("stop_ids")
    def _compute_stop_count(self):
        for trip in self:
            trip.stop_count = len(trip.stop_ids)

    @api.depends("weight", "vehicle_id.capacity_kg")
    def _compute_load_pct(self):
        for trip in self:
            cap = trip.vehicle_id.capacity_kg
            trip.load_pct = 100.0 * trip.weight / cap if cap else 0.0

    @api.depends("plan_id.warehouse_id.partner_id", "stop_ids.sequence", "stop_ids.latitude",
                 "stop_ids.longitude")
    def _compute_maps(self):
        for trip in self:
            doan = trip._maps_segments()
            trip.maps_url = doan[0][2] if doan else False
            trip.maps_segment_count = len(doan)
            n = len(trip.stop_ids)
            dong = []
            for so, (dau, cuoi, url) in enumerate(doan, start=1):
                tu = _("Kho") if dau == 0 else _("điểm %s", dau)
                den = _("Kho") if cuoi == n + 1 else _("điểm %s", cuoi)
                dong.append(Markup('<li><a href="%s" target="_blank" rel="noopener">%s %s: %s → %s</a></li>') % (
                    url, escape(_("Đoạn")), so, tu, den))
            trip.maps_links = Markup("<ol>%s</ol>") % Markup("").join(dong) if dong else False

    def _maps_segments(self):
        self.ensure_one()
        kho = self.plan_id.warehouse_id.partner_id
        stops = self.stop_ids.sorted("sequence")
        if not stops or not (kho.partner_latitude or kho.partner_longitude):
            return []
        return maps.link_chuyen((kho.partner_latitude, kho.partner_longitude),
                                [(s.latitude, s.longitude) for s in stops])

    def action_open_maps(self):
        self.ensure_one()
        if not self.maps_url:
            raise UserError(_("Chuyến chưa có điểm dừng hoặc kho chưa có tọa độ."))
        return {"type": "ir.actions.act_url", "url": self.maps_url, "target": "new"}

    @api.depends("vehicle_id", "plan_id")
    def _compute_display_name(self):
        for trip in self:
            trip.display_name = f"{trip.plan_id.name} / {trip.vehicle_id.code}"


class PlDeliveryStop(models.Model):
    _name = "pl.delivery.stop"
    _description = "Điểm dừng giao hàng"
    _order = "trip_id, sequence"

    trip_id = fields.Many2one("pl.delivery.trip", "Chuyến", required=True, ondelete="cascade", index=True)
    plan_id = fields.Many2one(related="trip_id.plan_id", store=True)
    sequence = fields.Integer("Thứ tự", required=True)
    partner_id = fields.Many2one("res.partner", "Khách hàng", required=True)
    picking_ids = fields.Many2many("stock.picking", string="Phiếu xuất")
    weight = fields.Float("Tải (kg)", digits=(16, 1))
    leg_km = fields.Float("Km chặng", digits=(16, 2), help="Quãng đường từ điểm trước (hoặc kho) đến điểm này.")
    latitude = fields.Float("Vĩ độ", digits=(10, 7))
    longitude = fields.Float("Kinh độ", digits=(10, 7))
    address = fields.Char(related="partner_id.contact_address_inline", string="Địa chỉ")


class PlDeliveryUnassigned(models.Model):
    _name = "pl.delivery.unassigned"
    _description = "Phiếu xuất chưa xếp lên xe"
    _order = "plan_id, partner_id, picking_id"

    plan_id = fields.Many2one("pl.delivery.plan", "Kế hoạch", required=True, ondelete="cascade", index=True)
    picking_id = fields.Many2one("stock.picking", "Phiếu xuất", required=True, ondelete="cascade")
    origin = fields.Char(related="picking_id.origin")
    partner_id = fields.Many2one("res.partner", "Khách hàng")
    weight = fields.Float("Tải (kg)", digits=(16, 1))
    reason = fields.Char("Lý do")
