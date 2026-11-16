#!/usr/bin/env python3
"""Tạo database phanlam_seminar3 từ database chính. Database chính không bị sửa.

Trên bản này: nhập 2 bước, xuất 3 bước, admin xem được bút toán, thêm sản phẩm
Dầu ăn Simply tồn 0. Xem scripts/seminar3/README.md.

    python scripts/seminar3/make_seminar_db.py
    python scripts/seminar3/make_seminar_db.py --force         # tạo lại, xóa bản cũ
    python scripts/seminar3/make_seminar_db.py --backup-clean  # lưu bản sạch sau khi check_flow pass
"""

import argparse
import sys
import xmlrpc.client

from chung import DB_CHINH, DB_CLEAN, DB_SEMINAR, MA_SP, TEN_SP, URL, QuanLyDb, ket_noi

GIA_VON = 600000
GIA_BAN = 660000
VAT = 8
HAN_DUNG_NGAY = 18 * 30  # như các mã Dầu ăn khác trong seed


def cau_hinh_kho(od):
    kho = od.search_read("stock.warehouse", [], ["code", "reception_steps", "delivery_steps"], order="id")
    if len(kho) != 1:
        sys.exit(f"Cần đúng 1 kho, đang có {len(kho)}")
    od("stock.warehouse", "write", [kho[0]["id"]], {"reception_steps": "two_steps", "delivery_steps": "pick_pack_ship"})
    r = od("stock.warehouse", "read", [kho[0]["id"]], fields=["code", "reception_steps", "delivery_steps"])[0]
    print(f"Kho {r['code']}: nhập {r['reception_steps']}, xuất {r['delivery_steps']}")


def cho_xem_ke_toan(od):
    """Menu Journal Entries cần group_account_readonly; admin mặc định chỉ có Billing Administrator."""
    g = od.search_read("ir.model.data", [("module", "=", "account"), ("name", "=", "group_account_user")], ["res_id"])
    od("res.users", "write", [od.uid], {"groups_id": [(4, g[0]["res_id"])]})
    print("Admin có Show Full Accounting Features")


def tao_san_pham(od):
    nhom = od.search_read("product.category", [("name", "=", "Dầu ăn")], ["property_valuation"])
    if not nhom or nhom[0]["property_valuation"] != "real_time":
        sys.exit("Nhóm Dầu ăn chưa cấu hình: chạy scripts/setup_warehouse.py trên database chính trước")
    ncc = od.search_read("res.partner", [("ref", "=", "NCC01"), ("name", "=", "Wilmar")], ["id"])
    if not ncc:
        sys.exit("Không có nhà cung cấp Wilmar (NCC01): chạy scripts/seed_import.py trước")
    thue = {t: od.search_read("account.tax", [("type_tax_use", "=", t), ("amount", "=", VAT),
                                              ("amount_type", "=", "percent")], ["id"], order="sequence, id")
            for t in ("sale", "purchase")}
    vals = {
        "name": TEN_SP,
        "default_code": MA_SP,
        "type": "consu",
        "is_storable": True,
        "tracking": "lot",
        "use_expiration_date": True,
        "expiration_time": HAN_DUNG_NGAY,
        "categ_id": nhom[0]["id"],
        "standard_price": GIA_VON,
        "list_price": GIA_BAN,
        "taxes_id": [(6, 0, [t["id"] for t in thue["sale"][:1]])],
        "supplier_taxes_id": [(6, 0, [t["id"] for t in thue["purchase"][:1]])],
        "seller_ids": [(0, 0, {"partner_id": ncc[0]["id"], "price": GIA_VON, "min_qty": 0})],
    }
    tmpl = od("product.template", "create", vals)
    pid = od("product.product", "search", [("product_tmpl_id", "=", tmpl)])[0]
    r = od("product.product", "read", [pid], fields=["display_name", "qty_available", "standard_price"])[0]
    print(f"Sản phẩm: {r['display_name']}, tồn {r['qty_available']:g}, giá vốn {r['standard_price']:,.0f}")

    quy_tac = od("stock.putaway.rule", "search_read", [("category_id", "=", nhom[0]["id"])], fields=["location_out_id"])
    print(f"Quy tắc cất hàng nhóm Dầu ăn: {quy_tac[0]['location_out_id'][1]}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", default=URL)
    p.add_argument("--src", default=DB_CHINH, help="database chính")
    p.add_argument("--db", default=DB_SEMINAR)
    p.add_argument("--force", action="store_true", help="xóa database đích nếu đã có")
    p.add_argument("--backup-clean", action="store_true", help=f"chỉ nhân bản --db thành {DB_CLEAN}")
    args = p.parse_args()
    url = args.url.rstrip("/")
    ql = QuanLyDb(url)

    dich = DB_CLEAN if args.backup_clean else args.db
    nguon = args.db if args.backup_clean else args.src
    if ql.co(dich):
        if not args.force:
            sys.exit(f"Database {dich} đã có. Thêm --force để xóa và tạo lại")
        ql.xoa(dich)
    if args.backup_clean:
        ql.nhan_ban(nguon, dich)
        print(f"Đã lưu {nguon} thành {dich}")
        return

    ql.nhan_ban(nguon, dich)
    print(f"Đã nhân bản {nguon} thành {dich}")
    od = ket_noi(url, dich)
    cau_hinh_kho(od)
    cho_xem_ke_toan(od)
    tao_san_pham(od)


if __name__ == "__main__":
    try:
        main()
    except xmlrpc.client.Fault as e:
        dong = [d for d in e.faultString.strip().splitlines() if d.strip()]
        sys.exit(f"Lỗi từ Odoo: {dong[-1] if dong else e.faultString}")
    except (ConnectionError, OSError) as e:
        sys.exit(f"Không kết nối được Odoo: {e}. Kiểm tra docker compose ps và --url")
