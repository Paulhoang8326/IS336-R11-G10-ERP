#!/usr/bin/env python3
"""Cấu hình kho cho database đã nạp seed (chạy sau seed_import.py), qua XML-RPC.

Chạy lại nhiều lần không đổi gì thêm. Lần đầu đổi định giá của các nhóm hàng sang
FIFO + Automated: Odoo xuất rồi nhập lại tồn hiện có, sinh một bút toán cho mỗi
sản phẩm còn tồn (Nợ 1560 / Có 1510). Mật khẩu lấy từ ODOO_PASSWORD, không có thì hỏi.

    python scripts/setup_warehouse.py --db pl_moc
"""

import argparse
import collections
import getpass
import os
import sys
import xmlrpc.client
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from seed_import import Odoo, ThongKe, bat_tuy_chon, cong_ty, doc_csv, dong_bo, khac  # noqa: E402

CAI_DAT = [
    "group_stock_multi_locations",  # Storage Locations
    "group_stock_adv_location",  # Multi-Step Routes
    "group_stock_production_lot",  # Lots & Serial Numbers
    "module_product_expiry",  # Expiration Dates
    "group_stock_tracking_lot",  # Packages
]

# Nhà phân phối mua bán hàng hóa nên tồn kho vào 1560, không dùng 1550 (thành phẩm) mặc định của l10n_vn.
TK_TON_KHO = "1560"
# l10n_vn không có sẵn hai tài khoản trung gian. Odoo cấn trừ chúng với hóa đơn nên phải cho đối soát.
TK_NHAP = "1510"
TK_XUAT = "1570"
TK_KIEM_KE = "13811"

NHOM_THUC_PHAM = [
    "Bánh kẹo", "Bột", "Bột ngọt", "Cà phê", "Dầu ăn", "Gạo, nếp", "Hạt nêm, gia vị", "Mì, nui, bánh tráng",
    "Nước giải khát", "Nước mắm, mắm nêm", "Nước suối", "Nước tương, nước chấm, giấm", "Sữa, thức uống cacao",
    "Tương, xốt, sa tế",
]
# Nhóm hàng cất vào đúng một ô; nhóm khác cất vào dãy của nhà cung cấp có nhiều mã nhất trong nhóm.
O_CUA_NHOM = {"Dầu ăn": "A-01-1"}
O_BAT_BUOC = ["A-01-1", "A-02-1"]


def tim_tai_khoan(od):
    ma = [TK_TON_KHO, TK_NHAP, TK_XUAT, TK_KIEM_KE]
    tk = {a["code"]: a for a in od.search_read("account.account", [("code", "in", ma)], ["code", "reconcile"])}
    thieu = [m for m in ma if m not in tk]
    if thieu:
        sys.exit(f"Thiếu tài khoản {', '.join(thieu)}: database cần bộ tài khoản Việt Nam (docs/seed.md)")
    return tk


def cho_doi_soat(od, tk, tai_khoan):
    print("Tài khoản trung gian")
    can = [tai_khoan[m]["id"] for m in (TK_NHAP, TK_XUAT) if not tai_khoan[m]["reconcile"]]
    if can:
        od("account.account", "write", can, {"reconcile": True})
    tk.them("Tài khoản", 0, len(can))


def tim_nhom(od, ten):
    goc = od.search_read("ir.model.data", [("module", "=", "product"), ("name", "=", "product_category_all")],
                         ["res_id"])[0]["res_id"]
    return {c["name"]: c["id"] for c in od.search_read(
        "product.category", [("name", "in", ten), ("parent_id", "=", goc)], ["name"])}


def nap_nhom_hang(od, tk, nhom_ids, tai_khoan):
    """FEFO, FIFO, Automated. Ghi cả tài khoản cùng định giá trong một lệnh để Odoo dùng ngay khi nhập lại tồn."""
    print("Nhóm hàng có hạn dùng")
    fefo = od.search_read("product.removal", [("method", "=", "fefo")], ["id"])
    if not fefo:
        sys.exit("Không có chiến lược xuất FEFO: database chưa cài product_expiry")
    muc_tieu = {
        "removal_strategy_id": fefo[0]["id"],
        "property_cost_method": "fifo",
        "property_valuation": "real_time",
        "property_stock_valuation_account_id": tai_khoan[TK_TON_KHO]["id"],
        "property_stock_account_input_categ_id": tai_khoan[TK_NHAP]["id"],
        "property_stock_account_output_categ_id": tai_khoan[TK_XUAT]["id"],
    }
    kieu = od.fields("product.category")
    sua = 0
    for r in od.search_read("product.category", [("id", "in", list(nhom_ids.values()))], list(muc_tieu)):
        doi = {f: v for f, v in muc_tieu.items() if khac(r.get(f), v, kieu[f]["type"], f)}
        if doi:
            od("product.category", "write", [r["id"]], doi)
            sua += 1
    tk.them("Nhóm hàng", 0, sua)


def nap_kiem_ke(od, tk, tai_khoan):
    print("Vị trí kiểm kê")
    tkk = tai_khoan[TK_KIEM_KE]["id"]
    sua = 0
    for r in od.search_read("stock.location", [("usage", "=", "inventory"), ("scrap_location", "=", False),
                                               ("company_id", "=", cong_ty(od))],
                            ["valuation_in_account_id", "valuation_out_account_id"]):
        doi = {f: tkk for f in ("valuation_in_account_id", "valuation_out_account_id")
               if khac(r[f], tkk, "many2one", f)}
        if doi:
            od("stock.location", "write", [r["id"]], doi)
            sua += 1
    tk.them("Vị trí kiểm kê", 0, sua)


def nap_quy_tac_nhom(od, tk, ton, nhom_ids, san_pham, vi_tri):
    """Quy tắc theo nhóm hàng cho sản phẩm chưa có quy tắc riêng. Quy tắc theo sản phẩm của seed được Odoo xét trước."""
    print("Quy tắc cất hàng theo nhóm")
    ma = O_BAT_BUOC + list(O_CUA_NHOM.values()) + [x["ma_vi_tri"] for x in vi_tri if not x["ma_cha"]]
    vt = {r["barcode"]: r["id"] for r in od.search_read(
        "stock.location", [("barcode", "in", ma), ("id", "child_of", ton)], ["barcode"])}
    thieu = sorted(set(ma) - set(vt))
    if thieu:
        sys.exit(f"Thiếu vị trí {', '.join(thieu)}: chạy scripts/seed_import.py trước")

    day_cua_ncc = {x["ma_ncc"]: x["ma_vi_tri"] for x in vi_tri if not x["ma_cha"]}
    dem = collections.Counter((r["nhom_hang"], r["ma_ncc"]) for r in san_pham)
    muc_tieu = {}
    for ten, cid in nhom_ids.items():
        if ten in O_CUA_NHOM:
            dich, phu = O_CUA_NHOM[ten], "no"
        else:
            ncc = max(sorted(n for t, n in dem if t == ten), key=lambda n: dem[(ten, n)])
            dich, phu = day_cua_ncc[ncc], "last_used"
        muc_tieu[cid] = {"category_id": cid, "location_in_id": ton, "location_out_id": vt[dich], "sublocation": phu}
    dong_bo(od, tk, "Quy tắc theo nhóm", "stock.putaway.rule", muc_tieu,
            [("location_in_id", "=", ton), ("category_id", "in", list(muc_tieu))], lambda r: r["category_id"][0])


def nap_san_pham(od, tk, nhom_ids):
    """Thực phẩm, đồ uống theo lô và có hạn dùng. Sản phẩm seed đã đúng sẵn, phần này giữ cho sản phẩm thêm sau."""
    print("Sản phẩm thực phẩm, đồ uống")
    can = od.search_read("product.template", [
        ("categ_id", "in", [nhom_ids[n] for n in NHOM_THUC_PHAM if n in nhom_ids]), ("is_storable", "=", True),
        "|", ("tracking", "!=", "lot"), ("use_expiration_date", "=", False)], ["id"])
    if can:
        od("product.template", "write", [r["id"] for r in can], {"tracking": "lot", "use_expiration_date": True})
    tk.them("Sản phẩm", 0, len(can))


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", default="http://localhost:8069")
    p.add_argument("--db", required=True)
    p.add_argument("--user", default="admin")
    p.add_argument("--dir", type=Path, default=ROOT / "seed" / "demo", help="thư mục bộ demo")
    args = p.parse_args()

    password = os.environ.get("ODOO_PASSWORD") or getpass.getpass(f"Mật khẩu Odoo của {args.user}: ")
    od = Odoo(args.url.rstrip("/"), args.db, args.user, password)
    tk = ThongKe()
    san_pham = doc_csv(args.dir / "san_pham.csv")
    vi_tri = doc_csv(args.dir / "vi_tri.csv")

    print("Cài đặt")
    bat_tuy_chon(od, tk, CAI_DAT)

    ct = cong_ty(od)
    kho = od.search_read("stock.warehouse", [("company_id", "=", ct)],
                         ["code", "lot_stock_id", "reception_steps", "delivery_steps"], order="id")
    if len(kho) != 1:
        sys.exit(f"Cần đúng 1 kho, đang có {len(kho)}")
    ton = kho[0]["lot_stock_id"][0]

    tai_khoan = tim_tai_khoan(od)
    cho_doi_soat(od, tk, tai_khoan)
    ten_nhom = sorted({r["nhom_hang"] for r in san_pham})
    nhom_ids = tim_nhom(od, ten_nhom)
    thieu = sorted(set(ten_nhom) - set(nhom_ids))
    if thieu:
        sys.exit(f"Thiếu nhóm hàng {', '.join(thieu)}: chạy scripts/seed_import.py trước")

    nap_nhom_hang(od, tk, nhom_ids, tai_khoan)
    nap_kiem_ke(od, tk, tai_khoan)
    nap_quy_tac_nhom(od, tk, ton, nhom_ids, san_pham, vi_tri)
    nap_san_pham(od, tk, nhom_ids)

    print(f"\nKho {kho[0]['code']} giữ nguyên: nhập {kho[0]['reception_steps']}, xuất {kho[0]['delivery_steps']}")
    print(f"{'Loại':<20} {'Tạo mới':>8} {'Cập nhật':>9}")
    for loai, (tao, sua) in tk.dem.items():
        print(f"{loai:<20} {tao:>8} {sua:>9}")


if __name__ == "__main__":
    try:
        main()
    except xmlrpc.client.Fault as e:
        dong = [d for d in e.faultString.strip().splitlines() if d.strip()]
        sys.exit(f"Lỗi từ Odoo: {dong[-1] if dong else e.faultString}")
    except (ConnectionError, OSError) as e:
        sys.exit(f"Không kết nối được Odoo: {e}. Kiểm tra docker compose ps và --url")
