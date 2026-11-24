#!/usr/bin/env python3
"""Chạy thử module pl_delivery_route trên bản nhân bản của database chính, xong thì xóa bản đó.

Nhân bản pl_moc thành pl_route_check > cài pl_delivery_route > nạp xe từ seed/demo/xe.csv > xác nhận đủ
đơn bán của ngày mốc và giữ hàng cho phiếu xuất > nhận hàng của một nhà cung cấp rồi tạo phiếu trả, để
Ready > tạo kế hoạch giao hàng cho ngày mốc > Lập tuyến (2 lần,
phải ra cùng kết quả) > in bảng theo xe và danh sách chưa xếp > Xác nhận kế hoạch.

Kiểm tra: không xe nào quá tải, mỗi phiếu xuất Ready của ngày mốc nằm đúng 1 lần (trong một chuyến hoặc
trong danh sách chưa xếp), không chuyến nào vượt số điểm tối đa, cả 4 xe đều có chuyến, chỉ đơn
DB<ngày mốc>-081 nằm trong danh sách chưa xếp, phiếu trả nhà cung cấp không có mặt trong kế hoạch, xác nhận xong phiếu có chuyến và thứ tự điểm dừng. Sai điều
nào thì dừng, mã thoát khác 0.

    python scripts/check_route.py
    python scripts/check_route.py --keep            # giữ database check để xem trên giao diện
    python scripts/check_route.py --max-stops 20    # số điểm tối đa mỗi chuyến (mặc định theo kế hoạch)

Mật khẩu như scripts/seminar3: admin lấy từ ODOO_PASSWORD, master từ ODOO_MASTER_PASSWORD hoặc
config/odoo.conf.
"""

import argparse
import datetime as dt
import re
import sys
import xmlrpc.client
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "seminar3"))

import chung  # noqa: E402
from chung import DB_CHINH, URL, QuanLyDb, goi, ket_noi  # noqa: E402
from seed_import import GIO_DAT_HANG, GIO_VN, ThongKe, doc_csv, nap_xe  # noqa: E402

DB_CHECK = "pl_route_check"
MODULE = "pl_delivery_route"
SEED = ROOT / "seed" / "demo"
NCC = "NCC01"
LO_TRA = "LTRANCC"


def kiem(dung, thong_diep):
    if not dung:
        raise AssertionError(thong_diep)


def utc(ngay, gio):
    """Giờ Việt Nam của ngày `ngay` đổi sang chuỗi UTC như Odoo lưu."""
    return (dt.datetime.combine(ngay, dt.time(gio)) - dt.timedelta(hours=GIO_VN)).strftime("%Y-%m-%d %H:%M:%S")


def cai_module(od):
    goi(od, "ir.module.module", "update_list")
    m = od.search_read("ir.module.module", [("name", "=", MODULE)], ["state"])
    kiem(m, f"Odoo không thấy module {MODULE}: kiểm tra addons_path")
    if m[0]["state"] != "installed":
        goi(od, "ir.module.module", "button_immediate_install", [m[0]["id"]])
    m = od.search_read("ir.module.module", [("name", "=", MODULE)], ["state", "latest_version"])[0]
    kiem(m["state"] == "installed", f"{MODULE} đang {m['state']}")
    print(f"Đã cài {MODULE} {m['latest_version']}")


def chuan_bi_don(od, ngay_moc, ds_so_don):
    """Xác nhận các báo giá của ngày mốc còn nháp và giữ hàng cho phiếu xuất chưa Ready.

    Odoo đặt ngày dự kiến của phiếu xuất theo lúc xác nhận đơn. Đơn xác nhận sau ngày mốc (vd. chạy trên
    database mới) sẽ có ngày dự kiến là hôm nay, nên được đưa về 08:00 ngày mốc để giống đơn đặt trong ngày.
    """
    don = od.search_read("sale.order", [("client_order_ref", "in", ds_so_don)], ["state", "client_order_ref"])
    kiem(len(don) == len(ds_so_don), f"có {len(don)}/{len(ds_so_don)} đơn của ngày mốc: chạy seed_import --orders")
    nhap = [d["id"] for d in don if d["state"] in ("draft", "sent")]
    if nhap:
        goi(od, "sale.order", "action_confirm", nhap)
    print(f"Đơn bán ngày mốc: {len(don)}, vừa xác nhận {len(nhap)}")

    so_id = [d["id"] for d in don]
    phieu = od.search_read("stock.picking", [("sale_id", "in", so_id), ("picking_type_code", "=", "outgoing"),
                                             ("state", "not in", ["done", "cancel"])],
                           ["state", "scheduled_date"], order="id")
    chua = [p["id"] for p in phieu if p["state"] in ("confirmed", "waiting")]
    if chua:
        goi(od, "stock.picking", "action_assign", chua)
    het_ngay = utc(ngay_moc + dt.timedelta(days=1), 0)
    tre = [p["id"] for p in phieu if p["scheduled_date"] >= het_ngay]
    if tre:
        od("stock.picking", "write", tre, {"scheduled_date": utc(ngay_moc, GIO_DAT_HANG)})
        print(f"  Đưa ngày dự kiến của {len(tre)} phiếu về ngày mốc")
    phieu = od.search_read("stock.picking", [("id", "in", [p["id"] for p in phieu])], ["state"])
    ready = [p["id"] for p in phieu if p["state"] == "assigned"]
    print(f"Phiếu xuất: {len(phieu)}, Ready {len(ready)}")
    kiem(len(ready) == len(phieu), f"còn {len(phieu) - len(ready)} phiếu chưa Ready (thiếu tồn?)")
    return set(ready)


def tao_phieu_tra_ncc(od, ngay_moc, kho_id):
    """Nhận 1 thùng hàng của NCC rồi Return cả thùng, chưa validate phiếu trả. Trả về phiếu trả, đang Ready.

    Phiếu trả dùng chung loại Delivery Orders (PL/OUT) với phiếu giao khách. Để nó chỉ có thể bị loại nhờ
    điểm đến là Vendors: ngày dự kiến đưa về ngày mốc, NCC được cho tọa độ của kho lệch đi một chút.
    """
    chung.cai_module(od, "purchase_stock")
    ncc = od.search_read("res.partner", [("ref", "=", NCC), ("parent_id", "=", False)], ["name"])
    sp = od.search_read("product.product", [("default_code", "=like", f"{NCC}-%")], ["expiration_time"],
                        order="default_code")
    thung = od.search_read("product.packaging", [("product_id", "in", [x["id"] for x in sp])],
                           ["qty", "product_id"], order="product_id")
    kiem(ncc and thung, f"seed không có {NCC} hoặc quy cách thùng")
    sl, pid = thung[0]["qty"], thung[0]["product_id"][0]
    kho = od("stock.warehouse", "read", [kho_id], fields=["partner_id"])[0]["partner_id"][0]
    td = od("res.partner", "read", [kho], fields=["partner_latitude", "partner_longitude"])[0]
    od("res.partner", "write", [ncc[0]["id"]], {"partner_latitude": td["partner_latitude"] + 0.01,
                                                "partner_longitude": td["partner_longitude"] + 0.01})

    po = od("purchase.order", "create", {"partner_id": ncc[0]["id"], "order_line": [
        (0, 0, {"product_id": pid, "product_qty": sl})]})
    goi(od, "purchase.order", "button_confirm", [po])
    nhap = od("purchase.order", "read", [po], fields=["picking_ids"])[0]["picking_ids"][0]
    ml = od("stock.move.line", "search", [("picking_id", "=", nhap)])
    han = next(x["expiration_time"] for x in sp if x["id"] == pid)
    od("stock.move.line", "write", ml, {"lot_name": LO_TRA, "quantity": sl, "picked": True,
                                        "expiration_date": utc(ngay_moc + dt.timedelta(days=han), 0)})
    goi(od, "stock.picking", "button_validate", [nhap])

    ctx = {"active_model": "stock.picking", "active_id": nhap, "active_ids": [nhap]}
    wiz = od("stock.return.picking", "create", {}, context=ctx)
    dong = od("stock.return.picking.line", "search", [("wizard_id", "=", wiz)])
    od("stock.return.picking.line", "write", dong, {"quantity": sl})
    tra = goi(od, "stock.return.picking", "action_create_returns", [wiz], context=ctx)["res_id"]
    od("stock.picking", "write", [tra], {"scheduled_date": utc(ngay_moc, GIO_DAT_HANG)})
    p = od.search_read("stock.picking", [("id", "=", tra)],
                       ["name", "state", "picking_type_code", "scheduled_date", "location_dest_id"])[0]
    kiem(p["state"] == "assigned" and p["picking_type_code"] == "outgoing"
         and p["scheduled_date"] == utc(ngay_moc, GIO_DAT_HANG), f"phiếu trả NCC: {p}")
    print(f"Phiếu trả {ncc[0]['name']}: {p['name']} Ready, đến {p['location_dest_id'][1]}")
    return p


def doc_ket_qua(od, plan_id):
    plan = od("pl.delivery.plan", "read", [plan_id],
              fields=["name", "state", "max_stops", "total_km", "total_weight", "trip_count",
                      "unassigned_count"])[0]
    trips = od.search_read("pl.delivery.trip", [("plan_id", "=", plan_id)],
                           ["vehicle_id", "stop_count", "weight", "capacity_kg", "load_pct", "total_km", "maps_url",
                            "maps_segment_count", "maps_links"], order="vehicle_id")
    stops = od.search_read("pl.delivery.stop", [("plan_id", "=", plan_id)],
                           ["trip_id", "sequence", "partner_id", "picking_ids", "weight", "leg_km"],
                           order="trip_id, sequence")
    chua = od.search_read("pl.delivery.unassigned", [("plan_id", "=", plan_id)],
                          ["picking_id", "partner_id", "weight", "reason"], order="partner_id, picking_id")
    return plan, trips, stops, chua


def tom_tat(trips, stops, chua):
    """Phần kết quả dùng để so hai lần lập tuyến."""
    return ([(t["vehicle_id"][0], round(t["weight"], 4), round(t["total_km"], 6)) for t in trips],
            [(s["sequence"], s["partner_id"][0], tuple(s["picking_ids"])) for s in stops],
            [(c["picking_id"][0], c["reason"]) for c in chua])


def in_bang(od, plan, trips, chua, xe):
    print(f"\n=== {plan['name']}: {plan['trip_count']} chuyến, {plan['total_weight']:,.1f} kg, "
          f"{plan['total_km']:,.1f} km, {plan['unassigned_count']} phiếu chưa xếp, "
          f"tối đa {plan['max_stops'] or 'không giới hạn'} điểm mỗi chuyến")
    theo_xe = {t["vehicle_id"][0]: t for t in trips}
    print(f"{'Xe':<6} {'Tải trọng':>9} {'Số điểm':>7} {'Tải kg':>9} {'% tải':>6} {'Km':>7} {'Đoạn Maps':>9}")
    for x in xe:
        t = theo_xe.get(x["id"])
        if not t:
            print(f"{x['code']:<6} {x['capacity_kg']:>9,.0f} {0:>7} {0:>9,.1f} {0:>6.1f} {0:>7.1f} {'-':>9}")
            continue
        print(f"{x['code']:<6} {x['capacity_kg']:>9,.0f} {t['stop_count']:>7} {t['weight']:>9,.1f} "
              f"{t['load_pct']:>6.1f} {t['total_km']:>7.1f} {t['maps_segment_count']:>9}")
    print("\nLink Google Maps")
    for t in trips:
        code = next(x["code"] for x in xe if x["id"] == t["vehicle_id"][0])
        for so, url in enumerate(re.findall(r'href="([^"]+)"', t["maps_links"] or ""), start=1):
            print(f"  {code} đoạn {so}: {url.replace('&amp;', '&')}")
    print("\nChưa xếp")
    don = {p["id"]: p for p in od.search_read("stock.picking", [("id", "in", [c["picking_id"][0] for c in chua])],
                                              ["name", "sale_id"])}
    ref = {s["id"]: s["client_order_ref"] for s in od.search_read(
        "sale.order", [("id", "in", [p["sale_id"][0] for p in don.values() if p["sale_id"]])], ["client_order_ref"])}
    for c in chua:
        p = don[c["picking_id"][0]]
        so_don = ref.get(p["sale_id"][0]) if p["sale_id"] else ""
        print(f"  {p['name']} {so_don} {c['partner_id'][1] if c['partner_id'] else ''}: "
              f"{c['weight']:,.1f} kg, {c['reason']}")
    if not chua:
        print("  (không có)")
    return {c["picking_id"][0]: ref.get(don[c["picking_id"][0]]["sale_id"][0]) for c in chua
            if don[c["picking_id"][0]]["sale_id"]}


def chay(od, ngay_moc, ds_so_don, max_stops=None):
    cai_module(od)
    tk = ThongKe()
    nap_xe(od, tk, doc_csv(SEED / "xe.csv"))
    xe = od.search_read("pl.vehicle", [], ["code", "capacity_kg", "warehouse_id"], order="code")
    kiem(len(xe) == len(doc_csv(SEED / "xe.csv")), f"có {len(xe)} xe trong Odoo")
    print("Xe: " + ", ".join(f"{x['code']} {x['capacity_kg']:g} kg" for x in xe))

    ready = chuan_bi_don(od, ngay_moc, ds_so_don)
    kho = od.search_read("stock.warehouse", [("code", "=", "PL")], ["id"])
    kiem(kho, "không có kho PL")
    tra = tao_phieu_tra_ncc(od, ngay_moc, kho[0]["id"])
    vals = {"date": ngay_moc.isoformat(), "warehouse_id": kho[0]["id"]}
    if max_stops is not None:
        vals["max_stops"] = max_stops
    plan_id = od("pl.delivery.plan", "create", vals)

    goi(od, "pl.delivery.plan", "action_compute_routes", [plan_id])
    lan_1 = doc_ket_qua(od, plan_id)
    goi(od, "pl.delivery.plan", "action_compute_routes", [plan_id])
    plan, trips, stops, chua = doc_ket_qua(od, plan_id)
    kiem(tom_tat(*lan_1[1:]) == tom_tat(trips, stops, chua), "lập tuyến hai lần ra kết quả khác nhau")
    kiem(plan["state"] == "routed", f"kế hoạch đang {plan['state']}")
    chua_xep = in_bang(od, plan, trips, chua, xe)

    # Mỗi phiếu Ready đúng một lần.
    da_xep = [p for s in stops for p in s["picking_ids"]]
    tat_ca = da_xep + [c["picking_id"][0] for c in chua]
    kiem(len(tat_ca) == len(set(tat_ca)), "có phiếu xuất xuất hiện hơn 1 lần")
    kiem(ready <= set(tat_ca), f"thiếu phiếu: {sorted(ready - set(tat_ca))}")
    # Phiếu trả NCC đang Ready không được vào chuyến, cũng không được vào danh sách chưa xếp.
    kiem(tra["id"] not in tat_ca, f"phiếu trả NCC {tra['name']} bị lấy vào kế hoạch giao hàng "
         f"({'trong chuyến' if tra['id'] in da_xep else 'chưa xếp'})")
    # Không xe nào quá tải; mỗi xe tối đa 1 chuyến.
    kiem(len({t["vehicle_id"][0] for t in trips}) == len(trips), "có xe chạy 2 chuyến")
    for t in trips:
        kiem(t["weight"] <= t["capacity_kg"] + 1e-6, f"{t['vehicle_id'][1]} quá tải: {t['weight']:,.1f} kg")
        kiem(t["maps_url"] and t["maps_url"].startswith("https://www.google.com/maps/dir/?api=1"),
             f"{t['vehicle_id'][1]} thiếu link Maps")
    # Số điểm mỗi chuyến không vượt giới hạn; cả đội xe đều có chuyến.
    if plan["max_stops"]:
        for t in trips:
            kiem(t["stop_count"] <= plan["max_stops"],
                 f"{t['vehicle_id'][1]} có {t['stop_count']} điểm, vượt {plan['max_stops']}")
    co_chuyen = {t["vehicle_id"][0] for t in trips}
    thieu_xe = [x["code"] for x in xe if x["id"] not in co_chuyen]
    kiem(not thieu_xe, f"xe không có chuyến: {', '.join(thieu_xe)}")
    # Đơn quá tải nằm trong danh sách chưa xếp, đúng lý do, và là phiếu chưa xếp duy nhất.
    so_081 = f"DB{ngay_moc:%Y%m%d}-081"
    dong_081 = [c for c in chua if chua_xep.get(c["picking_id"][0]) == so_081]
    kiem(dong_081, f"{so_081} không nằm trong danh sách chưa xếp")
    kiem(dong_081[0]["reason"] == "overweight", f"{so_081}: lý do {dong_081[0]['reason']}")
    khac = sorted(chua_xep.get(c["picking_id"][0]) or c["picking_id"][1] for c in chua if c not in dong_081)
    kiem(not khac, f"ngoài {so_081} còn {len(khac)} phiếu chưa xếp: {', '.join(khac)}")

    goi(od, "pl.delivery.plan", "action_confirm", [plan_id])
    plan = od("pl.delivery.plan", "read", [plan_id], fields=["state"])[0]
    kiem(plan["state"] == "confirmed", f"xác nhận xong kế hoạch đang {plan['state']}")
    ghi = od.search_read("stock.picking", [("id", "in", da_xep)], ["pl_trip_id", "pl_stop_sequence"])
    kiem(all(p["pl_trip_id"] and p["pl_stop_sequence"] for p in ghi), "phiếu chưa có chuyến sau khi xác nhận")
    print(f"\nXác nhận {plan_id}: {len(ghi)} phiếu đã ghi chuyến và thứ tự điểm dừng")

    # Mỗi chuyến một Batch Transfer, mỗi phiếu nằm đúng batch của chuyến mình.
    trips = od.search_read("pl.delivery.trip", [("plan_id", "=", plan_id)], ["vehicle_id", "batch_id"],
                           order="vehicle_id")
    batch_ids = {t["batch_id"][0] for t in trips if t["batch_id"]}
    kiem(len(batch_ids) == len(trips), f"{len(batch_ids)} batch cho {len(trips)} chuyến")
    batches = {b["id"]: b for b in od.search_read("stock.picking.batch", [("id", "in", list(batch_ids))],
                                                  ["name", "description", "state", "picking_ids"])}
    phieu = {p["id"]: p for p in od.search_read("stock.picking", [("id", "in", da_xep)],
                                                ["pl_trip_id", "batch_id", "batch_sequence", "pl_stop_sequence"])}
    for t in trips:
        b = batches[t["batch_id"][0]]
        cua_chuyen = {pid for pid, p in phieu.items() if p["pl_trip_id"][0] == t["id"]}
        kiem(set(b["picking_ids"]) == cua_chuyen, f"batch {b['name']} không khớp phiếu của chuyến {t['vehicle_id'][1]}")
        kiem(all(phieu[pid]["batch_sequence"] == phieu[pid]["pl_stop_sequence"] for pid in cua_chuyen),
             f"batch {b['name']}: thứ tự phiếu khác thứ tự giao")
        print(f"  {b['name']} [{b['state']}] {b['description']}: {len(b['picking_ids'])} phiếu")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", default=URL)
    p.add_argument("--src", default=DB_CHINH)
    p.add_argument("--db", default=DB_CHECK)
    p.add_argument("--keep", action="store_true", help="không xóa database check")
    p.add_argument("--max-stops", type=int, help="số điểm tối đa mỗi chuyến, 0 = không giới hạn "
                                                  "(mặc định theo kế hoạch)")
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
        chay(ket_noi(url, args.db), ngay_moc, ds_so_don, args.max_stops)
    finally:
        if args.keep:
            print(f"\nGiữ database {args.db}")
        else:
            ql.xoa(args.db)
            print(f"\nĐã xóa {args.db}")
    print("PASS: không xe nào quá tải hay vượt số điểm, cả đội xe có chuyến, chỉ đơn quá tải chưa xếp, "
          "phiếu trả NCC không vào kế hoạch")


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
