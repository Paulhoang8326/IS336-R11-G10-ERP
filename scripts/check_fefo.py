#!/usr/bin/env python3
"""Chạy thử module pl_fefo_pick trên bản nhân bản của database chính, xong thì xóa bản đó.

Nhân bản pl_moc thành pl_fefo_check > cài pl_fefo_pick > chạy lại seed_import.py để ghi hạn dùng tối thiểu
của khách > lấy mã NCC02 có đúng 3 lô (hết hạn sau ngày mốc 7, 11, 17 tháng) > tạo đơn mới cùng mã, cùng
ngày giao cho 4 khách: tạp hóa (30%), khách sạn (60%), căn tin KCN (60%), minimart (50%, đặt quá tồn các
lô đạt) > chọn tay lô 7 tháng cho phiếu minimart rồi Validate > một phiếu nhập và một phiếu nội bộ cùng mã >
hủy các đơn thử > xác nhận 81 đơn của ngày mốc, giữ hàng.

Kiểm tra: seed_import không còn cảnh báo; tạp hóa giữ lô 7 tháng; khách sạn, căn tin, minimart không giữ
lô 7 tháng mà giữ lô 11 tháng; phiếu minimart chỉ giữ một phần, không lỗi; Validate với lô 7 tháng chọn
tay ra UserError; phiếu nhập, phiếu nội bộ chạy bình thường (phiếu nội bộ vẫn giữ lô 7 tháng theo FEFO);
80 đơn của ngày mốc (trừ đơn 081) đều Ready đủ hàng, không đơn nào giữ lô cận date, lô hết hạn hay lô
dưới mức của khách. Sai điều nào thì dừng, mã thoát khác 0.

Ngày giao dự kiến của đơn là Delivery Date (commitment_date), đặt 08:00 ngày mốc. Không đặt thì Odoo lấy
lúc xác nhận đơn, và hạn dùng còn lại sẽ tính theo hôm nay chứ không theo ngày mốc.

    python scripts/check_fefo.py
    python scripts/check_fefo.py --keep              # giữ database check để xem trên giao diện
    python scripts/check_fefo.py --src pl_seed_fefo  # nhân bản từ database khác

Mật khẩu như scripts/seminar3: admin lấy từ ODOO_PASSWORD, master từ ODOO_MASTER_PASSWORD hoặc
config/odoo.conf.
"""

import argparse
import datetime as dt
import math
import os
import subprocess
import sys
import xmlrpc.client
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "seminar3"))

from chung import DB_CHINH, URL, QuanLyDb, goi, ket_noi  # noqa: E402
from gen_seed import NCC_3_LO, THANG_3_LO  # noqa: E402
from seed_import import GIO_DAT_HANG, GIO_VN, doc_csv  # noqa: E402

DB_CHECK = "pl_fefo_check"
MODULE = "pl_fefo_pick"
SEED = ROOT / "seed" / "demo"
NHOM_THU = ["Tạp hóa", "Khách sạn", "Căn tin KCN", "Minimart"]  # minimart cuối: đặt quá tồn các lô đạt
THUNG_DAT = 2
THUNG_THUA = 5
LOT_THU = "LFEFOCHECK"


def kiem(dung, thong_diep):
    if not dung:
        raise AssertionError(thong_diep)


def utc(ngay, gio):
    """Giờ Việt Nam của ngày `ngay` đổi sang chuỗi UTC như Odoo lưu."""
    return (dt.datetime.combine(ngay, dt.time(gio)) - dt.timedelta(hours=GIO_VN)).strftime("%Y-%m-%d %H:%M:%S")


def dt_odoo(s):
    return dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S") if s else None


def con_pct(han, giao, ngay_han):
    return (han - giao).total_seconds() / 86400 / ngay_han * 100


def loi_odoo(e):
    dong = [d for d in e.faultString.strip().splitlines() if d.strip()]
    return "\n".join(dong[-6:])


def cai_module(od):
    goi(od, "ir.module.module", "update_list")
    m = od.search_read("ir.module.module", [("name", "=", MODULE)], ["state"])
    kiem(m, f"Odoo không thấy module {MODULE}: kiểm tra addons_path")
    if m[0]["state"] != "installed":
        goi(od, "ir.module.module", "button_immediate_install", [m[0]["id"]])
    m = od.search_read("ir.module.module", [("name", "=", MODULE)], ["state", "latest_version"])[0]
    kiem(m["state"] == "installed", f"{MODULE} đang {m['state']}")
    print(f"Đã cài {MODULE} {m['latest_version']}")


def nap_lai_khach(url, db):
    """Chạy lại seed_import.py (không --orders) để ghi pl_min_shelf_life_pct; phải không còn cảnh báo."""
    env = dict(os.environ, ODOO_PASSWORD=os.environ.get("ODOO_PASSWORD", ""))
    kq = subprocess.run([sys.executable, str(ROOT / "scripts" / "seed_import.py"), "--url", url, "--db", db],
                        capture_output=True, text=True, encoding="utf-8", env=env)
    kiem(kq.returncode == 0, f"seed_import.py lỗi:\n{kq.stdout[-800:]}\n{kq.stderr[-800:]}")
    dong = [d for d in kq.stdout.splitlines() if "Khách hàng" in d and d.split()[-1].isdigit()]
    canh_bao = [d.strip() for d in kq.stdout.splitlines() if "CẢNH BÁO" in d]
    kiem("pl_min_shelf_life_pct" not in kq.stdout, "seed_import.py vẫn cảnh báo pl_min_shelf_life_pct")
    kiem(not canh_bao and "Cảnh báo: 0" in kq.stdout, "seed_import.py còn cảnh báo: " + "; ".join(canh_bao))
    print(f"Chạy lại seed_import.py: {dong[-1].strip() if dong else ''}, Cảnh báo: 0")


def kiem_muc_khach(od, khach):
    muc = {r["ma_kh"]: int(r["han_dung_toi_thieu_pct"] or 0) for r in khach}
    kh = od.search_read("res.partner", [("ref", "in", list(muc)), ("parent_id", "=", False)],
                        ["ref", "pl_min_shelf_life_pct"])
    sai = [k["ref"] for k in kh if k["pl_min_shelf_life_pct"] != muc[k["ref"]]]
    kiem(len(kh) == len(muc) and not sai, f"{len(sai)} khách sai mức hạn dùng tối thiểu: {sai[:5]}")
    theo_nhom = {}
    for r in khach:
        theo_nhom.setdefault(r["nhom_khach"], set()).add(muc[r["ma_kh"]])
    print("Mức hạn dùng tối thiểu: " + ", ".join(f"{n} {'/'.join(map(str, sorted(m)))}%"
                                                 for n, m in theo_nhom.items()))


def ma_3_lo(ton_kho, ngay_moc):
    lech = sorted(t * 30 for t in THANG_3_LO)
    lo = defaultdict(list)
    for r in ton_kho:
        lo[r["ma_sp"]].append(r)
    for ma in sorted(lo):
        ds = lo[ma]
        if ma.startswith(NCC_3_LO) and all(r["han_dung"] for r in ds) and \
                sorted((dt.date.fromisoformat(r["han_dung"]) - ngay_moc).days for r in ds) == lech:
            return ma, {r["so_lo"]: THANG_3_LO[lech.index((dt.date.fromisoformat(r["han_dung"]) - ngay_moc).days)]
                        for r in ds}
    raise AssertionError(f"seed không có mã {NCC_3_LO} nào có đúng 3 lô hết hạn sau {THANG_3_LO} tháng")


def dong_giu(od, picking_ids):
    return od.search_read("stock.move.line", [("picking_id", "in", picking_ids)],
                          ["picking_id", "move_id", "product_id", "lot_id", "quantity", "location_id"], order="id")


def tao_don(od, kh_id, sp_id, so_luong, kho_id, ngay_moc):
    so_id = od("sale.order", "create", {
        "partner_id": kh_id, "warehouse_id": kho_id,
        "date_order": utc(ngay_moc, GIO_DAT_HANG), "commitment_date": utc(ngay_moc, GIO_DAT_HANG),
        "order_line": [(0, 0, {"product_id": sp_id, "product_uom_qty": so_luong})],
    })
    goi(od, "sale.order", "action_confirm", [so_id])
    phieu = od.search_read("stock.picking", [("sale_id", "=", so_id), ("picking_type_code", "=", "outgoing")],
                           ["name", "state"])
    kiem(len(phieu) == 1, f"đơn {so_id}: {len(phieu)} phiếu xuất")
    if phieu[0]["state"] != "assigned":
        goi(od, "stock.picking", "action_assign", [phieu[0]["id"]])
    return so_id, phieu[0]["id"]


def kich_ban_3_lo(od, ngay_moc, khach, ma, thang_cua_lo, kho_id, bang):
    sp = od.search_read("product.product", [("default_code", "=", ma)],
                        ["display_name", "expiration_time", "uom_id"])
    kiem(sp, f"không có sản phẩm {ma}")
    sp = sp[0]
    goi_thung = od.search_read("product.packaging", [("product_id", "=", sp["id"])], ["qty"])
    n = int(goi_thung[0]["qty"]) if goi_thung else 1
    lo = {l["id"]: l for l in od.search_read("stock.lot", [("product_id", "=", sp["id"])],
                                             ["name", "expiration_date", "pl_remaining_shelf_life_pct"])}
    thang = {lid: thang_cua_lo[l["name"]] for lid, l in lo.items() if l["name"] in thang_cua_lo}
    lo_thang = {t: lid for lid, t in thang.items()}
    giao = dt_odoo(utc(ngay_moc, GIO_DAT_HANG))
    print(f"\n=== Mã 3 lô {sp['display_name']}: hạn dùng {sp['expiration_time']} ngày, thùng {n}")
    for t in THANG_3_LO:
        l = lo[lo_thang[t]]
        print(f"  Lô {l['name']} ({t} tháng): hạn {l['expiration_date']} UTC, "
              f"còn {con_pct(dt_odoo(l['expiration_date']), giao, sp['expiration_time']):.1f}% lúc giao, "
              f"hôm nay {l['pl_remaining_shelf_life_pct']:.1f}%")

    kh_theo_nhom = {}
    for r in khach:
        kh_theo_nhom.setdefault(r["nhom_khach"], r)
    kh_ids = {k["ref"]: k for k in od.search_read(
        "res.partner", [("ref", "in", [kh_theo_nhom[nh]["ma_kh"] for nh in NHOM_THU]), ("parent_id", "=", False)],
        ["ref", "name", "pl_min_shelf_life_pct"])}

    don = []
    for nhom in NHOM_THU:
        kh = kh_ids[kh_theo_nhom[nhom]["ma_kh"]]
        pct = kh["pl_min_shelf_life_pct"]
        so_luong = THUNG_DAT * n
        if nhom == "Minimart":
            # Đặt quá phần còn giữ được của các lô đạt mức, để phiếu chỉ giữ một phần.
            han_min = giao + dt.timedelta(days=math.ceil(pct * sp["expiration_time"] / 100))
            quant = od.search_read("stock.quant", [("product_id", "=", sp["id"]), ("location_id.usage", "=", "internal")],
                                   ["lot_id", "quantity", "reserved_quantity"])
            con = sum(q["quantity"] - q["reserved_quantity"] for q in quant
                      if q["lot_id"] and dt_odoo(lo[q["lot_id"][0]]["expiration_date"]) >= han_min)
            so_luong = int(con) + THUNG_THUA * n
        so_id, pick_id = tao_don(od, kh["id"], sp["id"], so_luong, kho_id, ngay_moc)
        don.append(dict(nhom=nhom, kh=kh, pct=pct, so_id=so_id, pick_id=pick_id, can=so_luong))

    ket_qua = {}
    for d in don:
        p = od("stock.picking", "read", [d["pick_id"]], fields=["name", "state", "scheduled_date"])[0]
        move_state = od.search_read("stock.move", [("picking_id", "=", d["pick_id"])], ["state"])[0]["state"]
        mls = dong_giu(od, [d["pick_id"]])
        giu = Counter()
        for ml in mls:
            giu[thang.get(ml["lot_id"][0], "?") if ml["lot_id"] else "-"] += ml["quantity"]
        d.update(phieu=p["name"], state=p["state"], move_state=move_state, giu=giu, tong=sum(giu.values()))
        ket_qua[d["nhom"]] = d
        bang.append((f"{d['nhom']} {d['pct']}%", p["name"],
                     f"cần {d['can'] // n} thùng, giữ {d['tong'] / n:g} thùng, "
                     + ", ".join(f"lô {t} tháng {q / n:g}" for t, q in sorted(giu.items(), key=str)),
                     f"{p['state']}/{move_state}"))
        kiem(p["scheduled_date"] == utc(ngay_moc, GIO_DAT_HANG),
             f"{p['name']}: ngày dự kiến {p['scheduled_date']}, cần {utc(ngay_moc, GIO_DAT_HANG)}")

    t7, t11 = THANG_3_LO[0], THANG_3_LO[1]
    th = ket_qua["Tạp hóa"]
    kiem(th["giu"] and set(th["giu"]) == {t7} and th["tong"] == th["can"],
         f"tạp hóa phải giữ đủ từ lô {t7} tháng, đang giữ {dict(th['giu'])}")
    for nhom in ("Khách sạn", "Căn tin KCN", "Minimart"):
        d = ket_qua[nhom]
        kiem(t7 not in d["giu"], f"{nhom} ({d['pct']}%) giữ lô {t7} tháng")
        kiem(d["giu"].get(t11), f"{nhom} ({d['pct']}%) không giữ lô {t11} tháng: {dict(d['giu'])}")
    for nhom in ("Khách sạn", "Căn tin KCN"):
        d = ket_qua[nhom]
        kiem(d["tong"] == d["can"] and d["move_state"] == "assigned",
             f"{nhom}: giữ {d['tong']}/{d['can']}, move {d['move_state']}")
    mm = ket_qua["Minimart"]
    # Giao "càng sớm càng tốt" thì phiếu giữ một phần vẫn Ready; move ở trạng thái giữ một phần.
    kiem(0 < mm["tong"] < mm["can"] and mm["move_state"] == "partially_available",
         f"minimart phải chỉ giữ một phần: giữ {mm['tong']}/{mm['can']}, move {mm['move_state']}")

    # Chọn tay lô 7 tháng cho phiếu minimart rồi Validate: phải ra UserError.
    move = od.search_read("stock.move", [("picking_id", "=", mm["pick_id"])], ["location_id", "location_dest_id"])[0]
    quant7 = od.search_read("stock.quant", [("lot_id", "=", lo_thang[t7]), ("location_id.usage", "=", "internal")],
                            ["location_id"])
    ml_id = od("stock.move.line", "create", {
        "move_id": move["id"], "picking_id": mm["pick_id"], "product_id": sp["id"], "lot_id": lo_thang[t7],
        "quantity": n, "location_id": quant7[0]["location_id"][0],
        "location_dest_id": move["location_dest_id"][0], "product_uom_id": sp["uom_id"][0], "picked": True})
    loi = loai_loi = None
    try:
        od("stock.picking", "button_validate", [mm["pick_id"]])
    except xmlrpc.client.Fault as e:
        loi, loai_loi = loi_odoo(e), e.faultCode
    p = od("stock.picking", "read", [mm["pick_id"]], fields=["state"])[0]
    # Odoo trả UserError qua XML-RPC với faultCode 2 (RPC_FAULT_CODE_WARNING), nội dung là thông báo.
    kiem(loi and loai_loi == 2 and lo[lo_thang[t7]]["name"] in loi,
         f"Validate với lô {t7} tháng chọn tay phải ra UserError, được: {loi or 'không lỗi, phiếu ' + p['state']}")
    kiem(p["state"] not in ("done", "cancel"), f"{mm['phieu']} đã {p['state']}")
    thong_bao = [d.strip() for d in loi.splitlines() if d.strip().startswith("- ")]
    bang.append(("Minimart chọn tay lô 7 tháng", mm["phieu"], "Validate: UserError " + " ".join(thong_bao), p["state"]))
    od("stock.move.line", "unlink", [ml_id])
    return sp, lo_thang, n, don


def phieu_nhap_noi_bo(od, sp, lo_thang, n, bang):
    kho = od.search_read("stock.warehouse", [("code", "=", "PL")],
                         ["in_type_id", "int_type_id", "lot_stock_id"])[0]
    loai_nhap = od("stock.picking.type", "read", [kho["in_type_id"][0]],
                   fields=["default_location_src_id", "default_location_dest_id"])[0]
    # Phiếu nhập: lô mới, nhập đủ rồi Validate.
    nhap = od("stock.picking", "create", {
        "picking_type_id": kho["in_type_id"][0],
        "location_id": loai_nhap["default_location_src_id"][0],
        "location_dest_id": loai_nhap["default_location_dest_id"][0],
        "move_ids": [(0, 0, {"name": sp["display_name"], "product_id": sp["id"], "product_uom_qty": 2 * n,
                             "product_uom": sp["uom_id"][0],
                             "location_id": loai_nhap["default_location_src_id"][0],
                             "location_dest_id": loai_nhap["default_location_dest_id"][0]})],
    })
    goi(od, "stock.picking", "action_confirm", [nhap])
    move = od.search_read("stock.move", [("picking_id", "=", nhap)], ["id"])[0]
    for ml in od.search_read("stock.move.line", [("picking_id", "=", nhap)], ["id"]):
        od("stock.move.line", "unlink", [ml["id"]])
    od("stock.move.line", "create", {"move_id": move["id"], "picking_id": nhap, "product_id": sp["id"],
                                     "lot_name": LOT_THU, "quantity": 2 * n, "product_uom_id": sp["uom_id"][0],
                                     "location_id": loai_nhap["default_location_src_id"][0],
                                     "location_dest_id": loai_nhap["default_location_dest_id"][0], "picked": True})
    goi(od, "stock.picking", "button_validate", [nhap])
    p = od("stock.picking", "read", [nhap], fields=["name", "state"])[0]
    kiem(p["state"] == "done", f"phiếu nhập {p['name']} đang {p['state']}")
    bang.append(("Phiếu nhập", p["name"], f"{2} thùng lô {LOT_THU}", p["state"]))

    # Phiếu nội bộ: không thuộc đơn bán nên giữ theo FEFO chuẩn, lấy lô 7 tháng.
    nguon = od.search_read("stock.quant", [("lot_id", "=", lo_thang[THANG_3_LO[0]]),
                                           ("location_id.usage", "=", "internal"), ("quantity", ">", 0)],
                           ["location_id"])[0]["location_id"][0]
    noi_bo = od("stock.picking", "create", {
        "picking_type_id": kho["int_type_id"][0], "location_id": nguon, "location_dest_id": kho["lot_stock_id"][0],
        "move_ids": [(0, 0, {"name": sp["display_name"], "product_id": sp["id"], "product_uom_qty": n,
                             "product_uom": sp["uom_id"][0], "location_id": nguon,
                             "location_dest_id": kho["lot_stock_id"][0]})],
    })
    goi(od, "stock.picking", "action_confirm", [noi_bo])
    goi(od, "stock.picking", "action_assign", [noi_bo])
    mls = dong_giu(od, [noi_bo])
    kiem(mls and all(ml["lot_id"] and ml["lot_id"][0] == lo_thang[THANG_3_LO[0]] for ml in mls),
         f"phiếu nội bộ phải giữ lô {THANG_3_LO[0]} tháng (FEFO chuẩn): {[ml['lot_id'] for ml in mls]}")
    od("stock.move.line", "write", [ml["id"] for ml in mls], {"picked": True})
    goi(od, "stock.picking", "button_validate", [noi_bo])
    p = od("stock.picking", "read", [noi_bo], fields=["name", "state"])[0]
    kiem(p["state"] == "done", f"phiếu nội bộ {p['name']} đang {p['state']}")
    bang.append(("Phiếu nội bộ", p["name"], f"1 thùng lô {THANG_3_LO[0]} tháng (FEFO chuẩn)", p["state"]))


def don_ngay_moc(od, ngay_moc, ds_so_don, ton_kho, bang):
    """Xác nhận 81 đơn của ngày mốc với ngày giao 08:00 ngày mốc, giữ hàng, kiểm từng dòng giữ."""
    don = od.search_read("sale.order", [("client_order_ref", "in", ds_so_don)],
                         ["state", "client_order_ref", "partner_id", "pl_min_shelf_life_pct"])
    kiem(len(don) == len(ds_so_don), f"có {len(don)}/{len(ds_so_don)} đơn của ngày mốc: chạy seed_import --orders")
    nhap = [d["id"] for d in don if d["state"] in ("draft", "sent")]
    kiem(len(nhap) == len(don), f"{len(don) - len(nhap)} đơn ngày mốc đã xác nhận trong database nguồn")
    od("sale.order", "write", nhap, {"commitment_date": utc(ngay_moc, GIO_DAT_HANG)})
    goi(od, "sale.order", "action_confirm", nhap)
    theo_id = {d["id"]: d for d in don}
    phieu = od.search_read("stock.picking", [("sale_id", "in", list(theo_id)), ("picking_type_code", "=", "outgoing")],
                           ["name", "state", "sale_id", "scheduled_date"], order="id")
    chua = [p["id"] for p in phieu if p["state"] in ("confirmed", "waiting")]
    if chua:
        goi(od, "stock.picking", "action_assign", chua)
    phieu = od.search_read("stock.picking", [("id", "in", [p["id"] for p in phieu])],
                           ["name", "state", "sale_id", "scheduled_date"], order="id")
    moves = od.search_read("stock.move", [("picking_id", "in", [p["id"] for p in phieu])],
                           ["picking_id", "state", "product_uom_qty", "quantity", "date"])
    mls = dong_giu(od, [p["id"] for p in phieu])
    sp_ids = sorted({ml["product_id"][0] for ml in mls})
    han_sp = {s["id"]: s["expiration_time"] for s in od.search_read("product.product", [("id", "in", sp_ids)],
                                                                     ["expiration_time"])}
    lo = {l["id"]: l for l in od.search_read("stock.lot", [("id", "in", sorted({ml["lot_id"][0] for ml in mls
                                                                                if ml["lot_id"]}))],
                                             ["name", "expiration_date", "product_id"])}
    lo_them = {(r["ma_sp"], r["so_lo"]) for r in ton_kho
               if r["han_dung"] and (dt.date.fromisoformat(r["han_dung"]) - ngay_moc).days <= 30}
    ma_sp = {s["id"]: s["default_code"] for s in od.search_read("product.product", [("id", "in", sp_ids)],
                                                                ["default_code"])}
    so_081 = f"DB{ngay_moc:%Y%m%d}-081"
    giao = dt_odoo(utc(ngay_moc, GIO_DAT_HANG))
    tong = Counter()
    con_thap = defaultdict(lambda: 1000.0)
    loi = []
    for p in phieu:
        d = theo_id[p["sale_id"][0]]
        ref = d["client_order_ref"]
        if ref == so_081:
            bang.append((f"Đơn quá tải {so_081}", p["name"], "không tính trong 80 đơn", p["state"]))
            continue
        nhom = f"{d['pl_min_shelf_life_pct']}%"
        tong[nhom, "phiếu"] += 1
        tong[nhom, "ready"] += p["state"] == "assigned"
        if p["state"] != "assigned":
            loi.append(f"{ref} {p['name']} đang {p['state']}")
        if p["scheduled_date"] != utc(ngay_moc, GIO_DAT_HANG):
            loi.append(f"{ref} {p['name']} ngày dự kiến {p['scheduled_date']}")
        for m in moves:
            if m["picking_id"][0] == p["id"] and (m["state"] != "assigned" or m["quantity"] < m["product_uom_qty"]):
                loi.append(f"{ref} move {m['id']}: {m['state']} {m['quantity']}/{m['product_uom_qty']}")
        for ml in mls:
            if ml["picking_id"][0] != p["id"] or not ml["lot_id"]:
                continue
            l = lo[ml["lot_id"][0]]
            tong[nhom, "dòng"] += 1
            if (ma_sp[ml["product_id"][0]], l["name"]) in lo_them:
                loi.append(f"{ref} giữ lô cận date/hết hạn {l['name']}")
            if not l["expiration_date"]:
                continue
            pct = con_pct(dt_odoo(l["expiration_date"]), giao, han_sp[ml["product_id"][0]])
            con_thap[nhom] = min(con_thap[nhom], pct)
            if pct < d["pl_min_shelf_life_pct"]:
                loi.append(f"{ref} giữ lô {l['name']} còn {pct:.1f}% < {d['pl_min_shelf_life_pct']}%")
    for nhom in sorted({k[0] for k in tong}, key=lambda s: int(s[:-1])):
        bang.append((f"Đơn ngày mốc, khách {nhom}", f"{tong[nhom, 'phiếu']} phiếu",
                     f"{tong[nhom, 'dòng']} dòng giữ lô, lô thấp nhất còn {con_thap[nhom]:.1f}%",
                     f"{tong[nhom, 'ready']} Ready"))
    kiem(sum(tong[k] for k in tong if k[1] == "phiếu") == len(ds_so_don) - 1,
         f"thiếu phiếu xuất: {sum(tong[k] for k in tong if k[1] == 'phiếu')}/{len(ds_so_don) - 1}")
    kiem(not loi, f"{len(loi)} lỗi ở đơn ngày mốc: " + "; ".join(loi[:8]))


def in_bang(bang):
    print("\n=== Kết quả")
    rong = [max(len(str(r[i])) for r in bang) for i in range(4)]
    for r in bang:
        print(f"{r[0]:<{rong[0]}}  {r[1]:<{rong[1]}}  {r[3]:<{rong[3]}}  {r[2]}")


def chay(od, url, db, ngay_moc, ds_so_don):
    bang = []
    try:
        cai_module(od)
        nap_lai_khach(url, db)
        khach = doc_csv(SEED / "khach_hang.csv")
        ton_kho = doc_csv(SEED / "ton_kho.csv")
        kiem_muc_khach(od, khach)
        kho = od.search_read("stock.warehouse", [("code", "=", "PL")], ["id"])
        kiem(kho, "không có kho PL")
        ma, thang_cua_lo = ma_3_lo(ton_kho, ngay_moc)
        sp, lo_thang, n, don = kich_ban_3_lo(od, ngay_moc, khach, ma, thang_cua_lo, kho[0]["id"], bang)
        phieu_nhap_noi_bo(od, sp, lo_thang, n, bang)
        # Hủy đơn thử để trả hàng đã giữ, rồi giữ hàng cho đơn ngày mốc trên tồn gốc.
        od("sale.order", "action_cancel", [d["so_id"] for d in don], context={"disable_cancel_warning": True})
        huy = od.search_read("sale.order", [("id", "in", [d["so_id"] for d in don])], ["state"])
        kiem(all(d["state"] == "cancel" for d in huy), "chưa hủy được đơn thử")
        don_ngay_moc(od, ngay_moc, ds_so_don, ton_kho, bang)
    finally:
        if bang:
            in_bang(bang)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", default=URL)
    p.add_argument("--src", default=DB_CHINH)
    p.add_argument("--db", default=DB_CHECK)
    p.add_argument("--keep", action="store_true", help="không xóa database check")
    args = p.parse_args()

    don_ban = doc_csv(SEED / "don_ban.csv")
    ngay_moc = dt.date.fromisoformat(don_ban[0]["ngay"])
    ds_so_don = sorted({r["so_don"] for r in don_ban})
    print(f"Ngày mốc {ngay_moc:%d/%m/%Y}, {len(ds_so_don)} đơn trong seed")

    url = args.url.rstrip("/")
    ql = QuanLyDb(url)
    ql.xoa(args.db)
    ql.nhan_ban(args.src, args.db)
    print(f"Đã nhân bản {args.src} thành {args.db}")
    try:
        chay(ket_noi(url, args.db), url, args.db, ngay_moc, ds_so_don)
    finally:
        if args.keep:
            print(f"\nGiữ database {args.db}")
        else:
            ql.xoa(args.db)
            print(f"\nĐã xóa {args.db}")
    print("PASS: giữ hàng đúng mức hạn dùng của khách, vẫn FEFO; validate lô không đạt bị chặn; "
          "nhập, nội bộ không bị ảnh hưởng; 80 đơn ngày mốc đều Ready")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        sys.exit(f"FAIL: {e}")
    except xmlrpc.client.Fault as e:
        sys.exit(f"Lỗi từ Odoo: {loi_odoo(e)}")
    except (ConnectionError, OSError) as e:
        sys.exit(f"Không kết nối được Odoo: {e}. Kiểm tra docker compose ps và --url")
