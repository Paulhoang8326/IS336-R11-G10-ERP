#!/usr/bin/env python3
"""Chạy thử trọn kịch bản seminar 3 trên bản nhân bản phanlam_seminar3_check, xong thì xóa bản đó.

PO 100 > Receipt > Storage > SO 30 > Pick > Pack > Delivery > kiểm kê 68. Sau mỗi bước in số liệu và
so với số mong đợi; sai số nào thì dừng, mã thoát khác 0.

    python scripts/seminar3/check_flow.py
    python scripts/seminar3/check_flow.py --keep   # giữ database check để xem lại
"""

import argparse
import sys
import xmlrpc.client

from chung import DB_CHECK, DB_SEMINAR, MA_O, MA_SP, URL, QuanLyDb, goi, ket_noi

SL_MUA = 100
SL_BAN = 30
SL_KIEM_KE = 68
GIA_VON = 600000
SO_LO = "SIM-2610-A"
HSD_UTC = "2027-04-29 17:00:00"  # 30/04/2027 00:00 giờ Việt Nam, Odoo lưu UTC


class KiemTra:
    def __init__(self, od, pid, o_id):
        self.od, self.pid, self.o_id = od, pid, o_id
        self.po_line = None
        self.so_line = None
        moi_nhat = od("account.move", "search", [], order="id desc", limit=1)
        self.am_cuoi = moi_nhat[0] if moi_nhat else 0

    def bao_cao(self, buoc, on_hand, reserved=None, gia_tri=None, but_toan=(), o_lo=None):
        """In số liệu sau một bước và so với mong đợi.

        but_toan: danh sách (TK nợ, TK có, số tiền) phải sinh ra đúng ở bước này.
        o_lo: {tên vị trí kết thúc bằng: số lượng} của lô SIM-2610-A.
        """
        od, pid = self.od, self.pid
        print(f"\n=== {buoc}")
        if self.po_line:
            r = od("purchase.order.line", "read", [self.po_line], fields=["product_qty", "qty_received"])[0]
            print(f"PO      ordered {r['product_qty']:g}, received {r['qty_received']:g}")
        if self.so_line:
            r = od("sale.order.line", "read", [self.so_line], fields=["product_uom_qty", "qty_delivered"])[0]
            print(f"SO      ordered {r['product_uom_qty']:g}, delivered {r['qty_delivered']:g}")

        sp = od("product.product", "read", [pid], fields=["qty_available", "free_qty"])[0]
        quant = od("stock.quant", "search_read", [("product_id", "=", pid), ("location_id.usage", "=", "internal"),
                                                  ("quantity", "!=", 0)],
                   fields=["location_id", "lot_id", "package_id", "quantity", "reserved_quantity"], order="id")
        giu = sum(q["reserved_quantity"] for q in quant)
        print(f"Tồn     on hand {sp['qty_available']:g}, reserved {giu:g}, available {sp['free_qty']:g}")
        for q in quant:
            lo = q["lot_id"][1] if q["lot_id"] else "-"
            kien = f", kiện {q['package_id'][1]}" if q["package_id"] else ""
            print(f"  quant {q['location_id'][1]} | lô {lo} | {q['quantity']:g} (giữ {q['reserved_quantity']:g}){kien}")

        svl = od("stock.valuation.layer", "search_read", [("product_id", "=", pid)], fields=["quantity", "value"])
        sl_svl = sum(x["quantity"] for x in svl)
        tri_gia = sum(x["value"] for x in svl)
        print(f"Giá trị {tri_gia:,.0f} đ ({sl_svl:g} đơn vị, {len(svl)} lớp định giá)")

        am = od("account.move", "search_read", [("id", ">", self.am_cuoi)], fields=["name", "ref", "state"], order="id")
        thuc_te = []
        for m in am:
            self.am_cuoi = max(self.am_cuoi, m["id"])
            print(f"  Bút toán mới {m['name']} [{m['state']}] {m['ref'] or ''}")
            no, co, tien = None, None, 0
            for l in od("account.move.line", "search_read", [("move_id", "=", m["id"])],
                        fields=["account_id", "debit", "credit"], order="id"):
                print(f"    {l['account_id'][1]}: Nợ {l['debit']:,.0f} Có {l['credit']:,.0f}")
                if l["debit"]:
                    no, tien = l["account_id"][1].split()[0], l["debit"]
                else:
                    co = l["account_id"][1].split()[0]
            thuc_te.append((no, co, round(tien)))
        if not am:
            print("  Không có bút toán mới")

        kiem(abs(sp["qty_available"] - on_hand) < 1e-6, f"on hand {sp['qty_available']:g}, mong đợi {on_hand:g}")
        if reserved is not None:
            kiem(abs(giu - reserved) < 1e-6, f"reserved {giu:g}, mong đợi {reserved:g}")
        if gia_tri is not None:
            kiem(abs(tri_gia - gia_tri) < 1e-6, f"giá trị {tri_gia:,.0f}, mong đợi {gia_tri:,.0f}")
        kiem(thuc_te == list(but_toan), f"bút toán {thuc_te}, mong đợi {list(but_toan)}")
        kiem(all(m["state"] == "posted" for m in am), "có bút toán chưa posted")
        if o_lo is not None:
            co_lo = {q["location_id"][1].rsplit("/", 1)[-1]: q["quantity"] for q in quant
                     if q["lot_id"] and q["lot_id"][1] == SO_LO}
            kiem(co_lo == o_lo, f"quant theo vị trí {co_lo}, mong đợi {o_lo}")
        print("OK")


def kiem(dung, thong_diep):
    if not dung:
        raise AssertionError(thong_diep)


def xac_nhan_phieu(od, pid, ma_loai, nguon):
    """Tìm phiếu kế tiếp của sản phẩm theo mã loại phiếu (IN, STOR, PICK, PACK, OUT)."""
    ds = od("stock.picking", "search_read", [("origin", "=", nguon), ("state", "not in", ["done", "cancel"]),
                                             ("picking_type_id.sequence_code", "=", ma_loai),
                                             ("move_ids.product_id", "=", pid)],
            fields=["name", "state", "location_id", "location_dest_id"], order="id")
    kiem(len(ds) == 1, f"cần đúng 1 phiếu {ma_loai} của {nguon}, có {len(ds)}")
    kiem(ds[0]["state"] == "assigned", f"phiếu {ds[0]['name']} đang {ds[0]['state']}, chưa Ready")
    print(f"\nPhiếu {ds[0]['name']}: {ds[0]['location_id'][1]} -> {ds[0]['location_dest_id'][1]}")
    return ds[0]["id"]


def kiem_validate(od, pk):
    kq = goi(od, "stock.picking", "button_validate", [pk])
    kiem(not isinstance(kq, dict), f"validate mở wizard {kq.get('res_model') if isinstance(kq, dict) else ''}")
    tt = od("stock.picking", "read", [pk], fields=["name", "state"])[0]
    kiem(tt["state"] == "done", f"{tt['name']} đang {tt['state']}")


def chay(od):
    sp = od("product.product", "search_read", [("default_code", "=", MA_SP)], fields=["id", "qty_available"])
    if not sp:
        sys.exit(f"Không có sản phẩm {MA_SP}: chạy make_seminar_db.py trước")
    pid = sp[0]["id"]
    kiem(sp[0]["qty_available"] == 0, f"sản phẩm phải tồn 0, đang {sp[0]['qty_available']:g}")
    o = od("stock.location", "search_read", [("barcode", "=", MA_O)], fields=["complete_name"])[0]
    kt = KiemTra(od, pid, o["id"])
    ten_o = MA_O

    # PO
    ncc = od("res.partner", "search", [("ref", "=", "NCC01"), ("name", "=", "Wilmar")])[0]
    po = od("purchase.order", "create", {"partner_id": ncc, "order_line": [
        (0, 0, {"product_id": pid, "product_qty": SL_MUA, "price_unit": GIA_VON})]})
    goi(od, "purchase.order", "button_confirm", [po])
    ten_po = od("purchase.order", "read", [po], fields=["name"])[0]["name"]
    kt.po_line = od("purchase.order.line", "search", [("order_id", "=", po)])[0]
    kt.bao_cao(f"1. Xác nhận {ten_po}: mua {SL_MUA}", on_hand=0, reserved=0, gia_tri=0)

    # Receipt
    pk = xac_nhan_phieu(od, pid, "IN", ten_po)
    dong = od("stock.move.line", "search", [("picking_id", "=", pk)])
    kiem(len(dong) == 1, f"phiếu nhập có {len(dong)} dòng")
    od("stock.move.line", "write", dong, {"lot_name": SO_LO, "expiration_date": HSD_UTC, "quantity": SL_MUA,
                                          "picked": True})
    kiem_validate(od, pk)
    lo = od("stock.lot", "search_read", [("name", "=", SO_LO), ("product_id", "=", pid)], fields=["expiration_date"])
    kiem(len(lo) == 1 and lo[0]["expiration_date"] == HSD_UTC, f"lô {SO_LO}: {lo}")
    print(f"Lô {SO_LO}, hạn dùng lưu UTC {lo[0]['expiration_date']} (30/04/2027 giờ Việt Nam)")
    # Phiếu Storage tự giữ hàng ở Input ngay khi Receipt xong, nên reserved = 100 tới hết bước Storage.
    kt.bao_cao("2. Receipt vào Input", on_hand=SL_MUA, reserved=SL_MUA, gia_tri=SL_MUA * GIA_VON,
               but_toan=[("1560", "1510", SL_MUA * GIA_VON)], o_lo={"Input": SL_MUA})

    # Storage
    pk = xac_nhan_phieu(od, pid, "STOR", ten_po)
    dich = od("stock.move.line", "search_read", [("picking_id", "=", pk)], fields=["location_dest_id"])
    print(f"Putaway gợi ý: {dich[0]['location_dest_id'][1]}")
    kiem(dich[0]["location_dest_id"][0] == kt.o_id, f"putaway ra {dich[0]['location_dest_id'][1]}")
    kiem_validate(od, pk)
    kt.bao_cao(f"3. Storage vào {ten_o}", on_hand=SL_MUA, reserved=0, gia_tri=SL_MUA * GIA_VON, o_lo={ten_o: SL_MUA})

    # SO
    nhan = od("res.partner.category", "search", [("name", "=", "Khách sạn")])
    kh = od("res.partner", "search", [("category_id", "in", nhan)], limit=1, order="id")[0]
    so = od("sale.order", "create", {"partner_id": kh, "order_line": [
        (0, 0, {"product_id": pid, "product_uom_qty": SL_BAN})]})
    goi(od, "sale.order", "action_confirm", [so])
    ten_so = od("sale.order", "read", [so], fields=["name"])[0]["name"]
    kt.so_line = od("sale.order.line", "search", [("order_id", "=", so)])[0]
    kt.bao_cao(f"4. Xác nhận {ten_so}: bán {SL_BAN}", on_hand=SL_MUA, reserved=SL_BAN, gia_tri=SL_MUA * GIA_VON,
               o_lo={ten_o: SL_MUA})

    # Pick
    pk = xac_nhan_phieu(od, pid, "PICK", ten_so)
    kiem_validate(od, pk)
    kt.bao_cao("5. Pick vào Packing Zone", on_hand=SL_MUA, reserved=SL_BAN, gia_tri=SL_MUA * GIA_VON,
               o_lo={ten_o: SL_MUA - SL_BAN, "Packing Zone": SL_BAN})

    # Pack: đóng kiện rồi chuyển ra Output
    pk = xac_nhan_phieu(od, pid, "PACK", ten_so)
    goi(od, "stock.picking", "action_put_in_pack", [pk])
    kiem_validate(od, pk)
    kt.bao_cao("6. Pack vào Output", on_hand=SL_MUA, reserved=SL_BAN, gia_tri=SL_MUA * GIA_VON,
               o_lo={ten_o: SL_MUA - SL_BAN, "Output": SL_BAN})

    # Delivery
    pk = xac_nhan_phieu(od, pid, "OUT", ten_so)
    kiem_validate(od, pk)
    con = SL_MUA - SL_BAN
    kt.bao_cao("7. Delivery cho khách", on_hand=con, reserved=0, gia_tri=con * GIA_VON,
               but_toan=[("1570", "1560", SL_BAN * GIA_VON)], o_lo={ten_o: con})

    # Kiểm kê
    q = od("stock.quant", "search", [("product_id", "=", pid), ("location_id", "=", kt.o_id)])
    kiem(len(q) == 1, f"có {len(q)} quant trong {ten_o}")
    od("stock.quant", "write", q, {"inventory_quantity": SL_KIEM_KE}, context={"inventory_mode": True})
    goi(od, "stock.quant", "action_apply_inventory", q)
    thieu = con - SL_KIEM_KE
    kt.bao_cao(f"8. Kiểm kê còn {SL_KIEM_KE}, Apply", on_hand=SL_KIEM_KE, reserved=0, gia_tri=SL_KIEM_KE * GIA_VON,
               but_toan=[("13811", "1560", thieu * GIA_VON)], o_lo={ten_o: SL_KIEM_KE})


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", default=URL)
    p.add_argument("--src", default=DB_SEMINAR)
    p.add_argument("--db", default=DB_CHECK)
    p.add_argument("--keep", action="store_true", help="không xóa database check")
    args = p.parse_args()
    url = args.url.rstrip("/")
    ql = QuanLyDb(url)
    ql.xoa(args.db)
    ql.nhan_ban(args.src, args.db)
    print(f"Đã nhân bản {args.src} thành {args.db}")
    try:
        chay(ket_noi(url, args.db))
    finally:
        if args.keep:
            print(f"\nGiữ database {args.db}")
        else:
            ql.xoa(args.db)
            print(f"\nĐã xóa {args.db}")
    print("PASS: toàn bộ kịch bản đúng số mong đợi")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        sys.exit(f"FAIL: {e}")
    except xmlrpc.client.Fault as e:
        dong = [d for d in e.faultString.strip().splitlines() if d.strip()]
        sys.exit(f"Lỗi từ Odoo: {dong[-1] if dong else e.faultString}")
    except (ConnectionError, OSError) as e:
        sys.exit(f"Không kết nối được Odoo: {e}. Kiểm tra docker compose ps và --url")
