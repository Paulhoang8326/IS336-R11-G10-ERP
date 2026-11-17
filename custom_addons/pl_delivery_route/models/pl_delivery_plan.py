from datetime import datetime, time

import pytz
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_date

from ..services import maps, vrp

MUI_GIO_MAC_DINH = "Asia/Ho_Chi_Minh"
SO_DIEM_TOI_DA_MAC_DINH = 25

# Lý do chưa xếp trả về từ vrp.py -> mã lưu trong Odoo.
LY_DO = {
    vrp.LY_DO_VUOT_TAI: "overweight",
    vrp.LY_DO_THIEU_XE: "no_vehicle",
    vrp.LY_DO_THIEU_TOA_DO: "no_coordinates",
}


class PlDeliveryPlan(models.Model):
    _name = "pl.delivery.plan"
    _description = "Delivery Plan"
    _order = "date desc, id desc"

    name = fields.Char("Reference", required=True, readonly=True, copy=False, default=lambda self: _("New"))
    date = fields.Date("Delivery Date", required=True, default=fields.Date.context_today)
    warehouse_id = fields.Many2one("stock.warehouse", "Warehouse", required=True, check_company=True,
                                   default=lambda self: self.env["stock.warehouse"].search(
                                       [("company_id", "=", self.env.company.id)], limit=1))
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    state = fields.Selection([("draft", "Draft"), ("routed", "Routed"), ("confirmed", "Confirmed")],
                             "Status", default="draft", required=True, readonly=True, copy=False)
    road_factor = fields.Float("Road Factor", default=vrp.HE_SO_DUONG_MAC_DINH, digits=(4, 2),
                               help="Road distance = straight-line (haversine) distance × this factor.")
    max_stops = fields.Integer("Max Stops per Trip", default=SO_DIEM_TOI_DA_MAC_DINH,
                               help="Maximum number of customers one driver delivers to in a day. 0 means no limit.")
    trip_ids = fields.One2many("pl.delivery.trip", "plan_id", "Trips", readonly=True, copy=False)
    unassigned_ids = fields.One2many("pl.delivery.unassigned", "plan_id", "Unassigned Transfers", readonly=True,
                                     copy=False)
    total_km = fields.Float("Total km", compute="_compute_totals", store=True, digits=(16, 1))
    total_weight = fields.Float("Assigned Weight (kg)", compute="_compute_totals", store=True, digits=(16, 1))
    trip_count = fields.Integer("Trip Count", compute="_compute_totals", store=True)
    unassigned_count = fields.Integer("Unassigned", compute="_compute_unassigned_count", store=True)

    _sql_constraints = [
        ("road_factor_positive", "CHECK(road_factor >= 1)", "The road factor must be at least 1."),
        ("max_stops_positive", "CHECK(max_stops >= 0)", "The maximum number of stops cannot be negative."),
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
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("pl.delivery.plan") or _("New")
        return super().create(vals_list)

    def unlink(self):
        if any(p.state == "confirmed" for p in self):
            raise UserError(_("A confirmed delivery plan cannot be deleted."))
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
        """Nút Compute Routes: xóa kết quả cũ, chọn phiếu, chạy vrp.lap_tuyen rồi ghi chuyến, điểm dừng, chưa xếp."""
        for plan in self:
            if plan.state == "confirmed":
                raise UserError(_("Delivery plan %s is confirmed; routes cannot be recomputed.", plan.name))
            kho_lat, kho_lng = plan._toa_do(plan.warehouse_id.partner_id)
            if kho_lat is None:
                raise UserError(_("The address of warehouse %s has no coordinates (latitude, longitude).",
                                  plan.warehouse_id.name))
            xe = self.env["pl.vehicle"].search([("warehouse_id", "=", plan.warehouse_id.id)])
            if not xe:
                raise UserError(_("Warehouse %s has no delivery vehicles "
                                  "(Inventory > Configuration > Delivery Vehicles).", plan.warehouse_id.name))

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
                               [vrp.Xe(x.id, x.capacity_kg) for x in xe], plan.road_factor,
                               so_diem_toi_da=plan.max_stops or None)

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
                 "reason": LY_DO[c.ly_do]}
                for c in kq.chua_xep for pk_id in diem[c.id].phieu])
            plan.state = "routed"
        return True

    def action_confirm(self):
        """Nút Confirm: ghi chuyến và thứ tự điểm dừng vào phiếu xuất, gom phiếu của mỗi chuyến thành một
        Batch Transfer (stock.picking.batch), rồi khóa kế hoạch.

        Kiểm tra hết trước khi ghi: phiếu đã thuộc kế hoạch khác, phiếu đã nằm trong batch khác, hay một chuyến
        có phiếu thuộc nhiều loại phiếu (batch chỉ nhận phiếu cùng loại) thì báo lỗi, không tạo batch nào.
        """
        for plan in self:
            if plan.state != "routed":
                raise UserError(_("Compute the routes before confirming the plan."))
            pickings = plan.trip_ids.stop_ids.picking_ids
            da_xep = pickings.filtered("pl_trip_id")
            if da_xep:
                raise UserError(_("These transfers already belong to another confirmed plan; "
                                  "compute the routes again: %s", ", ".join(da_xep.mapped("name"))))
            trong_batch = pickings.filtered("batch_id")
            if trong_batch:
                raise UserError(_("These transfers are already in a batch transfer; remove them from it or "
                                  "compute the routes again: %s",
                                  ", ".join(f"{p.name} ({p.batch_id.name})" for p in trong_batch)))
            for trip in plan.trip_ids:
                if len(trip.stop_ids.picking_ids.picking_type_id) > 1:
                    raise UserError(_("Trip %s has transfers of different operation types and cannot be "
                                      "grouped in one batch transfer.", trip.display_name))

            ngay = format_date(self.env, plan.date)
            for trip in plan.trip_ids:
                for stop in trip.stop_ids:
                    stop.picking_ids.write({"pl_trip_id": trip.id, "pl_stop_sequence": stop.sequence,
                                            "batch_sequence": stop.sequence})
                pk = trip.stop_ids.picking_ids
                batch = self.env["stock.picking.batch"].create({
                    "description": _("%(vehicle)s - %(date)s", vehicle=trip.vehicle_id.code, date=ngay),
                    "company_id": plan.company_id.id,
                    "picking_type_id": pk.picking_type_id.id,
                    "picking_ids": [(6, 0, pk.ids)],
                })
                batch.action_confirm()
                trip.batch_id = batch
            plan.state = "confirmed"
        return True

    def action_draft(self):
        """Nút Reset to Draft: chỉ khi chưa xác nhận; xóa kết quả lập tuyến."""
        for plan in self:
            if plan.state == "confirmed":
                raise UserError(_("A confirmed delivery plan cannot be reset to draft."))
            plan.trip_ids.unlink()
            plan.unassigned_ids.unlink()
            plan.state = "draft"
        return True


class PlDeliveryTrip(models.Model):
    _name = "pl.delivery.trip"
    _description = "Delivery Trip"
    _order = "plan_id, vehicle_id"

    plan_id = fields.Many2one("pl.delivery.plan", "Delivery Plan", required=True, ondelete="cascade", index=True)
    date = fields.Date(related="plan_id.date", store=True)
    state = fields.Selection(related="plan_id.state")
    vehicle_id = fields.Many2one("pl.vehicle", "Vehicle", required=True, ondelete="restrict")
    capacity_kg = fields.Float(related="vehicle_id.capacity_kg")
    stop_ids = fields.One2many("pl.delivery.stop", "trip_id", "Stops")
    stop_count = fields.Integer("Stop Count", compute="_compute_stop_count", store=True)
    weight = fields.Float("Load (kg)", digits=(16, 1))
    load_pct = fields.Float("Load (%)", compute="_compute_load_pct", store=True, digits=(16, 1))
    return_km = fields.Float("Return km", digits=(16, 2), help="Distance from the last stop back to the warehouse.")
    total_km = fields.Float("Total km", digits=(16, 1))
    batch_id = fields.Many2one("stock.picking.batch", "Batch Transfer", readonly=True, copy=False,
                               help="Batch transfer grouping the deliveries of this trip, created on confirmation.")
    maps_url = fields.Char("Google Maps", compute="_compute_maps",
                           help="Directions link of the first segment; long trips have more segments below.")
    maps_segment_count = fields.Integer("Map Segments", compute="_compute_maps")
    maps_links = fields.Html("Google Maps Links", compute="_compute_maps", sanitize=False)

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
                tu = _("Warehouse") if dau == 0 else _("stop %s", dau)
                den = _("Warehouse") if cuoi == n + 1 else _("stop %s", cuoi)
                dong.append(Markup('<li><a href="%s" target="_blank" rel="noopener">%s</a></li>') % (
                    url, _("Segment %(no)s: %(start)s → %(end)s", no=so, start=tu, end=den)))
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
            raise UserError(_("The trip has no stops or the warehouse has no coordinates."))
        return {"type": "ir.actions.act_url", "url": self.maps_url, "target": "new"}

    @api.depends("vehicle_id", "plan_id")
    def _compute_display_name(self):
        for trip in self:
            trip.display_name = f"{trip.plan_id.name} / {trip.vehicle_id.code}"


class PlDeliveryStop(models.Model):
    _name = "pl.delivery.stop"
    _description = "Delivery Stop"
    _order = "trip_id, sequence"

    trip_id = fields.Many2one("pl.delivery.trip", "Trip", required=True, ondelete="cascade", index=True)
    plan_id = fields.Many2one(related="trip_id.plan_id", store=True)
    sequence = fields.Integer("Sequence", required=True)
    partner_id = fields.Many2one("res.partner", "Customer", required=True)
    picking_ids = fields.Many2many("stock.picking", string="Transfers")
    weight = fields.Float("Load (kg)", digits=(16, 1))
    leg_km = fields.Float("Leg km", digits=(16, 2), help="Distance from the previous stop (or the warehouse).")
    latitude = fields.Float("Latitude", digits=(10, 7))
    longitude = fields.Float("Longitude", digits=(10, 7))
    address = fields.Char(related="partner_id.contact_address_inline", string="Address")


class PlDeliveryUnassigned(models.Model):
    _name = "pl.delivery.unassigned"
    _description = "Unassigned Delivery Transfer"
    _order = "plan_id, partner_id, picking_id"

    plan_id = fields.Many2one("pl.delivery.plan", "Delivery Plan", required=True, ondelete="cascade", index=True)
    picking_id = fields.Many2one("stock.picking", "Transfer", required=True, ondelete="cascade")
    origin = fields.Char(related="picking_id.origin")
    partner_id = fields.Many2one("res.partner", "Customer")
    weight = fields.Float("Load (kg)", digits=(16, 1))
    reason = fields.Selection([
        ("overweight", "Heavier than the largest vehicle"),
        ("no_vehicle", "Not enough vehicles"),
        ("no_coordinates", "Missing coordinates"),
    ], "Reason", required=True)
