#!/usr/bin/env python3
"""Chạy thử trọn quy trình Order-to-Cash trên bản nhân bản của database chính, xong thì xóa bản đó.

Nhân bản pl_moc thành pl_o2c_check rồi làm lần lượt:

0. Module: kiểm tra đã cài sale_management, purchase_stock, sale_stock, account, product_expiry,
   pl_fefo_pick, pl_delivery_route. In danh sách module pl_moc đang thiếu (chỉ đọc, không cài gì lên pl_moc),
   cài phần thiếu trên bản nhân bản. Chạy lại seed_import.py lên bản nhân bản: phải không còn cảnh báo,
   Sales Settings phải để Invoicing Policy = Delivered quantities.
1. Mua hàng: đơn mua 1 mã dầu ăn Wilmar, xác nhận, nhận hàng với lô mới và hạn dùng.
   Kiểm tra: hàng vào ô kệ của dãy Wilmar theo quy tắc cất hàng, không nằm ở PL/Stock.
2. Bán hàng: 3 đơn cùng mã, Delivery Date 08:00 ngày mốc, cho 3 khách lấy từ seed:
   X trả ngay (tạp hóa), Y có hạn thanh toán (căn tin KCN), Z có hạn mức nợ (minimart) và đã có sẵn một hóa
   đơn chưa thu, đủ để đơn mới vượt hạn mức.
   Kiểm tra: phiếu xuất Ready đủ hàng, lô được giữ còn hạn dùng lúc giao không dưới mức tối thiểu của khách
   (pl_fefo_pick); với Z, báo giá có cảnh báo vượt hạn mức (sale.order.partner_credit_warning), X và Y không có.
   Odoo 18 Community chỉ cảnh báo, không chặn: đơn Z vẫn xác nhận được, script chỉ ghi nhận.
3. Lập tuyến: kế hoạch giao hàng ngày mốc (pl_delivery_route), Compute Routes, Confirm.
   Kiểm tra: 3 phiếu của X, Y, Z nằm trong chuyến, đã ghi chuyến vào phiếu.
4. Giao hàng: X giao đủ; Y giao thiếu, tạo backorder; Z giao thiếu, không tạo backorder.
   Kiểm tra: X không có backorder; backorder của Y tồn tại, còn đúng phần thiếu; phần thiếu của Z không còn
   move mở.
5. Hóa đơn: tạo (Create Invoice > Regular invoice) và post hóa đơn từ cả 3 đơn.
   Kiểm tra: số lượng trên hóa đơn bằng số lượng đã giao, không phải số lượng đặt; tạo hóa đơn lần nữa cho Y
   (phần backorder chưa giao) bị Odoo từ chối.
6. Thu tiền: X Register Payment toàn bộ vào sổ tiền mặt (tài xế thu khi giao, kế toán ghi nhận lúc đối chiếu
   cuối ngày); Y không thu.
   Kiểm tra: hóa đơn X ở trạng thái Paid; hóa đơn Y còn nợ đúng tổng hóa đơn, ngày đến hạn = ngày hóa đơn +
   hạn thanh toán của khách.
7. Backorder của Y: giao nốt, xuất hóa đơn lần 2.
   Kiểm tra: tổng số lượng đã xuất hóa đơn của đơn Y bằng số lượng đặt.

Cuối cùng in bảng từng bước PASS/FAIL kèm số phiếu, số hóa đơn để đối chiếu trên giao diện khi dùng --keep.
Sai điều nào thì in FAIL, mã thoát khác 0.

    python scripts/check_o2c.py
    python scripts/check_o2c.py --keep            # giữ database check để xem trên giao diện
    python scripts/check_o2c.py --policy-order    # thử âm: giữ invoice_policy = order, phải FAIL ở bước 5

Mật khẩu như scripts/seminar3: admin lấy từ ODOO_PASSWORD, master từ ODOO_MASTER_PASSWORD hoặc
config/odoo.conf.
"""

import argparse
import datetime as dt
import getpass
import os
import subprocess
import sys
import xmlrpc.client
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "seminar3"))

from chung import DB_CHINH, URL, Odoo, QuanLyDb, cai_module, goi, ket_noi, kiem, utc  # noqa: E402
from seed_import import GIO_DAT_HANG, GIO_VN, doc_csv  # noqa: E402

DB_CHECK = "pl_o2c_check"
MODULES = ["sale_management", "purchase_stock", "sale_stock", "account", "product_expiry",
           "pl_fefo_pick", "pl_delivery_route"]
SEED = ROOT / "seed" / "demo"
NCC = "NCC01"  # Wilmar
LOT_MUA = "LO2CCHECK"
THUNG_MUA = 10
# (thùng đặt, thùng giao lần đầu) của từng khách.
THUNG = {"X": (2, 2), "Y": (4, 3), "Z": (3, 2)}
VAI_TRO = {"X": "trả ngay", "Y": "công nợ", "Z": "vượt hạn mức"}


def dt_odoo(s):
    return dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S") if s else None


def con_pct(han, giao, ngay_han):
    return (han - giao).total_seconds() / 86400 / ngay_han * 100


def loi_odoo(e):
    dong = [d for d in e.faultString.strip().splitlines() if d.strip()]
    return "\n".join(dong[-6:])


class Bang:
    """Kết quả từng bước: (bước, nội dung, PASS/FAIL, chứng từ để đối chiếu)."""

    BUOC = ["Module, seed_import", "Mua hàng, nhận hàng", "Bán hàng, giữ lô, hạn mức", "Lập tuyến",
            "Giao hàng", "Hóa đơn theo số giao", "Thu tiền", "Backorder Y, hóa đơn lần 2"]

    def __init__(self):
        self.dong = {}

    def chay(self, so, ham, *args):
        print(f"\n=== Bước {so}. {self.BUOC[so]}")
        try:
            chung_tu = ham(*args)
        except AssertionError as e:
            self.dong[so] = ("FAIL", str(e))
            raise
        except xmlrpc.client.Fault as e:
            self.dong[so] = ("FAIL", "lỗi Odoo: " + loi_odoo(e).splitlines()[-1])
            raise
        self.dong[so] = ("PASS", chung_tu)

    def in_ra(self):
        print("\n=== Tóm tắt")
        rong = max(len(b) for b in self.BUOC)
        for so, ten in enumerate(self.BUOC):
            kq, ct = self.dong.get(so, ("-", "chưa chạy"))
            print(f"{so}  {ten:<{rong}}  {kq:<4}  {ct}")


class O2C:
    def __init__(self, od, url, db, ngay_moc, giu_order):
        self.od, self.url, self.db, self.ngay_moc, self.giu_order = od, url, db, ngay_moc, giu_order
        self.giao = dt_odoo(utc(ngay_moc, GIO_DAT_HANG))
        self.kh = {}     # vai trò -> partner
        self.don = {}    # vai trò -> dict(so_id, name, pick_id, ...)

    # ------------------------------------------------------------------ bước 0

    def buoc_0(self, thieu_nguon):
        od = self.od
        vua_cai = cai_module(od, *MODULES)
        print(f"Đã cài trên {self.db}: {', '.join(vua_cai) if vua_cai else '(không cần cài thêm)'}")
        kiem(set(vua_cai) <= set(thieu_nguon), f"{self.db} phải cài {vua_cai}, khác với phần {DB_CHINH} thiếu")

        env = dict(os.environ, ODOO_PASSWORD=os.environ.get("ODOO_PASSWORD", ""))
        kq = subprocess.run([sys.executable, str(ROOT / "scripts" / "seed_import.py"), "--url", self.url,
                             "--db", self.db], capture_output=True, text=True, encoding="utf-8", env=env)
        kiem(kq.returncode == 0, f"seed_import.py lỗi:\n{kq.stdout[-800:]}\n{kq.stderr[-800:]}")
        canh_bao = [d.strip() for d in kq.stdout.splitlines() if "CẢNH BÁO" in d]
        kiem(not canh_bao and "Cảnh báo: 0" in kq.stdout, "seed_import.py còn cảnh báo: " + "; ".join(canh_bao))
        for d in kq.stdout.splitlines():
            if d.strip().startswith(("Đã bật", "Cài đặt ", "Sản phẩm ", "Xe giao hàng ")):
                print(f"  seed_import: {d.strip()}")

        sid = od("res.config.settings", "create", {})
        chinh_sach = od("res.config.settings", "read", [sid], fields=["default_invoice_policy"])[0]
        kiem(chinh_sach["default_invoice_policy"] == "delivery",
             f"Sales Settings > Invoicing Policy đang {chinh_sach['default_invoice_policy']}, cần delivery")
        if self.giu_order:
            ids = od("product.template", "search", [("default_code", "=like", "NCC%")])
            od("product.template", "write", ids, {"invoice_policy": "order"})
            print(f"  --policy-order: ghi invoice_policy = order cho {len(ids)} sản phẩm")
        dem = {}
        for r in od.search_read("product.template", [("default_code", "=like", "NCC%")], ["invoice_policy"]):
            dem[r["invoice_policy"]] = dem.get(r["invoice_policy"], 0) + 1
        print(f"  Invoicing Policy mặc định: delivery; sản phẩm seed: {dem}")
        return f"cài {', '.join(vua_cai) or 'không'}; seed_import 0 cảnh báo; sản phẩm {dem}"

    # ------------------------------------------------------------------ bước 1

    def chon_san_pham(self):
        """Mã dầu ăn Wilmar có nhiều lô nhất (ưu tiên có lô còn 30-60% hạn dùng lúc giao, để thấy khách 60%
        không lấy lô mà khách 30% lấy được)."""
        od = self.od
        sps = od.search_read("product.product", [("default_code", "=like", f"{NCC}-%"), ("name", "ilike", "dầu"),
                                                 ("categ_id.name", "=", "Dầu ăn")],
                             ["default_code", "display_name", "expiration_time", "uom_id"], order="default_code")
        kiem(sps, f"không có mã dầu ăn {NCC}")
        tot = None
        for sp in sps:
            lo = od.search_read("stock.lot", [("product_id", "=", sp["id"]), ("product_qty", ">", 0)],
                                ["expiration_date"])
            giua = sum(1 for l in lo if l["expiration_date"] and
                       30 <= con_pct(dt_odoo(l["expiration_date"]), self.giao, sp["expiration_time"]) < 60)
            diem = (giua > 0, len(lo))
            if tot is None or diem > tot[0]:
                tot = (diem, sp)
        sp = tot[1]
        goi_thung = od.search_read("product.packaging", [("product_id", "=", sp["id"])], ["qty"])
        sp["n"] = int(goi_thung[0]["qty"]) if goi_thung else 1
        sp["thung_id"] = goi_thung[0]["id"] if goi_thung else False
        return sp

    def buoc_1(self):
        od = self.od
        self.sp = sp = self.chon_san_pham()
        print(f"Sản phẩm: {sp['display_name']}, thùng {sp['n']}, hạn dùng {sp['expiration_time']} ngày")
        ncc = od.search_read("res.partner", [("ref", "=", NCC), ("parent_id", "=", False)], ["name"])
        kiem(ncc, f"không có nhà cung cấp {NCC}")
        po = od("purchase.order", "create", {
            "partner_id": ncc[0]["id"],
            "order_line": [(0, 0, {"product_id": sp["id"], "product_qty": THUNG_MUA * sp["n"],
                                   "product_packaging_id": sp["thung_id"]})],
        })
        goi(od, "purchase.order", "button_confirm", [po])
        po_r = od("purchase.order", "read", [po], fields=["name", "state", "picking_ids"])[0]
        kiem(po_r["state"] == "purchase" and len(po_r["picking_ids"]) == 1,
             f"{po_r['name']}: {po_r['state']}, {len(po_r['picking_ids'])} phiếu nhập")
        nhap = po_r["picking_ids"][0]

        # Hạn dùng của lô mới: đủ thời hạn tính từ ngày mốc, 00:00 giờ Việt Nam.
        han = dt.datetime.combine(self.ngay_moc + dt.timedelta(days=sp["expiration_time"]), dt.time()) \
            - dt.timedelta(hours=GIO_VN)
        mls = od.search_read("stock.move.line", [("picking_id", "=", nhap)], ["location_dest_id", "quantity"])
        kiem(len(mls) == 1, f"phiếu nhập có {len(mls)} dòng chi tiết")
        od("stock.move.line", "write", [mls[0]["id"]], {
            "lot_name": LOT_MUA, "expiration_date": han.strftime("%Y-%m-%d %H:%M:%S"),
            "quantity": THUNG_MUA * sp["n"], "picked": True})
        goi(od, "stock.picking", "button_validate", [nhap])
        p = od("stock.picking", "read", [nhap], fields=["name", "state", "location_dest_id"])[0]
        kiem(p["state"] == "done", f"phiếu nhập {p['name']} đang {p['state']}")

        kho = od.search_read("stock.warehouse", [("code", "=", "PL")], ["lot_stock_id"])[0]
        self.kho_id, ton = kho["id"], kho["lot_stock_id"][0]
        day = od.search_read("stock.location", [("barcode", "=", "PL-A")], ["complete_name"])
        kiem(day, "không có dãy PL-A (Wilmar)")
        ql = od.search_read("stock.putaway.rule", [("product_id", "=", sp["id"]), ("location_in_id", "=", ton)],
                            ["location_out_id"])
        kiem(ql and ql[0]["location_out_id"][0] == day[0]["id"],
             f"quy tắc cất hàng của {sp['default_code']} không trỏ vào dãy Wilmar: {ql}")
        quant = od.search_read("stock.quant", [("lot_id.name", "=", LOT_MUA), ("product_id", "=", sp["id"]),
                                               ("location_id.usage", "=", "internal")],
                               ["location_id", "quantity"])
        kiem(quant and sum(q["quantity"] for q in quant) == THUNG_MUA * sp["n"],
             f"lô {LOT_MUA}: tồn {[(q['location_id'][1], q['quantity']) for q in quant]}")
        trong_day = od("stock.location", "search", [("id", "child_of", day[0]["id"])])
        for q in quant:
            kiem(q["location_id"][0] != ton, f"lô {LOT_MUA} nằm ở PL/Stock")
            kiem(q["location_id"][0] in trong_day and q["location_id"][0] != day[0]["id"],
                 f"lô {LOT_MUA} nằm ở {q['location_id'][1]}, không phải ô của {day[0]['complete_name']}")
        noi = ", ".join(sorted({q["location_id"][1] for q in quant}))
        print(f"{po_r['name']} > {p['name']}: {THUNG_MUA} thùng lô {LOT_MUA}, hạn {han:%d/%m/%Y} UTC, vào {noi}")
        return f"{po_r['name']}, {p['name']}: lô {LOT_MUA} vào {noi}"

    # ------------------------------------------------------------------ bước 2

    def chon_khach(self):
        khach = doc_csv(SEED / "khach_hang.csv")

        def dau_tien(dk, sap=None):
            ds = [r for r in khach if dk(r) and r["ma_kh"] not in {k["ref"] for k in self.kh.values()}]
            kiem(ds, "seed không có khách phù hợp")
            return sorted(ds, key=sap)[0] if sap else ds[0]

        chon = {
            "X": dau_tien(lambda r: r["nhom_khach"] == "Tạp hóa" and r["han_thanh_toan_ngay"] == "0"
                          and not r["han_muc_no"]),
            "Y": dau_tien(lambda r: r["nhom_khach"] == "Căn tin KCN" and int(r["han_thanh_toan_ngay"]) > 0),
            "Z": dau_tien(lambda r: r["nhom_khach"] == "Minimart" and r["han_muc_no"],
                          lambda r: int(r["han_muc_no"])),
        }
        for vai, r in chon.items():
            kh = self.od.search_read("res.partner", [("ref", "=", r["ma_kh"]), ("parent_id", "=", False)],
                                     ["ref", "name", "pl_min_shelf_life_pct", "credit_limit",
                                      "use_partner_credit_limit", "property_payment_term_id", "credit"])
            kiem(kh, f"không có khách {r['ma_kh']}")
            self.kh[vai] = kh[0]

    def tao_cong_no(self, kh, so_tien):
        """Hóa đơn đã post, chưa thu của khách Z: công nợ có sẵn trước đơn mới."""
        od = self.od
        hd = od("account.move", "create", {
            "move_type": "out_invoice", "partner_id": kh["id"],
            "invoice_line_ids": [(0, 0, {"name": "Công nợ đơn trước", "quantity": 1, "price_unit": so_tien,
                                         "tax_ids": [(6, 0, [])]})],
        })
        goi(od, "account.move", "action_post", [hd])
        return od("account.move", "read", [hd], fields=["name", "amount_residual"])[0]

    def buoc_2(self):
        od, sp = self.od, self.sp
        self.chon_khach()
        lo = {l["id"]: l for l in od.search_read("stock.lot", [("product_id", "=", sp["id"])],
                                                 ["name", "expiration_date"])}
        chung_tu = []
        for vai in "XYZ":
            kh = self.kh[vai]
            dat, giao = THUNG[vai]
            so_id = od("sale.order", "create", {
                "partner_id": kh["id"], "warehouse_id": self.kho_id,
                "date_order": utc(self.ngay_moc, GIO_DAT_HANG), "commitment_date": utc(self.ngay_moc, GIO_DAT_HANG),
                "order_line": [(0, 0, {"product_id": sp["id"], "product_uom_qty": dat * sp["n"],
                                       "product_packaging_id": sp["thung_id"]})],
            })
            so = od("sale.order", "read", [so_id], fields=["name", "amount_total", "pl_min_shelf_life_pct"])[0]
            no_cu = None
            if vai == "Z":
                kiem(kh["use_partner_credit_limit"] and kh["credit_limit"] > 0, f"{kh['name']} không có hạn mức nợ")
                # Nợ cũ chưa vượt hạn mức; cộng đơn mới thì vượt.
                no_cu = self.tao_cong_no(kh, round(kh["credit_limit"] - so["amount_total"] / 2))
                print(f"  Công nợ có sẵn của {kh['ref']}: {no_cu['name']} {no_cu['amount_residual']:,.0f} đ, "
                      f"hạn mức {kh['credit_limit']:,.0f} đ")
            canh_bao = od("sale.order", "read", [so_id], fields=["partner_credit_warning"])[0]["partner_credit_warning"]
            goi(od, "sale.order", "action_confirm", [so_id])
            so = od("sale.order", "read", [so_id], fields=["name", "state", "amount_total", "picking_ids"])[0]
            kiem(so["state"] == "sale", f"{so['name']} ({vai}) đang {so['state']}")
            phieu = od.search_read("stock.picking", [("sale_id", "=", so_id), ("picking_type_code", "=", "outgoing")],
                                   ["name", "state", "scheduled_date"])
            kiem(len(phieu) == 1, f"{so['name']}: {len(phieu)} phiếu xuất")
            if phieu[0]["state"] != "assigned":
                goi(od, "stock.picking", "action_assign", [phieu[0]["id"]])
            p = od("stock.picking", "read", [phieu[0]["id"]], fields=["name", "state", "scheduled_date"])[0]
            self.don[vai] = dict(so_id=so_id, so=so["name"], pick_id=p["id"], phieu=p["name"],
                                 tong=so["amount_total"], dat=dat * sp["n"], giao=giao * sp["n"], no_cu=no_cu)
            pct = kh["pl_min_shelf_life_pct"]
            print(f"{vai} ({VAI_TRO[vai]}) {kh['ref']} {kh['name']}: {so['name']} {so['amount_total']:,.0f} đ, "
                  f"{p['name']} {p['state']}, hạn dùng tối thiểu {pct}%")
            kiem(p["scheduled_date"] == utc(self.ngay_moc, GIO_DAT_HANG),
                 f"{p['name']}: ngày dự kiến {p['scheduled_date']}, cần {utc(self.ngay_moc, GIO_DAT_HANG)}")
            kiem(p["state"] == "assigned", f"{p['name']} ({vai}) đang {p['state']}, cần Ready")
            mls = od.search_read("stock.move.line", [("picking_id", "=", p["id"])], ["lot_id", "quantity"])
            kiem(sum(m["quantity"] for m in mls) == dat * sp["n"],
                 f"{p['name']}: giữ {sum(m['quantity'] for m in mls)}/{dat * sp['n']}")
            for m in mls:
                l = lo[m["lot_id"][0]]
                con = con_pct(dt_odoo(l["expiration_date"]), self.giao, sp["expiration_time"])
                print(f"  giữ lô {l['name']} {m['quantity'] / sp['n']:g} thùng, còn {con:.1f}% lúc giao")
                kiem(con >= pct, f"{p['name']} ({vai}) giữ lô {l['name']} còn {con:.1f}% < {pct}%")
            if vai == "Z":
                kiem(canh_bao, f"{so['name']} (Z) không có cảnh báo vượt hạn mức (partner_credit_warning trống)")
                print(f"  partner_credit_warning: {canh_bao.splitlines()[0]}")
                print(f"  Odoo không chặn: {so['name']} vẫn xác nhận, trạng thái {so['state']}")
                chung_tu.append(f"Z {so['name']} {p['name']} (cảnh báo hạn mức, nợ cũ {no_cu['name']})")
            else:
                kiem(not canh_bao, f"{so['name']} ({vai}) có cảnh báo hạn mức: {canh_bao}")
                chung_tu.append(f"{vai} {so['name']} {p['name']}")
        return "; ".join(chung_tu)

    # ------------------------------------------------------------------ bước 3

    def buoc_3(self):
        od = self.od
        plan_id = od("pl.delivery.plan", "create", {"date": self.ngay_moc.isoformat(), "warehouse_id": self.kho_id})
        goi(od, "pl.delivery.plan", "action_compute_routes", [plan_id])
        stops = od.search_read("pl.delivery.stop", [("plan_id", "=", plan_id)], ["trip_id", "picking_ids"])
        chua = od.search_read("pl.delivery.unassigned", [("plan_id", "=", plan_id)], ["picking_id", "reason"])
        trong_chuyen = {p: s["trip_id"][1] for s in stops for p in s["picking_ids"]}
        for vai, d in self.don.items():
            kiem(d["pick_id"] in trong_chuyen,
                 f"{d['phieu']} ({vai}) không nằm trong chuyến; chưa xếp: "
                 f"{[(c['picking_id'][1], c['reason']) for c in chua]}")
        goi(od, "pl.delivery.plan", "action_confirm", [plan_id])
        plan = od("pl.delivery.plan", "read", [plan_id], fields=["name", "state", "trip_count"])[0]
        kiem(plan["state"] == "confirmed", f"{plan['name']} đang {plan['state']}")
        ghi = od("stock.picking", "read", [d["pick_id"] for d in self.don.values()],
                 fields=["name", "pl_trip_id", "pl_stop_sequence", "batch_id"])
        for p in ghi:
            kiem(p["pl_trip_id"] and p["pl_stop_sequence"], f"{p['name']} chưa ghi chuyến sau khi xác nhận")
            print(f"  {p['name']}: {p['pl_trip_id'][1]}, điểm {p['pl_stop_sequence']}, "
                  f"{p['batch_id'][1] if p['batch_id'] else 'không batch'}")
        chuyen = sorted({p["pl_trip_id"][1] for p in ghi})
        print(f"{plan['name']}: {plan['trip_count']} chuyến, 3 phiếu nằm trong {', '.join(chuyen)}")
        return f"{plan['name']}: {', '.join(chuyen)}"

    # ------------------------------------------------------------------ bước 4

    def validate(self, pick_id, so_luong, backorder):
        """Đặt số lượng giao (đơn vị lẻ) rồi Validate. Giao thiếu thì Odoo hỏi backorder: backorder=True là
        Create Backorder, False là No Backorder."""
        od = self.od
        moves = od.search_read("stock.move", [("picking_id", "=", pick_id)], ["product_uom_qty"])
        kiem(len(moves) == 1, f"phiếu {pick_id} có {len(moves)} move")
        od("stock.move", "write", [moves[0]["id"]], {"quantity": so_luong, "picked": True})
        kq = goi(od, "stock.picking", "button_validate", [pick_id])
        if isinstance(kq, dict) and kq.get("res_model") == "stock.backorder.confirmation":
            ctx = kq.get("context", {})
            wiz = od("stock.backorder.confirmation", "create", {"pick_ids": [(4, pick_id)]}, context=ctx)
            goi(od, "stock.backorder.confirmation", "process" if backorder else "process_cancel_backorder", [wiz],
                context=ctx)
        else:
            kiem(so_luong >= moves[0]["product_uom_qty"], f"giao thiếu phiếu {pick_id} mà Odoo không hỏi backorder")
        return od("stock.picking", "read", [pick_id], fields=["name", "state"])[0]

    def buoc_4(self):
        od, n = self.od, self.sp["n"]
        chung_tu = []
        for vai, backorder in (("X", False), ("Y", True), ("Z", False)):
            d = self.don[vai]
            p = self.validate(d["pick_id"], d["giao"], backorder)
            kiem(p["state"] == "done", f"{p['name']} ({vai}) đang {p['state']}")
            bo = od.search_read("stock.picking", [("backorder_id", "=", d["pick_id"])], ["name", "state"])
            line = od.search_read("sale.order.line", [("order_id", "=", d["so_id"])], ["qty_delivered"])[0]
            kiem(line["qty_delivered"] == d["giao"], f"{d['so']}: đã giao {line['qty_delivered']}, cần {d['giao']}")
            mo = od.search_read("stock.move", [("sale_line_id.order_id", "=", d["so_id"]),
                                               ("state", "not in", ["done", "cancel"])],
                                ["picking_id", "product_uom_qty"])
            con_mo = sum(m["product_uom_qty"] for m in mo)
            print(f"{vai} {p['name']}: giao {d['giao'] / n:g}/{d['dat'] / n:g} thùng, "
                  f"backorder {', '.join(b['name'] + ' ' + b['state'] for b in bo) or 'không'}, "
                  f"move mở {con_mo / n:g} thùng")
            if vai == "Y":
                kiem(len(bo) == 1 and bo[0]["state"] not in ("done", "cancel"), f"{p['name']} (Y): backorder {bo}")
                kiem(con_mo == d["dat"] - d["giao"], f"backorder Y còn {con_mo}, cần {d['dat'] - d['giao']}")
                d["bo_id"], d["bo"] = bo[0]["id"], bo[0]["name"]
                chung_tu.append(f"Y {p['name']} thiếu {(d['dat'] - d['giao']) / n:g} thùng, backorder {bo[0]['name']}")
            else:
                kiem(not bo, f"{p['name']} ({vai}) không được có backorder: {bo}")
                kiem(not mo, f"{d['so']} ({vai}) còn move mở: {mo}")
                chung_tu.append(f"{vai} {p['name']}" + (f" bỏ {(d['dat'] - d['giao']) / n:g} thùng" if vai == "Z" else ""))
        return "; ".join(chung_tu)

    # ------------------------------------------------------------------ bước 5

    def xuat_hoa_don(self, so_id):
        """Create Invoice > Regular invoice trên đơn bán, rồi post. Trả về id hóa đơn mới."""
        od = self.od
        ctx = {"active_model": "sale.order", "active_ids": [so_id], "active_id": so_id}
        cu = set(od("sale.order", "read", [so_id], fields=["invoice_ids"])[0]["invoice_ids"])
        wiz = od("sale.advance.payment.inv", "create", {"advance_payment_method": "delivered"}, context=ctx)
        goi(od, "sale.advance.payment.inv", "create_invoices", [wiz], context=ctx)
        moi = sorted(set(od("sale.order", "read", [so_id], fields=["invoice_ids"])[0]["invoice_ids"]) - cu)
        kiem(len(moi) == 1, f"đơn {so_id}: tạo {len(moi)} hóa đơn")
        goi(od, "account.move", "action_post", moi)
        return moi[0]

    def so_luong_hoa_don(self, inv_id):
        lines = self.od.search_read("account.move.line", [("move_id", "=", inv_id), ("display_type", "=", "product")],
                                    ["quantity"])
        return sum(l["quantity"] for l in lines)

    def buoc_5(self):
        od, n = self.od, self.sp["n"]
        chung_tu = []
        for vai in "XYZ":
            d = self.don[vai]
            inv = self.xuat_hoa_don(d["so_id"])
            hd = od("account.move", "read", [inv], fields=["name", "state", "amount_total"])[0]
            sl = self.so_luong_hoa_don(inv)
            d.update(inv=inv, hd=hd["name"], hd_tong=hd["amount_total"])
            print(f"{vai} {d['so']}: {hd['name']} {hd['state']}, {sl / n:g} thùng, {hd['amount_total']:,.0f} đ "
                  f"(đặt {d['dat'] / n:g}, giao {d['giao'] / n:g})")
            kiem(hd["state"] == "posted", f"{hd['name']} đang {hd['state']}")
            kiem(sl == d["giao"], f"{hd['name']} ({vai}) lập {sl / n:g} thùng, đã giao {d['giao'] / n:g} thùng "
                                   f"(đặt {d['dat'] / n:g}): hóa đơn không theo số lượng giao")
            chung_tu.append(f"{vai} {hd['name']} {sl / n:g} thùng")

        # Phần backorder của Y chưa giao: không tạo được hóa đơn.
        y = self.don["Y"]
        line = od.search_read("sale.order.line", [("order_id", "=", y["so_id"])],
                              ["qty_to_invoice", "qty_invoiced"])[0]
        kiem(line["qty_to_invoice"] == 0, f"{y['so']} còn {line['qty_to_invoice']} chờ xuất hóa đơn khi chưa giao")
        loi = None
        try:
            self.xuat_hoa_don(y["so_id"])
        except xmlrpc.client.Fault as e:
            loi = e
        except AssertionError as e:
            loi = e
        kiem(isinstance(loi, xmlrpc.client.Fault) and loi.faultCode == 2,
             f"tạo hóa đơn cho phần backorder chưa giao của {y['so']} phải bị Odoo từ chối, được: {loi or 'tạo được'}")
        print(f"Y {y['so']}: tạo hóa đơn lần nữa trước khi giao backorder bị từ chối: "
              f"{loi.faultString.strip().splitlines()[0]}")
        chung_tu.append("Y backorder chưa giao: không lập được")
        return "; ".join(chung_tu)

    # ------------------------------------------------------------------ bước 6

    def buoc_6(self):
        od = self.od
        x, y = self.don["X"], self.don["Y"]
        so_quy = od.search_read("account.journal", [("type", "=", "cash")], ["name", "code"], order="id")
        kiem(so_quy, "không có sổ tiền mặt")
        ctx = {"active_model": "account.move", "active_ids": [x["inv"]]}
        wiz = od("account.payment.register", "create", {"journal_id": so_quy[0]["id"]}, context=ctx)
        goi(od, "account.payment.register", "action_create_payments", [wiz], context=ctx)
        hx = od("account.move", "read", [x["inv"]], fields=["name", "payment_state", "amount_residual"])[0]
        tt = od.search_read("account.payment", [("partner_id", "=", self.kh["X"]["id"])],
                            ["name", "amount", "state", "journal_id"])
        print(f"X {hx['name']}: thu {tt[0]['amount']:,.0f} đ vào {tt[0]['journal_id'][1]} ({tt[0]['name']}), "
              f"payment_state {hx['payment_state']}, còn nợ {hx['amount_residual']:,.0f}")
        kiem(hx["payment_state"] == "paid" and hx["amount_residual"] == 0,
             f"{hx['name']} (X): payment_state {hx['payment_state']}, còn nợ {hx['amount_residual']}")

        hy = od("account.move", "read", [y["inv"]], fields=["name", "payment_state", "amount_residual", "amount_total",
                                                            "invoice_date", "invoice_date_due",
                                                            "invoice_payment_term_id"])[0]
        han = self.kh["Y"]["property_payment_term_id"]
        ngay = od.search_read("account.payment.term.line", [("payment_id", "=", han[0])], ["nb_days"])
        kiem(len(ngay) == 1, f"hạn thanh toán {han[1]} có {len(ngay)} dòng")
        den_han = dt.date.fromisoformat(hy["invoice_date"]) + dt.timedelta(days=ngay[0]["nb_days"])
        print(f"Y {hy['name']}: không thu, còn nợ {hy['amount_residual']:,.0f}/{hy['amount_total']:,.0f} đ, "
              f"ngày hóa đơn {hy['invoice_date']}, đến hạn {hy['invoice_date_due']} ({han[1]})")
        kiem(hy["amount_residual"] == hy["amount_total"] and hy["payment_state"] == "not_paid",
             f"{hy['name']} (Y): còn nợ {hy['amount_residual']}, tổng {hy['amount_total']}, {hy['payment_state']}")
        kiem(hy["invoice_payment_term_id"] and hy["invoice_payment_term_id"][0] == han[0],
             f"{hy['name']}: hạn thanh toán {hy['invoice_payment_term_id']}, khách dùng {han[1]}")
        kiem(hy["invoice_date_due"] == den_han.isoformat(),
             f"{hy['name']}: đến hạn {hy['invoice_date_due']}, cần {den_han}")
        return f"X {hx['name']} paid ({tt[0]['name']}, {tt[0]['journal_id'][1]}); " \
               f"Y {hy['name']} nợ {hy['amount_residual']:,.0f} đ đến {hy['invoice_date_due']}"

    # ------------------------------------------------------------------ bước 7

    def buoc_7(self):
        od, n = self.od, self.sp["n"]
        y = self.don["Y"]
        p = self.validate(y["bo_id"], y["dat"] - y["giao"], False)
        kiem(p["state"] == "done", f"{p['name']} đang {p['state']}")
        inv = self.xuat_hoa_don(y["so_id"])
        hd = od("account.move", "read", [inv], fields=["name", "state"])[0]
        line = od.search_read("sale.order.line", [("order_id", "=", y["so_id"])],
                              ["product_uom_qty", "qty_delivered", "qty_invoiced"])[0]
        tong = sum(self.so_luong_hoa_don(i) for i in (y["inv"], inv))
        print(f"Y {p['name']} giao {(y['dat'] - y['giao']) / n:g} thùng > {hd['name']} {hd['state']} "
              f"{self.so_luong_hoa_don(inv) / n:g} thùng; đơn {y['so']}: đặt {line['product_uom_qty'] / n:g}, "
              f"giao {line['qty_delivered'] / n:g}, đã xuất hóa đơn {line['qty_invoiced'] / n:g} thùng")
        kiem(hd["state"] == "posted", f"{hd['name']} đang {hd['state']}")
        kiem(line["qty_invoiced"] == line["product_uom_qty"] == tong,
             f"{y['so']}: đã xuất hóa đơn {line['qty_invoiced']} (2 hóa đơn {tong}), đặt {line['product_uom_qty']}")
        return f"{p['name']}, {hd['name']}: {y['so']} đã xuất hóa đơn {tong / n:g}/{line['product_uom_qty'] / n:g} thùng"

    def chay(self, bang, thieu_nguon):
        bang.chay(0, self.buoc_0, thieu_nguon)
        for so in range(1, 8):
            bang.chay(so, getattr(self, f"buoc_{so}"))


def module_thieu(url, db, password):
    """Module trong MODULES chưa cài trên database nguồn. Chỉ đọc."""
    od = Odoo(url, db, "admin", password)
    co = {m["name"]: m["state"] for m in od.search_read("ir.module.module", [("name", "in", MODULES)],
                                                        ["name", "state"])}
    return [m for m in MODULES if co.get(m) != "installed"]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", default=URL)
    p.add_argument("--src", default=DB_CHINH)
    p.add_argument("--db", default=DB_CHECK)
    p.add_argument("--keep", action="store_true", help="không xóa database check")
    p.add_argument("--policy-order", action="store_true",
                   help="thử âm: ghi invoice_policy = order cho sản phẩm trên bản nhân bản, phải FAIL ở bước 5")
    args = p.parse_args()
    kiem(args.db != args.src, "--db phải khác --src")

    don_ban = doc_csv(SEED / "don_ban.csv")
    ngay_moc = dt.date.fromisoformat(don_ban[0]["ngay"])
    print(f"Ngày mốc {ngay_moc:%d/%m/%Y}")

    url = args.url.rstrip("/")
    ql = QuanLyDb(url)
    # Hỏi một lần, dùng cho pl_moc (chỉ đọc), bản nhân bản và seed_import.py.
    if not os.environ.get("ODOO_PASSWORD"):
        os.environ["ODOO_PASSWORD"] = getpass.getpass("Mật khẩu Odoo của admin: ")
    thieu = module_thieu(url, args.src, os.environ["ODOO_PASSWORD"])
    print(f"Module {args.src} đang thiếu: {', '.join(thieu) if thieu else '(không thiếu)'}")

    ql.xoa(args.db)
    ql.nhan_ban(args.src, args.db)
    print(f"Đã nhân bản {args.src} thành {args.db}")
    bang = Bang()
    try:
        O2C(ket_noi(url, args.db), url, args.db, ngay_moc, args.policy_order).chay(bang, thieu)
    finally:
        bang.in_ra()
        if args.keep:
            print(f"\nGiữ database {args.db}")
        else:
            ql.xoa(args.db)
            print(f"\nĐã xóa {args.db}")
        if thieu:
            print(f"Module {args.src} đang thiếu: {', '.join(thieu)} (script không cài gì lên {args.src})")
    print("PASS: mua, bán, lập tuyến, giao, hóa đơn theo số lượng giao, thu tiền đều đúng")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        sys.exit(f"FAIL: {e}")
    except xmlrpc.client.Fault as e:
        sys.exit(f"Lỗi từ Odoo: {loi_odoo(e)}")
    except (ConnectionError, OSError) as e:
        sys.exit(f"Không kết nối được Odoo: {e}. Kiểm tra docker compose ps và --url")
