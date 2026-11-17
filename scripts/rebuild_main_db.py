#!/usr/bin/env python3
"""Dựng lại database chính (mặc định pl_moc) từ bộ seed hiện tại trong seed/demo/.

1. Dựng database mới <build-name> theo thứ tự trong docs/seed.md: base, đặt công ty ở Việt Nam và tiền VND
   trước khi cài kế toán, rồi cài các module của nhóm.
2. seed_import.py --orders lên database mới, phải ra 0 cảnh báo.
3. setup_warehouse.py lên database mới.
4. Gán Barcode option group cho các Operation Type của kho (docs/barcode.md).
5. Kiểm tra database mới: kho, dãy, ô, sản phẩm, lô và tồn, khách, báo giá, xe, Invoicing Policy.
6. Rà soát database chính cũ (chỉ đọc): những gì có trong DB cũ mà không đến từ seed. Danh sách khác rỗng
   thì in ra và hỏi trước khi đi tiếp (trừ khi có --yes).
7. Thay database chính: backup DB cũ bằng scripts/backup.sh (Windows: backup.ps1), đổi tên DB cũ thành
   <target>_old_<yyyymmdd_hhmm>, đổi tên <build-name> thành <target>. Đổi tên qua database manager của Odoo
   để filestore đổi theo. Không xóa database chính cũ.

Sai ở bước nào thì dừng, mã thoát khác 0, database chính không bị đụng tới. Database <build-name> do script
này tạo được đánh dấu; chạy lại thì script xóa bản đánh dấu đó rồi dựng lại. Database trùng tên mà không có
dấu thì script dừng, không xóa.

    python scripts/rebuild_main_db.py                 # dựng pl_moc_new, rà soát, thay pl_moc
    python scripts/rebuild_main_db.py --skip-swap     # chỉ dựng và kiểm tra pl_moc_new
    python scripts/rebuild_main_db.py --yes           # không hỏi xác nhận

Mật khẩu như scripts/seminar3: admin lấy từ ODOO_PASSWORD, master từ ODOO_MASTER_PASSWORD hoặc
config/odoo.conf. Xem docs/seed.md, mục "Dựng lại database chính".
"""

import argparse
import datetime as dt
import getpass
import os
import re
import subprocess
import sys
import time
import xmlrpc.client
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "seminar3"))

from chung import DB_CHINH, URL, QuanLyDb, goi  # noqa: E402
from seed_import import Odoo, doc_csv, so  # noqa: E402

MODULE = [
    "stock", "purchase_stock", "sale_stock", "sale_management", "product_expiry", "pl_base", "pl_fefo_pick",
    "pl_delivery_route", "stock_barcodes", "pl_barcode_camera", "pl_product_barcode",
]
# Trường loại thao tác của kho > nhóm tùy chọn quét mã vạch (docs/barcode.md).
NHOM_BARCODE = {
    "in_type_id": "stock_barcodes.stock_barcodes_option_group_picking_in",
    "out_type_id": "stock_barcodes.stock_barcodes_option_group_picking_out",
    "int_type_id": "stock_barcodes.stock_barcodes_option_group_picking_internal",
}
# Dấu của database do script này dựng: chỉ database có dấu mới được xóa để dựng lại.
DAU = "pl_rebuild.build_db"

SO_KHO, SO_DAY, SO_O = 1, 6, 240
SO_SP, SO_KHACH, SO_XE = 150, 300, 4
HOA_DON_THEO = "delivery"

VND_SHELL = """
vnd = env.ref('base.VND')
vnd.active = True
env.company.write({{'country_id': env.ref('base.vn').id, 'currency_id': vnd.id}})
env['ir.config_parameter'].sudo().set_param({dau!r}, {db!r})
env.cr.commit()
"""


def buoc(so_buoc, ten):
    print(f"\n=== Bước {so_buoc}. {ten}", flush=True)


def dung(thong_diep, ma=1):
    print(f"\nDỪNG: {thong_diep}", file=sys.stderr)
    sys.exit(ma)


def chay(lenh, input=None, hien=False):
    """Chạy lệnh trong thư mục repo. hien: in output ra luôn; không thì giữ lại, lỗi mới in 40 dòng cuối."""
    kq = subprocess.run(lenh, cwd=ROOT, input=input, text=True, encoding="utf-8", errors="replace",
                        stdout=None if hien else subprocess.PIPE, stderr=None if hien else subprocess.STDOUT)
    if kq.returncode != 0:
        if not hien:
            print("\n".join((kq.stdout or "").splitlines()[-40:]))
        dung(f"lệnh lỗi (mã {kq.returncode}): {' '.join(lenh)}")
    return kq.stdout or ""


def compose(*args, input=None):
    return chay(["docker", "compose", *args], input=input)


def psql(db, sql):
    """Một câu SQL chỉ đọc trên database `db` qua container db, trả về chuỗi kết quả (-tA)."""
    return compose("exec", "-T", "db", "sh", "-c", 'psql -U "$POSTGRES_USER" -d "$1" -tAc "$2"', "_", db, sql).strip()


def chay_script(ten, db, *them):
    """Chạy scripts/<ten> lên `db`, in output, trả về output."""
    print(f"$ python scripts/{ten} --db {db} {' '.join(them)}".rstrip(), flush=True)
    out = chay([sys.executable, str(ROOT / "scripts" / ten), "--db", db, *them])
    print(out.rstrip())
    return out


def hoi(cau):
    try:
        return input(f"{cau} [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:
        print()
        return False


# ---------------------------------------------------------------- Bước 1


def don_build(ql, build):
    if not ql.co(build):
        return
    try:
        dau = psql(build, f"SELECT value FROM ir_config_parameter WHERE key = '{DAU}'")
    except SystemExit:
        dau = ""
    if dau != build:
        dung(f"database {build} đã có nhưng không do script này dựng. Đổi --build-name hoặc tự xử lý {build}")
    print(f"Xóa {build} do lần chạy trước của script dựng")
    ql.xoa(build)


def dung_db(ql, build):
    buoc(1, f"Dựng database {build}")
    don_build(ql, build)
    bat_dau = time.monotonic()
    print("Cài base (không dữ liệu demo)", flush=True)
    compose("run", "--rm", "-T", "odoo", "odoo", "-d", build, "-i", "base", "--without-demo=all",
            "--stop-after-init", "--log-level=warn")
    print("Đặt công ty ở Việt Nam, tiền VND", flush=True)
    compose("run", "--rm", "-T", "odoo", "odoo", "shell", "-d", build, "--no-http", "--log-level=warn",
            input=VND_SHELL.format(dau=DAU, db=build))
    print(f"Cài {', '.join(MODULE)}", flush=True)
    compose("run", "--rm", "-T", "odoo", "odoo", "-d", build, "-i", ",".join(MODULE), "--without-demo=all",
            "--stop-after-init", "--log-level=warn")
    print(f"Xong sau {time.monotonic() - bat_dau:.0f} giây")


# ---------------------------------------------------------------- Bước 2-4


def nap_seed(build):
    buoc(2, "Nạp seed")
    out = chay_script("seed_import.py", build, "--orders")
    m = re.search(r"^Cảnh báo: (\d+)", out, re.M)
    if not m:
        dung("không đọc được số cảnh báo của seed_import.py")
    if int(m.group(1)):
        dung(f"seed_import.py ra {m.group(1)} cảnh báo, cần 0")


def cau_hinh_kho(build):
    buoc(3, "Cấu hình kho")
    chay_script("setup_warehouse.py", build)


def gan_barcode(od):
    buoc(4, "Gán Barcode option group cho Operation Type")
    kho = od.search_read("stock.warehouse", [], list(NHOM_BARCODE), order="id")
    if len(kho) != 1:
        dung(f"cần đúng 1 kho, đang có {len(kho)}")
    doi = 0
    for truong, xmlid in NHOM_BARCODE.items():
        module, ten = xmlid.split(".")
        nhom = od.search_read("ir.model.data", [("module", "=", module), ("name", "=", ten)], ["res_id"])
        if not nhom:
            dung(f"không có {xmlid}: chưa cài stock_barcodes")
        loai_id = kho[0][truong][0]
        loai = od("stock.picking.type", "read", [loai_id], fields=["name", "barcode_option_group_id"])[0]
        hien = loai["barcode_option_group_id"]
        if not hien or hien[0] != nhom[0]["res_id"]:
            od("stock.picking.type", "write", [loai_id], {"barcode_option_group_id": nhom[0]["res_id"]})
            doi += 1
        sau = od("stock.picking.type", "read", [loai_id], fields=["barcode_option_group_id"])[0]
        print(f"  {loai['name']}: {sau['barcode_option_group_id'][1]}")
    print(f"  Cập nhật {doi}")


# ---------------------------------------------------------------- Bước 5


def kiem_tra(od, seed):
    buoc(5, "Kiểm tra database mới")
    kq = []

    def ghi(ten, mong, thuc):
        kq.append((ten, str(mong), str(thuc), str(mong) == str(thuc)))

    kho = od.search_read("stock.warehouse", [], ["code", "lot_stock_id"])
    ghi("Kho", f"{SO_KHO} kho PL", f"{len(kho)} kho {', '.join(k['code'] for k in kho)}")
    ton = kho[0]["lot_stock_id"][0] if kho else 0

    ma_day = {r["ma_vi_tri"]: r for r in seed["vi_tri"] if not r["ma_cha"]}
    ma_o = {r["ma_vi_tri"]: r for r in seed["vi_tri"] if r["ma_cha"]}
    vi_tri = od.search_read("stock.location", [("location_id", "child_of", ton), ("id", "!=", ton)],
                            ["barcode", "location_id", "usage"])
    id_vt = {v["id"]: v for v in vi_tri}
    day = [v for v in vi_tri if v["location_id"][0] == ton]
    o = [v for v in vi_tri if v["location_id"][0] != ton]
    day_dung = sum(v["barcode"] in ma_day for v in day)
    o_dung = sum(v["barcode"] in ma_o and id_vt.get(v["location_id"][0], {}).get("barcode") == ma_o[v["barcode"]]["ma_cha"]
                 for v in o)
    ghi("Dãy kệ dưới PL/Stock", SO_DAY, f"{len(day)}" + ("" if day_dung == len(day) else f" ({len(day) - day_dung} lạ)"))
    ghi("Ô kệ trong dãy", SO_O, f"{len(o)}" + ("" if o_dung == len(o) else f" ({len(o) - o_dung} sai dãy hoặc lạ)"))

    sp = od.search_read("product.template", [], ["default_code", "invoice_policy"])
    ghi("Sản phẩm", SO_SP, len(sp))
    ghi(f"Sản phẩm invoice_policy = {HOA_DON_THEO}", len(sp), sum(p["invoice_policy"] == HOA_DON_THEO for p in sp))

    # Lô và tồn: so từng lô với ton_kho.csv (ô, số lượng).
    mong = {(r["ma_sp"], r["so_lo"]): (r["ma_vi_tri"], so(r["so_luong"], True) or 0) for r in seed["ton_kho"]}
    ma_sp = {p["id"]: p["default_code"] for p in od.search_read("product.product", [], ["default_code"])}
    lo = od.search_read("stock.lot", [], ["product_id", "name"])
    quant = od.search_read("stock.quant", [("location_id.usage", "=", "internal"), ("quantity", "!=", 0)],
                           ["product_id", "lot_id", "location_id", "quantity"])
    ma_vt = {v["id"]: v["barcode"] for v in od.search_read("stock.location", [("usage", "=", "internal")], ["barcode"])}
    thuc = {}
    khong_lo = 0
    for q in quant:
        if not q["lot_id"]:
            khong_lo += 1
            continue
        k = (ma_sp.get(q["product_id"][0]), q["lot_id"][1])
        thuc.setdefault(k, {}).setdefault(ma_vt.get(q["location_id"][0]) or q["location_id"][1], 0)
        thuc[k][ma_vt.get(q["location_id"][0]) or q["location_id"][1]] += q["quantity"]
    sai = [k for k, (cho, sl) in mong.items() if thuc.get(k) != {cho: sl}] + [k for k in thuc if k not in mong]
    ngoai_o = sum(1 for k, cho in thuc.items() for b in cho if b not in ma_o)
    ghi("Lô", len(mong), len(lo))
    ghi("Tổng tồn", f"{sum(sl for _, sl in mong.values()):,.0f}", f"{sum(q['quantity'] for q in quant):,.0f}")
    ghi("Lô sai ô hoặc sai số lượng so với ton_kho.csv", 0, len(sai) + khong_lo)
    ghi("Lô ở cấp dãy, PL/Stock hoặc ngoài ô", 0, ngoai_o)

    ma_kh = [r["ma_kh"] for r in seed["khach_hang"]]
    khach = od.search_read("res.partner", [("customer_rank", ">", 0), ("parent_id", "=", False)],
                           ["ref", "pl_min_shelf_life_pct"])
    ghi("Khách", SO_KHACH, len(khach))
    ghi("Khách có pl_min_shelf_life_pct > 0", SO_KHACH, sum((k["pl_min_shelf_life_pct"] or 0) > 0 for k in khach))
    ghi("Khách đúng mã trong khach_hang.csv", len(ma_kh), len({k["ref"] for k in khach} & set(ma_kh)))

    so_don = {r["so_don"] for r in seed["don_ban"]}
    don = od.search_read("sale.order", [], ["client_order_ref", "state"])
    ghi("Đơn bán", len(so_don), len(don))
    ghi("Báo giá chưa xác nhận", len(so_don), sum(d["state"] == "draft" and d["client_order_ref"] in so_don for d in don))

    ghi("Xe", SO_XE, od("pl.vehicle", "search_count", []))
    cd = od("res.config.settings", "default_get", ["default_invoice_policy"])
    ghi("Sales Settings: Invoicing Policy", HOA_DON_THEO, cd.get("default_invoice_policy"))

    rong = max(len(r[0]) for r in kq)
    print(f"| {'Điều kiện':<{rong}} | Mong đợi | Thực tế | Kết quả |")
    print(f"| {'-' * rong} | --- | --- | --- |")
    for ten, m, t, ok in kq:
        print(f"| {ten:<{rong}} | {m} | {t} | {'PASS' if ok else 'FAIL'} |")
    if sai:
        print("  Lô lệch (tối đa 10):", ", ".join(f"{a}/{b}" for a, b in sai[:10]))
    hong = [r[0] for r in kq if not r[3]]
    if hong:
        dung(f"database mới sai {len(hong)} điều: {'; '.join(hong)}. Không thay database chính")
    print("Bước 5: PASS")


# ---------------------------------------------------------------- Bước 6


def tap(od, model, domain, khoa, truong):
    return {khoa(r) for r in od.search_read(model, domain, truong)}


def ten_m2o(od, model, ids):
    ids = [i for i in set(ids) if i]
    if not ids:
        return {}
    return {r["id"]: r["display_name"] for r in od(model, "read", ids, fields=["display_name"],
                                                    context={"active_test": False})}


def cai_dat(od):
    """Giá trị đọc được của res.config.settings (không tạo bản ghi): default_get và các trường related
    company_id.*. many2one đổi sang tên, bỏ html/binary/x2many."""
    f = od("res.config.settings", "fields_get", attributes=["type", "related", "relation"])
    bo = {"html", "binary", "one2many", "many2many", "datetime"}
    v = od("res.config.settings", "default_get", list(f))
    gia_tri = {}
    for ten, x in v.items():
        if f[ten]["type"] in bo:
            continue
        if f[ten]["type"] == "many2one":
            x = ten_m2o(od, f[ten]["relation"], [x]).get(x, False) if x else False
        gia_tri[ten] = x
    ct = od("res.users", "read", [od.uid], fields=["company_id"])[0]["company_id"][0]
    for ten, x in f.items():
        duong = (x.get("related") or "").split(".")
        if ten in v or x["type"] in bo or duong[0] != "company_id" or len(duong) < 2:
            continue
        model, rid, val = "res.company", ct, None
        try:
            for i, phan in enumerate(duong[1:]):
                fm = od.fields(model)
                val = od(model, "read", [rid], fields=[phan])[0][phan]
                if fm[phan]["type"] == "many2one" and i < len(duong) - 2:
                    if not val:
                        break
                    model, rid = od(model, "fields_get", [phan], attributes=["relation"])[phan]["relation"], val[0]
            gia_tri[ten] = val[1] if isinstance(val, list) and len(val) == 2 else val
        except xmlrpc.client.Fault:
            continue
    return gia_tri


def ra_soat(od_cu, od_moi, seed):
    """Những gì có trong DB cũ mà không đến từ seed. Trả về (danh sách chặn, ghi chú)."""
    chan, ghi_chu = {}, []

    def them(muc, ds):
        ds = sorted(str(x) for x in ds)
        if ds:
            chan[muc] = ds

    mod_cu = tap(od_cu, "ir.module.module", [("state", "=", "installed")], lambda r: r["name"], ["name"])
    mod_moi = tap(od_moi, "ir.module.module", [("state", "=", "installed")], lambda r: r["name"], ["name"])
    them("Module cài trong DB cũ, không có trong DB mới", mod_cu - mod_moi)
    if mod_moi - mod_cu:
        ghi_chu.append(f"DB cũ thiếu {len(mod_moi - mod_cu)} module so với DB mới: "
                       f"{', '.join(sorted(m for m in mod_moi - mod_cu if m in MODULE))} (cùng các module phụ thuộc)")

    login_moi = tap(od_moi, "res.users", [], lambda r: r["login"], ["login"])
    them("User khác admin (không có trong DB mới)",
         [f"{r['login']} ({'active' if r['active'] else 'archived'})"
          for r in od_cu.search_read("res.users", [], ["login", "active"]) if r["login"] not in login_moi])

    so_don = sorted({r["so_don"] for r in seed["don_ban"]})
    don = od_cu.search_read("sale.order", [], ["name", "client_order_ref", "state"], order="id")
    them("Đơn bán không thuộc seed", [f"{d['name']} ({d['client_order_ref'] or '-'}, {d['state']})"
                                      for d in don if d["client_order_ref"] not in so_don])
    trang_thai = {}
    for d in don:
        if d["client_order_ref"] in so_don:
            trang_thai[d["state"]] = trang_thai.get(d["state"], 0) + 1
    if trang_thai:
        ghi_chu.append("Đơn seed trong DB cũ theo trạng thái: "
                       + ", ".join(f"{k} {v}" for k, v in sorted(trang_thai.items()))
                       + " (DB mới: draft " + str(len(so_don)) + ")")
    them("Đơn mua", [f"{p['name']} ({p['state']})" for p in od_cu.search_read("purchase.order", [], ["name", "state"])])

    phieu = od_cu.search_read("stock.picking", ["|", ("sale_id", "=", False), ("sale_id.client_order_ref", "not in", so_don)],
                              ["name", "origin", "state"], order="id")
    them("Phiếu kho không thuộc đơn seed", [f"{p['name']} ({p['origin'] or '-'}, {p['state']})" for p in phieu])
    phieu_seed = od_cu("stock.picking", "search_count", [("sale_id.client_order_ref", "in", so_don)])
    if phieu_seed:
        ghi_chu.append(f"Phiếu kho của đơn seed trong DB cũ: {phieu_seed}")

    # Bút toán: khớp theo (sổ, loại, ref) với DB mới. Bút toán định giá tồn đầu kỳ của setup_warehouse có
    # ref là mã sản phẩm nên khớp dù số tiền khác do tồn kho cũ khác seed.
    def chu_ky(r):
        return (r["journal_id"][1] if r["journal_id"] else "", r["move_type"], r["ref"] or "")

    but_moi = tap(od_moi, "account.move", [], chu_ky, ["journal_id", "move_type", "ref"])
    but_cu = od_cu.search_read("account.move", [], ["name", "journal_id", "move_type", "ref", "state"], order="id")
    them("Hóa đơn, bút toán không đến từ seed",
         [f"{m['name']} ({m['move_type']}, {m['journal_id'][1] if m['journal_id'] else '-'}, ref {m['ref'] or '-'}, {m['state']})"
          for m in but_cu if chu_ky(m) not in but_moi])
    if but_cu:
        ghi_chu.append(f"Bút toán trong DB cũ: {len(but_cu)}, khớp DB mới theo (sổ, loại, ref): "
                       f"{sum(chu_ky(m) in but_moi for m in but_cu)}")

    def ma_kho(r, f="warehouse_id"):
        return r[f][1] if r.get(f) else "-"

    cau_hinh = [
        ("Kho", "stock.warehouse", lambda r: r["code"], ["code"]),
        ("Loại thao tác", "stock.picking.type", lambda r: (ma_kho(r), r["sequence_code"]),
         ["warehouse_id", "sequence_code"]),
        ("Vị trí", "stock.location", lambda r: r["complete_name"], ["complete_name"]),
        ("Route", "stock.route", lambda r: r["name"], ["name"]),
        ("Quy tắc kho (stock.rule)", "stock.rule", lambda r: r["name"], ["name"]),
        ("Quy tắc cất hàng", "stock.putaway.rule",
         lambda r: (r["product_id"][1] if r["product_id"] else (r["category_id"][1] if r["category_id"] else "-"),
                    r["location_in_id"][1], r["location_out_id"][1]),
         ["product_id", "category_id", "location_in_id", "location_out_id"]),
    ]
    for ten, model, khoa, truong in cau_hinh:
        them(f"{ten} không có trong DB mới", tap(od_cu, model, [], khoa, truong) - tap(od_moi, model, [], khoa, truong))

    # Bỏ module_<x> khi <x> đã nằm trong phần khác biệt module ở trên, và is_installed_<x> (id module, khác
    # nhau giữa hai database dù cùng cài).
    cd_cu, cd_moi = cai_dat(od_cu), cai_dat(od_moi)
    lech_mod = mod_cu ^ mod_moi
    bo_qua = {k for k in set(cd_cu) | set(cd_moi)
              if k.startswith("is_installed_") or (k.startswith("module_") and k[7:] in lech_mod)}
    khac = [f"{k}: cũ {cd_cu[k]!r}, mới {cd_moi[k]!r}" for k in sorted(set(cd_cu) & set(cd_moi) - bo_qua)
            if cd_cu[k] != cd_moi[k]]
    them("res.config.settings khác giữa DB cũ và DB mới", khac)
    chi_cu = sorted(set(cd_cu) - set(cd_moi) - bo_qua)
    if chi_cu:
        them("res.config.settings chỉ có trong DB cũ", [f"{k} = {cd_cu[k]!r}" for k in chi_cu])
    return chan, ghi_chu


def in_ra_soat(target, chan, ghi_chu):
    if not chan:
        print(f"Không thấy gì trong {target} nằm ngoài seed")
    for muc, ds in chan.items():
        print(f"- {muc}: {len(ds)}")
        for x in ds[:30]:
            print(f"    {x}")
        if len(ds) > 30:
            print(f"    ... và {len(ds) - 30} mục nữa")
    for g in ghi_chu:
        print(f"  Ghi chú: {g}")


# ---------------------------------------------------------------- Bước 7


def backup(target):
    if os.name == "nt":
        lenh = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                str(ROOT / "scripts" / "backup.ps1"), target]
    else:
        lenh = ["bash", str(ROOT / "scripts" / "backup.sh"), target]
    out = chay(lenh)
    print(out.rstrip())
    m = re.search(r"Backup written to (.+)", out)
    if not m:
        dung("không thấy đường dẫn backup trong output của script backup")
    return m.group(1).strip()


def thay_db(ql, url, target, build, mat_khau):
    buoc(7, f"Thay {target} bằng {build}")
    cu = f"{target}_old_{dt.datetime.now():%Y%m%d_%H%M}"
    if ql.co(cu):
        dung(f"đã có database {cu}, chờ 1 phút rồi chạy lại")
    duong = backup(target)
    psql(build, f"DELETE FROM ir_config_parameter WHERE key = '{DAU}'")
    ql.rpc.rename(ql.master, target, cu)
    print(f"Đổi tên {target} -> {cu}")
    try:
        ql.rpc.rename(ql.master, build, target)
    except (xmlrpc.client.Fault, OSError) as e:
        print(f"Đổi tên {build} lỗi ({e}), trả {cu} về {target}", file=sys.stderr)
        ql.rpc.rename(ql.master, cu, target)
        raise
    print(f"Đổi tên {build} -> {target}")
    Odoo(url, target, "admin", mat_khau)
    print(f"\nDatabase chính: {target} (dựng từ seed)\nDatabase cũ: {cu}\nBackup: {duong}")


# ---------------------------------------------------------------- main


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", default=URL)
    p.add_argument("--target", default=DB_CHINH, help="database chính cần thay (mặc định %(default)s)")
    p.add_argument("--build-name", help="database dựng mới (mặc định <target>_new)")
    p.add_argument("--keep-old", action=argparse.BooleanOptionalAction, default=True,
                   help="giữ database chính cũ dưới tên <target>_old_<yyyymmdd_hhmm> (mặc định có)")
    p.add_argument("--yes", action="store_true", help="không hỏi xác nhận")
    p.add_argument("--skip-swap", action="store_true", help="chỉ dựng và kiểm tra database mới, không thay")
    p.add_argument("--dir", type=Path, default=ROOT / "seed" / "demo", help="thư mục bộ seed")
    args = p.parse_args()
    url = args.url.rstrip("/")
    target = args.target
    build = args.build_name or f"{target}_new"
    if build == target:
        dung("--build-name phải khác --target", 2)
    if not args.keep_old:
        dung("script không xóa database: database chính cũ luôn được giữ dưới tên <target>_old_*. "
             "Muốn bỏ thì tự xóa trong database manager sau khi đã kiểm tra", 2)

    seed = {}
    for ten in ("vi_tri", "ton_kho", "khach_hang", "don_ban"):
        path = args.dir / f"{ten}.csv"
        if not path.exists():
            dung(f"thiếu {path}: chạy scripts/gen_seed.py trước", 2)
        seed[ten] = doc_csv(path)

    mat_khau = os.environ.get("ODOO_PASSWORD") or getpass.getpass("Mật khẩu Odoo của admin: ")
    os.environ["ODOO_PASSWORD"] = mat_khau  # cho seed_import.py, setup_warehouse.py
    ql = QuanLyDb(url)
    co_target = ql.co(target)
    if co_target:
        Odoo(url, target, "admin", mat_khau)  # sai mật khẩu thì dừng ngay, trước khi dựng
    print(f"Database chính: {target} ({'có' if co_target else 'chưa có'}), dựng mới: {build}, "
          f"seed: {args.dir.relative_to(ROOT) if args.dir.is_relative_to(ROOT) else args.dir}")
    bat_dau = time.monotonic()

    dung_db(ql, build)
    od = Odoo(url, build, "admin", mat_khau)
    thieu = [m for m in MODULE if not od.search_read("ir.module.module", [("name", "=", m), ("state", "=", "installed")], ["id"])]
    if thieu:
        dung(f"chưa cài được {', '.join(thieu)}")
    nap_seed(build)
    cau_hinh_kho(build)
    od = Odoo(url, build, "admin", mat_khau)  # quyền mới của admin sau setup_warehouse
    gan_barcode(od)
    kiem_tra(od, seed)

    buoc(6, f"Rà soát {target} (chỉ đọc)")
    if not co_target:
        print(f"Chưa có {target}, bỏ qua")
        chan = {}
    else:
        chan, ghi_chu = ra_soat(Odoo(url, target, "admin", mat_khau), od, seed)
        in_ra_soat(target, chan, ghi_chu)

    print(f"\nĐã chạy {time.monotonic() - bat_dau:.0f} giây")
    if args.skip_swap:
        print(f"--skip-swap: dừng ở đây, {build} đã dựng và kiểm tra xong, {target} không đổi")
        return
    if not co_target:
        psql(build, f"DELETE FROM ir_config_parameter WHERE key = '{DAU}'")
        ql.rpc.rename(ql.master, build, target)
        print(f"Đổi tên {build} -> {target}")
        return
    if not args.yes:
        cau = (f"{target} có {sum(len(v) for v in chan.values())} mục không đến từ seed (ở trên). "
               if chan else "") + f"Backup {target}, đổi tên thành {target}_old_*, đưa {build} lên thay?"
        if not hoi(cau):
            dung(f"chưa thay {target}. {build} vẫn còn để xem; chạy lại với --yes để thay", 3)
    thay_db(ql, url, target, build, mat_khau)


if __name__ == "__main__":
    try:
        main()
    except xmlrpc.client.Fault as e:
        dong = [d for d in e.faultString.strip().splitlines() if d.strip()]
        sys.exit(f"Lỗi từ Odoo: {dong[-1] if dong else e.faultString}")
    except (ConnectionError, OSError) as e:
        sys.exit(f"Không kết nối được Odoo: {e}. Kiểm tra docker compose ps và --url")
