#!/usr/bin/env python3
"""Chạy thử quy trình Procure-to-Pay trên bản nhân bản của database chính, xong thì xóa bản đó.

Nhân bản pl_moc thành pl_p2p_check rồi làm lần lượt (mọi đơn mua cùng một mã dầu ăn Wilmar, 10 thùng):

0. Module, seed: kiểm tra đã cài purchase_stock, account, product_expiry (pl_fefo_pick để seed_import.py ghi được
   hạn dùng tối thiểu của khách). In danh sách module pl_moc đang thiếu (chỉ đọc, không cài gì lên pl_moc), cài
   phần thiếu trên bản nhân bản. Chạy lại seed_import.py lên bản nhân bản: phải không còn cảnh báo, Purchase
   Settings phải để Bill Control = Received quantities, mọi sản phẩm seed có purchase_method = receive.
1. Ca chuẩn, đơn A: nhận đủ 10 thùng (lô, hạn dùng), Create Bill, post, Register Payment toàn bộ từ Bank.
   Kiểm tra: lô vào ô kệ của dãy Wilmar theo quy tắc cất hàng; hóa đơn 10 thùng, Paid; công nợ phải trả về 0.
2. Giao thiếu có backorder, đơn B: nhận 6, Create Backorder, lập hóa đơn; nhận nốt 4, lập hóa đơn lần 2.
   Kiểm tra: hóa đơn 6 thùng rồi 4 thùng; đúng 1 backorder còn 4 thùng.
3. Giao thiếu không backorder, đơn C: nhận 7, No Backorder, lập hóa đơn.
   Kiểm tra: hóa đơn 7 thùng; đơn không còn move mở.
4. Trả hàng lỗi, đơn A: Return 2 thùng trên phiếu nhập của bước 1, đúng lô; Create Bill trên đơn A để Odoo lập
   vendor credit note.
   Kiểm tra: tồn lô giảm 2 thùng; credit note 2 thùng post được; công nợ ròng = hóa đơn - credit note - đã trả.
5. Chưa nhận hàng, đơn D: xác nhận, chưa nhận, Create Bill.
   Kiểm tra: Odoo từ chối, không có hóa đơn nào sinh ra.

Cuối cùng in bảng từng bước PASS/FAIL kèm số chứng từ để đối chiếu trên giao diện khi dùng --keep.
Sai điều nào thì in FAIL, mã thoát khác 0.

    python scripts/check_p2p.py
    python scripts/check_p2p.py --keep              # giữ database check để xem trên giao diện
    python scripts/check_p2p.py --method-purchase   # thử âm: purchase_method = purchase, phải FAIL ở bước 2

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

import check_o2c  # noqa: E402
from chung import DB_CHINH, URL, Odoo, QuanLyDb, cai_module, goi, ket_noi, kiem  # noqa: E402
from seed_import import GIO_VN, doc_csv, so  # noqa: E402

DB_CHECK = "pl_p2p_check"
MODULES = ["purchase_stock", "account", "product_expiry", "pl_fefo_pick"]
SEED = ROOT / "seed" / "demo"
NCC = "NCC01"  # Wilmar
DAY = "PL-A"   # dãy kệ của Wilmar
THUNG_DAT = 10
NHAN_B, NHAN_C, TRA_A = 6, 7, 2
LO = {"A": "LP2PA", "B": "LP2PB", "B2": "LP2PB2", "C": "LP2PC"}


class Bang(check_o2c.Bang):
    BUOC = ["Module, seed_import", "Ca chuẩn: nhận, hóa đơn, trả tiền", "Giao thiếu, có backorder",
            "Giao thiếu, không backorder", "Trả hàng lỗi, credit note", "Chưa nhận thì chưa lập hóa đơn"]


class P2P:
    def __init__(self, od, url, db, ngay_moc, theo_dat):
        self.od, self.url, self.db, self.ngay_moc, self.theo_dat = od, url, db, ngay_moc, theo_dat
        self.don = {}    # A..D -> dict(po_id, po, nhap_id, nhap, ...)

    # ------------------------------------------------------------------ bước 0

    def buoc_0(self, thieu_nguon):
        od = self.od
        vua_cai = cai_module(od, *MODULES)
        print(f"Đã cài trên {self.db}: {', '.join(vua_cai) if vua_cai else '(không cần cài thêm)'}")
        kiem(set(vua_cai) <= set(thieu_nguon), f"{self.db} phải cài {vua_cai}, khác với phần nguồn thiếu")

        kq = subprocess.run([sys.executable, str(ROOT / "scripts" / "seed_import.py"), "--url", self.url,
                             "--db", self.db], capture_output=True, text=True, encoding="utf-8", env=dict(os.environ))
        kiem(kq.returncode == 0, f"seed_import.py lỗi:\n{kq.stdout[-800:]}\n{kq.stderr[-800:]}")
        canh_bao = [d.strip() for d in kq.stdout.splitlines() if "CẢNH BÁO" in d]
        kiem(not canh_bao and "Cảnh báo: 0" in kq.stdout, "seed_import.py còn cảnh báo: " + "; ".join(canh_bao))
        for d in kq.stdout.splitlines():
            if d.strip().startswith(("Đã bật", "Cài đặt ", "Sản phẩm ")):
                print(f"  seed_import: {d.strip()}")

        sid = od("res.config.settings", "create", {})
        bc = od("res.config.settings", "read", [sid], fields=["default_purchase_method"])[0]["default_purchase_method"]
        kiem(bc == "receive", f"Purchase Settings > Bill Control đang {bc}, cần receive")
        muon = len(doc_csv(SEED / "san_pham.csv"))
        dem = self.dem_purchase_method()
        kiem(dem == {"receive": muon}, f"purchase_method của sản phẩm seed: {dem}, cần receive cho cả {muon}")
        print(f"  Bill Control: {bc}; sản phẩm seed: {dem}")
        if self.theo_dat:
            ids = od("product.template", "search", [("default_code", "=like", "NCC%")])
            od("product.template", "write", ids, {"purchase_method": "purchase"})
            print(f"  --method-purchase: ghi purchase_method = purchase cho {len(ids)} sản phẩm")
            dem = self.dem_purchase_method()

        ncc = od.search_read("res.partner", [("ref", "=", NCC), ("parent_id", "=", False)],
                             ["name", "property_supplier_payment_term_id"])
        kiem(ncc, f"không có nhà cung cấp {NCC}")
        self.ncc = ncc[0]
        self.sp = self.chon_san_pham()
        kho = od.search_read("stock.warehouse", [("code", "=", "PL")], ["lot_stock_id"])[0]
        self.ton = kho["lot_stock_id"][0]
        self.no_dau = self.cong_no()
        print(f"Sản phẩm: {self.sp['display_name']}, thùng {self.sp['n']}, hạn dùng {self.sp['expiration_time']} ngày; "
              f"công nợ phải trả {self.ncc['name']} đầu kỳ {self.no_dau:,.0f} đ")
        return f"cài {', '.join(vua_cai) or 'không'}; seed_import 0 cảnh báo; Bill Control {bc}; sản phẩm {dem}"

    def dem_purchase_method(self):
        dem = {}
        for r in self.od.search_read("product.template", [("default_code", "=like", "NCC%")], ["purchase_method"]):
            dem[r["purchase_method"]] = dem.get(r["purchase_method"], 0) + 1
        return dem

    def chon_san_pham(self):
        """Mã dầu ăn Wilmar đầu tiên của seed có quy cách thùng."""
        od = self.od
        for r in doc_csv(SEED / "san_pham.csv"):
            n = so(r["so_dvt_moi_thung"], True) or 1
            if r["ma_ncc"] == NCC and r["nhom_hang"] == "Dầu ăn" and "dầu" in r["ten"].lower() and n > 1:
                sp = od.search_read("product.product", [("default_code", "=", r["ma_sp"])],
                                    ["default_code", "display_name", "expiration_time"])
                kiem(sp, f"không có sản phẩm {r['ma_sp']}")
                thung = od.search_read("product.packaging", [("product_id", "=", sp[0]["id"]), ("qty", "=", n)], ["qty"])
                kiem(thung, f"{r['ma_sp']} không có quy cách thùng {n}")
                return dict(sp[0], n=n, thung_id=thung[0]["id"], gia=so(r["gia_nhap"], True))
        raise AssertionError(f"seed không có mã dầu ăn {NCC} theo thùng")

    # ------------------------------------------------------------------ thao tác chung

    def cong_no(self, move_ids=None):
        """Công nợ phải trả NCC trên sổ: Có trừ Nợ của tài khoản phải trả, bút toán đã post. Dương là mình còn nợ."""
        dk = [("partner_id", "=", self.ncc["id"]), ("account_id.account_type", "=", "liability_payable"),
              ("parent_state", "=", "posted")]
        if move_ids is not None:
            dk.append(("move_id", "in", move_ids))
        return 0 - sum(l["balance"] for l in self.od.search_read("account.move.line", dk, ["balance"]))

    def ton_lo(self, lo):
        return self.od.search_read("stock.quant", [("lot_id.name", "=", lo), ("product_id", "=", self.sp["id"]),
                                                   ("location_id.usage", "=", "internal"), ("quantity", "!=", 0)],
                                   ["location_id", "quantity"])

    def dat_mua(self, ten):
        """Đơn mua THUNG_DAT thùng, xác nhận; trả về dict của đơn kèm phiếu nhập."""
        od, sp = self.od, self.sp
        # Hạn thanh toán: trên giao diện onchange_partner_id lấy từ nhà cung cấp, qua XML-RPC phải tự ghi.
        han = self.ncc["property_supplier_payment_term_id"]
        po = od("purchase.order", "create", {
            "partner_id": self.ncc["id"], "payment_term_id": han[0] if han else False,
            "order_line": [(0, 0, {"product_id": sp["id"], "product_qty": THUNG_DAT * sp["n"],
                                   "product_packaging_id": sp["thung_id"]})],
        })
        goi(od, "purchase.order", "button_confirm", [po])
        r = od("purchase.order", "read", [po], fields=["name", "state", "picking_ids"])[0]
        kiem(r["state"] == "purchase" and len(r["picking_ids"]) == 1,
             f"{r['name']}: {r['state']}, {len(r['picking_ids'])} phiếu nhập")
        nhap = od("stock.picking", "read", r["picking_ids"], fields=["name"])[0]
        self.don[ten] = dict(po_id=po, po=r["name"], nhap_id=nhap["id"], nhap=nhap["name"], bill=[])
        return self.don[ten]

    def nhan(self, pick_id, lo, thung, backorder=None):
        """Nhận `thung` thùng vào lô `lo` rồi Validate. Nhận thiếu thì Odoo hỏi backorder: backorder=True là Create
        Backorder, False là No Backorder, None là phải nhận đủ. Kiểm tra lô nằm trong ô kệ của dãy NCC."""
        od, sp = self.od, self.sp
        # Hạn dùng của lô mới: đủ thời hạn tính từ ngày mốc, 00:00 giờ Việt Nam.
        han = dt.datetime.combine(self.ngay_moc + dt.timedelta(days=sp["expiration_time"]), dt.time()) \
            - dt.timedelta(hours=GIO_VN)
        mls = od.search_read("stock.move.line", [("picking_id", "=", pick_id)], ["quantity"])
        kiem(len(mls) == 1, f"phiếu nhập {pick_id} có {len(mls)} dòng chi tiết")
        od("stock.move.line", "write", [mls[0]["id"]], {
            "lot_name": lo, "expiration_date": han.strftime("%Y-%m-%d %H:%M:%S"),
            "quantity": thung * sp["n"], "picked": True})
        kq = goi(od, "stock.picking", "button_validate", [pick_id])
        hoi = isinstance(kq, dict) and kq.get("res_model") == "stock.backorder.confirmation"
        kiem(hoi == (backorder is not None),
             f"phiếu {pick_id} nhận {thung} thùng: Odoo {'có' if hoi else 'không'} hỏi backorder")
        if hoi:
            ctx = kq.get("context", {})
            wiz = od("stock.backorder.confirmation", "create", {"pick_ids": [(4, pick_id)]}, context=ctx)
            goi(od, "stock.backorder.confirmation", "process" if backorder else "process_cancel_backorder", [wiz],
                context=ctx)
        p = od("stock.picking", "read", [pick_id], fields=["name", "state"])[0]
        kiem(p["state"] == "done", f"phiếu nhập {p['name']} đang {p['state']}")

        day = od.search_read("stock.location", [("barcode", "=", DAY)], ["complete_name"])
        kiem(day, f"không có dãy {DAY}")
        ql = od.search_read("stock.putaway.rule", [("product_id", "=", sp["id"]), ("location_in_id", "=", self.ton)],
                            ["location_out_id"])
        kiem(ql and ql[0]["location_out_id"][0] == day[0]["id"],
             f"quy tắc cất hàng của {sp['default_code']} không trỏ vào {day[0]['complete_name']}: {ql}")
        o_ke = od("stock.location", "search", [("id", "child_of", day[0]["id"]), ("id", "!=", day[0]["id"])])
        quant = self.ton_lo(lo)
        kiem(sum(q["quantity"] for q in quant) == thung * sp["n"],
             f"lô {lo}: tồn {[(q['location_id'][1], q['quantity']) for q in quant]}, cần {thung * sp['n']}")
        for q in quant:
            kiem(q["location_id"][0] in o_ke,
                 f"lô {lo} nằm ở {q['location_id'][1]}, không phải ô của {day[0]['complete_name']}")
        noi = ", ".join(sorted({q["location_id"][1] for q in quant}))
        lot = od.search_read("stock.lot", [("name", "=", lo), ("product_id", "=", sp["id"])], ["expiration_date"])
        kiem(lot[0]["expiration_date"] == han.strftime("%Y-%m-%d %H:%M:%S"),
             f"lô {lo}: hạn dùng {lot[0]['expiration_date']}, cần {han}")
        print(f"  {p['name']}: nhận {thung} thùng lô {lo}, hạn {han:%d/%m/%Y} UTC, vào {noi}")
        return noi

    def create_bill(self, don):
        """Nút Create Bill trên đơn mua. Trả về id các chứng từ kế toán mới sinh (nháp)."""
        od = self.od
        cu = set(od("purchase.order", "read", [don["po_id"]], fields=["invoice_ids"])[0]["invoice_ids"])
        goi(od, "purchase.order", "action_create_invoice", [don["po_id"]])
        return sorted(set(od("purchase.order", "read", [don["po_id"]], fields=["invoice_ids"])[0]["invoice_ids"]) - cu)

    def lap_bill(self, ten, loai, thung):
        """Create Bill, ghi Bill Date hôm nay, post; kiểm loại chứng từ, số lượng và tiền hàng theo giá nhập của seed."""
        od, sp, don = self.od, self.sp, self.don[ten]
        moi = self.create_bill(don)
        kiem(len(moi) == 1, f"{don['po']}: Create Bill tạo {len(moi)} chứng từ")
        # Hóa đơn mua bắt buộc có Bill Date mới post được, Odoo không tự điền.
        od("account.move", "write", moi, {"invoice_date": dt.date.today().isoformat()})
        goi(od, "account.move", "action_post", moi)
        hd = od("account.move", "read", moi, fields=["name", "state", "move_type", "amount_untaxed", "amount_total",
                                                     "invoice_date", "invoice_date_due"])[0]
        sl = sum(l["quantity"] for l in od.search_read(
            "account.move.line", [("move_id", "=", moi[0]), ("display_type", "=", "product")], ["quantity"]))
        line = od.search_read("purchase.order.line", [("order_id", "=", don["po_id"])],
                              ["product_qty", "qty_received", "qty_invoiced"])[0]
        hd["thung"] = sl / sp["n"]
        print(f"  {don['po']}: {hd['name']} ({hd['move_type']}) {hd['state']}, {hd['thung']:g} thùng, "
              f"{hd['amount_total']:,.0f} đ; đơn đặt {line['product_qty'] / sp['n']:g}, "
              f"đã nhận {line['qty_received'] / sp['n']:g}, đã lập hóa đơn {line['qty_invoiced'] / sp['n']:g} thùng")
        kiem(hd["state"] == "posted" and hd["move_type"] == loai,
             f"{hd['name']}: {hd['move_type']} {hd['state']}, cần {loai} posted")
        kiem(sl == thung * sp["n"],
             f"{hd['name']} ({don['po']}) lập {hd['thung']:g} thùng, cần {thung} thùng (đặt "
             f"{line['product_qty'] / sp['n']:g}, đã nhận {line['qty_received'] / sp['n']:g}): "
             f"hóa đơn không theo số lượng thực nhận")
        kiem(line["qty_invoiced"] == line["qty_received"],
             f"{don['po']}: đã lập hóa đơn {line['qty_invoiced']}, đã nhận {line['qty_received']}")
        kiem(hd["amount_untaxed"] == sl * sp["gia"],
             f"{hd['name']}: tiền hàng {hd['amount_untaxed']:,.0f}, cần {sl:g} x {sp['gia']:,} đ")
        return hd

    # ------------------------------------------------------------------ bước 1

    def buoc_1(self):
        od = self.od
        a = self.dat_mua("A")
        noi = self.nhan(a["nhap_id"], LO["A"], THUNG_DAT)
        hd = self.lap_bill("A", "in_invoice", THUNG_DAT)
        a["bill"].append(hd)

        han = self.ncc["property_supplier_payment_term_id"]
        kiem(han, f"{self.ncc['name']} không có hạn thanh toán")
        ngay = od.search_read("account.payment.term.line", [("payment_id", "=", han[0])], ["nb_days"])
        den_han = dt.date.fromisoformat(hd["invoice_date"]) + dt.timedelta(days=ngay[0]["nb_days"])
        kiem(hd["invoice_date_due"] == den_han.isoformat(),
             f"{hd['name']}: đến hạn {hd['invoice_date_due']}, cần {den_han} ({han[1]})")
        kiem(self.cong_no() - self.no_dau == hd["amount_total"],
             f"công nợ sau khi post {hd['name']}: {self.cong_no() - self.no_dau}, cần {hd['amount_total']}")

        so_quy = od.search_read("account.journal", [("type", "=", "bank")], ["name"], order="id")
        kiem(so_quy, "không có sổ ngân hàng")
        ctx = {"active_model": "account.move", "active_ids": [hd["id"]]}
        wiz = od("account.payment.register", "create", {"journal_id": so_quy[0]["id"]}, context=ctx)
        goi(od, "account.payment.register", "action_create_payments", [wiz], context=ctx)
        tt = od.search_read("account.payment", [("partner_id", "=", self.ncc["id"]), ("payment_type", "=", "outbound")],
                            ["name", "amount", "state", "move_id"], order="id desc")
        kiem(tt and tt[0]["move_id"], f"không có payment kèm bút toán cho {hd['name']}")
        a["tt"] = tt = tt[0]
        hd2 = od("account.move", "read", [hd["id"]], fields=["payment_state", "amount_residual"])[0]
        con = self.cong_no([hd["id"], tt["move_id"][0]])
        print(f"  {tt['name']}: trả {tt['amount']:,.0f} đ từ {so_quy[0]['name']}; {hd['name']} {hd2['payment_state']}, "
              f"còn nợ {hd2['amount_residual']:,.0f}; công nợ phải trả {self.cong_no():,.0f} đ")
        kiem(tt["amount"] == hd["amount_total"], f"{tt['name']} trả {tt['amount']}, hóa đơn {hd['amount_total']}")
        kiem(hd2["payment_state"] == "paid" and hd2["amount_residual"] == 0,
             f"{hd['name']}: payment_state {hd2['payment_state']}, còn nợ {hd2['amount_residual']}")
        kiem(con == 0 and self.cong_no() == self.no_dau,
             f"công nợ của {a['po']} còn {con}, của {self.ncc['name']} {self.cong_no()} (đầu kỳ {self.no_dau})")
        return f"{a['po']}, {a['nhap']}: lô {LO['A']} vào {noi}; {hd['name']} {hd['thung']:g} thùng paid; {tt['name']}"

    # ------------------------------------------------------------------ bước 2, 3

    def move_mo(self, don):
        return self.od.search_read("stock.move", [("purchase_line_id.order_id", "=", don["po_id"]),
                                                  ("state", "not in", ["done", "cancel"])],
                                   ["picking_id", "product_uom_qty"])

    def buoc_2(self):
        od, n = self.od, self.sp["n"]
        thieu = THUNG_DAT - NHAN_B
        b = self.dat_mua("B")
        self.nhan(b["nhap_id"], LO["B"], NHAN_B, backorder=True)
        bo = od.search_read("stock.picking", [("backorder_id", "=", b["nhap_id"])], ["name", "state"])
        kiem(len(bo) == 1 and bo[0]["state"] not in ("done", "cancel"), f"{b['nhap']}: backorder {bo}, cần đúng 1")
        mo = self.move_mo(b)
        kiem(sum(m["product_uom_qty"] for m in mo) == thieu * n and {m["picking_id"][0] for m in mo} == {bo[0]["id"]},
             f"backorder {bo[0]['name']}: move mở {mo}, cần {thieu} thùng")
        print(f"  {bo[0]['name']}: backorder {bo[0]['state']}, còn {thieu} thùng")
        hd1 = self.lap_bill("B", "in_invoice", NHAN_B)
        self.nhan(bo[0]["id"], LO["B2"], thieu)
        hd2 = self.lap_bill("B", "in_invoice", thieu)
        tong = hd1["thung"] + hd2["thung"]
        kiem(tong == THUNG_DAT and not self.move_mo(b), f"{b['po']}: hai hóa đơn {tong:g} thùng, move mở {self.move_mo(b)}")
        return (f"{b['po']}, {b['nhap']} nhận {NHAN_B}, {hd1['name']} {hd1['thung']:g} thùng; backorder "
                f"{bo[0]['name']} nhận {thieu}, {hd2['name']} {hd2['thung']:g} thùng; tổng {tong:g}")

    def buoc_3(self):
        od = self.od
        c = self.dat_mua("C")
        self.nhan(c["nhap_id"], LO["C"], NHAN_C, backorder=False)
        bo = od.search_read("stock.picking", [("backorder_id", "=", c["nhap_id"])], ["name", "state"])
        kiem(not bo, f"{c['nhap']} không được có backorder: {bo}")
        hd = self.lap_bill("C", "in_invoice", NHAN_C)
        kiem(not self.move_mo(c), f"{c['po']} còn move mở: {self.move_mo(c)}")
        tt = od("purchase.order", "read", [c["po_id"]], fields=["invoice_status"])[0]["invoice_status"]
        kiem(tt == "invoiced", f"{c['po']}: Billing Status {tt}, cần invoiced (không chờ phần đã hủy)")
        print(f"  {c['po']}: không backorder, không move mở, Billing Status {tt}")
        return f"{c['po']}, {c['nhap']} nhận {NHAN_C}, bỏ {THUNG_DAT - NHAN_C}; {hd['name']} {hd['thung']:g} thùng"

    # ------------------------------------------------------------------ bước 4

    def buoc_4(self):
        od, n, a = self.od, self.sp["n"], self.don["A"]
        hd, tt = a["bill"][0], a["tt"]
        truoc, no_truoc = sum(q["quantity"] for q in self.ton_lo(LO["A"])), self.cong_no()

        # Nút Return trên phiếu nhập: Odoo mặc định số lượng 0, to_refund (Update quantities on SO/PO) bật.
        ctx = {"active_model": "stock.picking", "active_id": a["nhap_id"], "active_ids": [a["nhap_id"]]}
        wiz = od("stock.return.picking", "create", {}, context=ctx)
        dong = od.search_read("stock.return.picking.line", [("wizard_id", "=", wiz)], ["quantity", "to_refund"])
        kiem(len(dong) == 1 and dong[0]["to_refund"], f"màn hình Return của {a['nhap']}: {dong}")
        od("stock.return.picking.line", "write", [dong[0]["id"]], {"quantity": TRA_A * n})
        tra = goi(od, "stock.return.picking", "action_create_returns", [wiz], context=ctx)["res_id"]
        mls = od.search_read("stock.move.line", [("picking_id", "=", tra)], ["lot_id", "quantity", "location_id",
                                                                           "location_dest_id"])
        kiem(mls and sum(m["quantity"] for m in mls) == TRA_A * n and {m["lot_id"][1] for m in mls} == {LO["A"]},
             f"phiếu trả giữ {[(m['lot_id'], m['quantity']) for m in mls]}, cần {TRA_A * n} của lô {LO['A']}")
        od("stock.move.line", "write", [m["id"] for m in mls], {"picked": True})
        goi(od, "stock.picking", "button_validate", [tra])
        p = od("stock.picking", "read", [tra], fields=["name", "state", "location_dest_id"])[0]
        dich = od("stock.location", "read", [p["location_dest_id"][0]], fields=["usage"])[0]["usage"]
        kiem(p["state"] == "done" and dich == "supplier", f"phiếu trả {p['name']}: {p['state']}, đến {dich}")
        sau = sum(q["quantity"] for q in self.ton_lo(LO["A"]))
        print(f"  {p['name']}: trả {TRA_A} thùng lô {LO['A']} từ {mls[0]['location_id'][1]} về "
              f"{p['location_dest_id'][1]}; tồn lô {truoc / n:g} -> {sau / n:g} thùng")
        kiem(truoc - sau == TRA_A * n, f"tồn lô {LO['A']} {truoc} -> {sau}, cần giảm {TRA_A * n}")

        # qty_to_invoice = 8 đã nhận - 10 đã lập = -2 thùng: Create Bill trên đơn mua ra vendor credit note.
        line = od.search_read("purchase.order.line", [("order_id", "=", a["po_id"])], ["qty_received", "qty_to_invoice"])[0]
        st = od("purchase.order", "read", [a["po_id"]], fields=["invoice_status"])[0]["invoice_status"]
        print(f"  {a['po']}: đã nhận {line['qty_received'] / n:g}, chờ lập hóa đơn {line['qty_to_invoice'] / n:g} thùng, "
              f"Billing Status {st}")
        kiem(line["qty_to_invoice"] == -TRA_A * n and st == "to invoice",
             f"{a['po']}: chờ lập hóa đơn {line['qty_to_invoice']}, {st}")
        cn = self.lap_bill("A", "in_refund", TRA_A)
        rong = self.cong_no([hd["id"], tt["move_id"][0], cn["id"]])
        can = hd["amount_total"] - cn["amount_total"] - tt["amount"]
        print(f"  Công nợ ròng của {a['po']}: {hd['amount_total']:,.0f} - {cn['amount_total']:,.0f} - "
              f"{tt['amount']:,.0f} = {can:,.0f} đ, trên sổ {rong:,.0f} đ")
        kiem(rong == can, f"công nợ ròng {rong}, cần {can}")
        kiem(self.cong_no() - no_truoc == -cn["amount_total"],
             f"công nợ {self.ncc['name']} đổi {self.cong_no() - no_truoc}, cần {-cn['amount_total']}")
        return f"{p['name']} trả {TRA_A} thùng lô {LO['A']}; {cn['name']} {cn['thung']:g} thùng; công nợ ròng {rong:,.0f} đ"

    # ------------------------------------------------------------------ bước 5

    def buoc_5(self):
        od = self.od
        d = self.dat_mua("D")
        loi = None
        try:
            moi = self.create_bill(d)
        except xmlrpc.client.Fault as e:
            loi = e
        kiem(loi is not None and loi.faultCode == 2,
             f"Create Bill khi chưa nhận hàng của {d['po']} phải bị Odoo từ chối, được: {loi or moi}")
        con = od("purchase.order", "read", [d["po_id"]], fields=["invoice_ids", "invoice_status"])[0]
        kiem(not con["invoice_ids"] and con["invoice_status"] == "no",
             f"{d['po']}: hóa đơn {con['invoice_ids']}, Billing Status {con['invoice_status']}")
        print(f"  {d['po']}, {d['nhap']} chưa nhận: Create Bill bị từ chối: {loi.faultString.strip()}")
        return f"{d['po']}, {d['nhap']} chưa nhận: Odoo từ chối Create Bill"

    def chay(self, bang, thieu_nguon):
        bang.chay(0, self.buoc_0, thieu_nguon)
        for so_buoc in range(1, 6):
            bang.chay(so_buoc, getattr(self, f"buoc_{so_buoc}"))


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
    p.add_argument("--method-purchase", action="store_true",
                   help="thử âm: ghi purchase_method = purchase cho sản phẩm trên bản nhân bản, phải FAIL ở bước 2")
    args = p.parse_args()
    # --db bị xóa trước và sau khi chạy: không cho trỏ vào database chính hay database nguồn.
    kiem(args.db not in (args.src, DB_CHINH), f"--db phải khác --src và {DB_CHINH}")

    ngay_moc = dt.date.fromisoformat(doc_csv(SEED / "don_ban.csv")[0]["ngay"])
    print(f"Ngày mốc {ngay_moc:%d/%m/%Y}")

    url = args.url.rstrip("/")
    ql = QuanLyDb(url)
    # Hỏi một lần, dùng cho database nguồn (chỉ đọc), bản nhân bản và seed_import.py.
    if not os.environ.get("ODOO_PASSWORD"):
        os.environ["ODOO_PASSWORD"] = getpass.getpass("Mật khẩu Odoo của admin: ")
    thieu = module_thieu(url, args.src, os.environ["ODOO_PASSWORD"])
    print(f"Module {args.src} đang thiếu: {', '.join(thieu) if thieu else '(không thiếu)'}")

    ql.xoa(args.db)
    ql.nhan_ban(args.src, args.db)
    print(f"Đã nhân bản {args.src} thành {args.db}")
    bang = Bang()
    try:
        P2P(ket_noi(url, args.db), url, args.db, ngay_moc, args.method_purchase).chay(bang, thieu)
    finally:
        bang.in_ra()
        if args.keep:
            print(f"\nGiữ database {args.db}")
        else:
            ql.xoa(args.db)
            print(f"\nĐã xóa {args.db}")
    print("PASS: nhận hàng, hóa đơn theo số thực nhận, trả tiền, giao thiếu, trả hàng đều đúng")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        sys.exit(f"FAIL: {e}")
    except xmlrpc.client.Fault as e:
        sys.exit(f"Lỗi từ Odoo: {check_o2c.loi_odoo(e)}")
    except (ConnectionError, OSError) as e:
        sys.exit(f"Không kết nối được Odoo: {e}. Kiểm tra docker compose ps và --url")
