#!/usr/bin/env python3
"""Nạp bộ dữ liệu demo (seed/demo) vào Odoo 18 qua XML-RPC.

Chỉ dùng thư viện chuẩn. Chạy lại nhiều lần không tạo trùng: bản ghi tìm theo
mã, thiếu thì tạo, có rồi thì cập nhật trường khác đi. Mật khẩu lấy từ biến
môi trường ODOO_PASSWORD, không có thì hỏi. Xem docs/seed.md.

    python scripts/seed_import.py --db demo
    python scripts/seed_import.py --db demo --orders
"""

import argparse
import csv
import datetime as dt
import getpass
import os
import re
import sys
import time
import xmlrpc.client
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Việt Nam dùng UTC+7 quanh năm; Odoo lưu giờ theo UTC.
GIO_VN = 7
GIO_DAT_HANG = 8

CAI_DAT = [
    "group_stock_production_lot",
    "group_stock_packaging",
    "group_product_pricelist",
    "group_stock_multi_locations",
    "account_use_credit_limit",
]
DO_CHINH_XAC_KG = 4


def so(text, nguyen=False):
    """Đọc số kiểu 12.000 / 12,000 / 11,5 / 18.0. Ô trống trả về None.

    Một dấu phân cách đơn lẻ theo sau đúng 3 chữ số được hiểu là phân cách
    hàng nghìn khi trường là số nguyên (giá, số lượng), là dấu thập phân khi
    trường là số thực (kg, tọa độ).
    """
    s = re.sub(r"[\s đ₫%]", "", text or "")
    if not s:
        return None
    if "." in s and "," in s:
        thap_phan = "." if s.rfind(".") > s.rfind(",") else ","
        s = s.replace("," if thap_phan == "." else ".", "").replace(thap_phan, ".")
    elif s.count(".") + s.count(",") > 1:
        s = s.replace(".", "").replace(",", "")
    elif "." in s or "," in s:
        nguyen_phan, phan_le = re.split(r"[.,]", s)
        if nguyen and len(phan_le) == 3:
            s = nguyen_phan + phan_le
        else:
            s = nguyen_phan + "." + phan_le
    gia_tri = float(s)
    return int(round(gia_tri)) if nguyen and gia_tri == int(gia_tri) else gia_tri


def doc_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        reader.fieldnames = [c.strip() for c in reader.fieldnames]
        return [{k: (v or "").strip() for k, v in r.items() if k is not None} for r in reader]


class Odoo:
    def __init__(self, url, db, user, password):
        self.db, self.password = db, password
        common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", allow_none=True)
        self.uid = common.authenticate(db, user, password, {})
        if not self.uid:
            sys.exit(f"Đăng nhập thất bại: kiểm tra --db {db}, --user {user} và mật khẩu")
        self.object = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)
        self._fields = {}

    def __call__(self, model, method, *args, **kw):
        return self.object.execute_kw(self.db, self.uid, self.password, model, method, list(args), kw)

    def fields(self, model):
        if model not in self._fields:
            self._fields[model] = self(model, "fields_get", attributes=["type"])
        return self._fields[model]

    def search_read(self, model, domain, fields, order=None):
        kw = dict(fields=fields, context={"active_test": False})
        if order:
            kw["order"] = order
        return self(model, "search_read", domain, **kw)


class ThongKe:
    def __init__(self):
        self.dem = {}
        self.canh_bao = 0
        self._da_bao = set()

    def them(self, loai, tao=0, sua=0):
        d = self.dem.setdefault(loai, [0, 0])
        d[0] += tao
        d[1] += sua

    def bao(self, thong_diep, khoa=None):
        """In cảnh báo; cùng `khoa` chỉ in một lần."""
        khoa = khoa or thong_diep
        if khoa not in self._da_bao:
            self._da_bao.add(khoa)
            self.canh_bao += 1
            print(f"  CẢNH BÁO: {thong_diep}")


def khac(cu, moi, kieu, ten):
    """Giá trị đọc từ Odoo (`cu`) có khác giá trị muốn ghi (`moi`) không."""
    if ten in ("customer_rank", "supplier_rank"):
        return (cu or 0) < moi
    if kieu == "one2many":
        return False
    if kieu == "many2many":
        ids = set(cu or [])
        for lenh in moi:
            if lenh[0] == 6:
                return ids != set(lenh[2])
            if lenh[0] == 4 and lenh[1] not in ids:
                return True
        return False
    if kieu == "many2one":
        return (cu[0] if cu else False) != (moi or False)
    if kieu in ("float", "monetary"):
        return abs((cu or 0) - (moi or 0)) > 1e-6
    if kieu == "integer":
        return (cu or 0) != (moi or 0)
    return (cu or False) != (moi or False)


def dong_bo(od, tk, loai, model, muc_tieu, domain, khoa, cap_nhat=True):
    """Tạo bản ghi còn thiếu trong một lần create, cập nhật bản ghi đã có.

    muc_tieu: {khóa: vals}; khoa(record) trả về khóa của bản ghi đọc về.
    Trả về {khóa: id}.
    """
    kieu = od.fields(model)
    truong = sorted({f for vals in muc_tieu.values() for f in vals if kieu[f]["type"] != "one2many"})
    da_co = {}
    for r in od.search_read(model, domain, truong):
        da_co.setdefault(khoa(r), r)
    ids, tao, sua = {}, [], 0
    for k, vals in muc_tieu.items():
        r = da_co.get(k)
        if r is None:
            tao.append(k)
            continue
        ids[k] = r["id"]
        if cap_nhat:
            doi = {f: v for f, v in vals.items() if khac(r.get(f), v, kieu[f]["type"], f)}
            if doi:
                od(model, "write", [r["id"]], doi)
                sua += 1
    if tao:
        moi = od(model, "create", [muc_tieu[k] for k in tao])
        ids.update(zip(tao, moi))
    tk.them(loai, len(tao), sua)
    return ids


def chi_giu_truong_co(od, tk, model, vals_list):
    """Bỏ các trường model không có (module chưa cài), cảnh báo một lần."""
    co = od.fields(model)
    for vals in vals_list:
        for f in [f for f in vals if f not in co]:
            tk.bao(f"{model} không có trường {f} (thiếu module?), bỏ qua", (model, f))
            del vals[f]


def bat_cai_dat(od, tk):
    print("Cài đặt")
    co = od.fields("res.config.settings")
    for f in CAI_DAT:
        if f not in co:
            print(f"  Bỏ qua {f}: không có trường này")
    can = [f for f in CAI_DAT if f in co]
    # default_get bỏ sót trường related (account_use_credit_limit): đọc từ bản ghi tạm.
    sid = od("res.config.settings", "create", {})
    hien_tai = od("res.config.settings", "read", [sid], fields=can)[0]
    thieu = [f for f in can if not hien_tai.get(f)]
    if thieu:
        od("res.config.settings", "write", [sid], {f: True for f in thieu})
        try:
            od("res.config.settings", "execute", [sid])
        except xmlrpc.client.Fault as e:
            if "cannot marshal None" not in e.faultString:
                raise
        print(f"  Đã bật: {', '.join(thieu)}")
    tk.them("Cài đặt", 0, len(thieu))

    # Khối lượng mỗi đơn vị lẻ rất nhỏ (vd 0,0567 kg); 2 chữ số mặc định làm sai tải xe.
    dp = od.search_read("decimal.precision", [("name", "=", "Stock Weight")], ["digits"])
    if dp and dp[0]["digits"] < DO_CHINH_XAC_KG:
        od("decimal.precision", "write", [dp[0]["id"]], {"digits": DO_CHINH_XAC_KG})
        print(f"  Độ chính xác khối lượng: {dp[0]['digits']} -> {DO_CHINH_XAC_KG} chữ số")
        tk.them("Cài đặt", 0, 1)
    return max(dp[0]["digits"], DO_CHINH_XAC_KG) if dp else 2


def ten_han_tt(ngay):
    return "Trả ngay" if ngay == 0 else f"{ngay} ngày"


def nap_han_thanh_toan(od, tk, ds_ngay):
    print("Hạn thanh toán")
    muc_tieu = {ten_han_tt(n): {
        "name": ten_han_tt(n),
        "line_ids": [(0, 0, {"value": "percent", "value_amount": 100, "delay_type": "days_after", "nb_days": n})],
    } for n in sorted(ds_ngay)}
    ids = dong_bo(od, tk, "Hạn thanh toán", "account.payment.term", muc_tieu,
                  [("name", "in", list(muc_tieu))], lambda r: r["name"], cap_nhat=False)
    return {n: ids[ten_han_tt(n)] for n in ds_ngay}


def nap_kho(od, tk, kho):
    print("Kho")
    muc_tieu = {r["ma_kho"]: {"name": r["ten"], "code": r["ma_kho"]} for r in kho}
    ids = dong_bo(od, tk, "Kho", "stock.warehouse", muc_tieu, [("code", "in", list(muc_tieu))],
                  lambda r: r["code"], cap_nhat=False)
    print("  Tọa độ kho chưa nạp; nhập/xuất 2 bước và ô kệ làm ở STT 16-17")
    return ids


def nap_nha_cung_cap(od, tk, ncc, han_tt):
    print("Nhà cung cấp")
    muc_tieu = {r["ma_ncc"]: {
        "name": r["ten"],
        "ref": r["ma_ncc"],
        "is_company": True,
        "supplier_rank": 1,
        "property_supplier_payment_term_id": han_tt[so(r["han_thanh_toan_ngay"], True) or 0],
    } for r in ncc}
    return dong_bo(od, tk, "Nhà cung cấp", "res.partner", muc_tieu,
                   [("ref", "in", list(muc_tieu)), ("parent_id", "=", False)], lambda r: r["ref"])


def tim_thue(od):
    cong_ty = od("res.users", "read", [od.uid], fields=["company_id"])[0]["company_id"][0]
    thue = {}
    for t in od.search_read("account.tax", [("type_tax_use", "in", ["sale", "purchase"]),
                                            ("amount_type", "=", "percent"),
                                            ("company_id", "=", cong_ty), ("active", "=", True)],
                            ["type_tax_use", "amount"], order="sequence, id"):
        thue.setdefault((t["type_tax_use"], round(t["amount"], 4)), t["id"])
    return thue


def nap_san_pham(od, tk, san_pham, ncc_ids, digits_kg):
    print("Sản phẩm")
    goc = od.search_read("ir.model.data", [("module", "=", "product"), ("name", "=", "product_category_all")],
                         ["res_id"])
    cha = goc[0]["res_id"] if goc else False
    nhom = sorted({r["nhom_hang"] for r in san_pham})
    nhom_ids = dong_bo(od, tk, "Nhóm hàng", "product.category", {n: {"name": n, "parent_id": cha} for n in nhom},
                       [("name", "in", nhom), ("parent_id", "=", cha)], lambda r: r["name"], cap_nhat=False)

    thue = tim_thue(od)

    def ma_thue(loai, pct):
        t = thue.get((loai, round(float(pct or 0), 4)))
        if not t:
            tk.bao(f"không có thuế {'bán' if loai == 'sale' else 'mua'} {float(pct or 0):g}%, để trống "
                   f"(database cần bộ tài khoản Việt Nam)", (loai, pct))
        return [(6, 0, [t] if t else [])]

    muc_tieu = {}
    for r in san_pham:
        n = max(1, so(r["so_dvt_moi_thung"], True) or 1)
        vat = so(r["vat_pct"])
        han_dung = so(r["han_dung_thang"], True)
        vals = {
            "name": r["ten"],
            "default_code": r["ma_sp"],
            "type": "consu",
            "is_storable": True,
            "tracking": "lot",
            "use_expiration_date": True,
            "list_price": so(r["gia_ban"], True) or 0,
            "standard_price": so(r["gia_nhap"], True) or 0,
            "barcode": r["ma_vach_le"] or False,
            "weight": round((so(r["kg_moi_thung"]) or 0) / n, digits_kg),
            "categ_id": nhom_ids[r["nhom_hang"]],
            "taxes_id": ma_thue("sale", vat),
            "supplier_taxes_id": ma_thue("purchase", vat),
        }
        if han_dung:
            vals["expiration_time"] = han_dung * 30
        muc_tieu[r["ma_sp"]] = vals
    chi_giu_truong_co(od, tk, "product.template", muc_tieu.values())
    tmpl = dong_bo(od, tk, "Sản phẩm", "product.template", muc_tieu,
                   [("default_code", "in", list(muc_tieu))], lambda r: r["default_code"])

    bien_the = {r["product_tmpl_id"][0]: r["id"] for r in od.search_read(
        "product.product", [("product_tmpl_id", "in", list(tmpl.values()))], ["product_tmpl_id"])}
    sp = {r["ma_sp"]: dict(tmpl=tmpl[r["ma_sp"]], id=bien_the[tmpl[r["ma_sp"]]],
                           n=max(1, so(r["so_dvt_moi_thung"], True) or 1)) for r in san_pham}

    print("Quy cách đóng gói")
    muc_tieu = {}
    for r in san_pham:
        x = sp[r["ma_sp"]]
        if x["n"] > 1:
            muc_tieu[x["id"]] = {"name": f"Thùng {x['n']}", "product_id": x["id"], "qty": x["n"],
                                 "barcode": r["ma_vach_thung"] or False}
    thung = dong_bo(od, tk, "Quy cách thùng", "product.packaging", muc_tieu,
                    [("product_id", "in", list(muc_tieu)), ("name", "=like", "Thùng %")],
                    lambda r: r["product_id"][0])
    for x in sp.values():
        x["thung"] = thung.get(x["id"])

    print("Giá nhập theo nhà cung cấp")
    muc_tieu = {}
    for r in san_pham:
        if r["ma_ncc"] not in ncc_ids:
            tk.bao(f"{r['ma_sp']}: không có nhà cung cấp {r['ma_ncc']}")
            continue
        k = (ncc_ids[r["ma_ncc"]], sp[r["ma_sp"]]["tmpl"])
        muc_tieu[k] = {"partner_id": k[0], "product_tmpl_id": k[1], "price": so(r["gia_nhap"], True) or 0,
                       "min_qty": 0}
    dong_bo(od, tk, "Giá nhập NCC", "product.supplierinfo", muc_tieu,
            [("product_tmpl_id", "in", [x["tmpl"] for x in sp.values()])],
            lambda r: (r["partner_id"][0], r["product_tmpl_id"][0] if r["product_tmpl_id"] else False))
    return sp


def nap_bang_gia(od, tk, bang_gia, ds_nhom, sp):
    print("Bảng giá")
    ten = {n: f"Giá sỉ - {n}" for n in ds_nhom}
    pl = dong_bo(od, tk, "Bảng giá", "product.pricelist", {t: {"name": t} for t in ten.values()},
                 [("name", "in", list(ten.values()))], lambda r: r["name"], cap_nhat=False)
    pl = {n: pl[t] for n, t in ten.items()}
    muc_tieu = {}
    for r in bang_gia:
        if r["ma_sp"] not in sp:
            tk.bao(f"bang_gia.csv: không có sản phẩm {r['ma_sp']}, bỏ qua", ("bg", r["ma_sp"]))
            continue
        sl = so(r["so_luong_toi_thieu"], True) or 0
        k = (pl[r["nhom_khach"]], sp[r["ma_sp"]]["tmpl"], float(sl))
        muc_tieu[k] = {"pricelist_id": k[0], "applied_on": "1_product", "product_tmpl_id": k[1],
                       "compute_price": "fixed", "fixed_price": so(r["gia_ban"], True) or 0, "min_quantity": sl}
    dong_bo(od, tk, "Dòng bảng giá", "product.pricelist.item", muc_tieu,
            [("pricelist_id", "in", list(pl.values())), ("applied_on", "=", "1_product")],
            lambda r: (r["pricelist_id"][0], r["product_tmpl_id"][0] if r["product_tmpl_id"] else False,
                       float(r["min_quantity"])))
    return pl


def nap_khach_hang(od, tk, khach, han_tt, bang_gia_ids):
    print("Khách hàng")
    ds_nhom = list(dict.fromkeys(r["nhom_khach"] for r in khach))
    nhan = dong_bo(od, tk, "Nhãn khách", "res.partner.category", {n: {"name": n} for n in ds_nhom},
                   [("name", "in", ds_nhom)], lambda r: r["name"], cap_nhat=False)
    vn = od.search_read("res.country", [("code", "=", "VN")], ["id"])
    truong = od.fields("res.partner")
    co_hsd = "pl_min_shelf_life_pct" in truong
    if not co_hsd:
        tk.bao("res.partner chưa có trường pl_min_shelf_life_pct, chưa ghi hạn dùng tối thiểu của khách")
    co_han_muc = "credit_limit" in truong and "use_partner_credit_limit" in truong
    if not co_han_muc:
        tk.bao("res.partner không có credit_limit (thiếu module account hoặc quyền kế toán), bỏ hạn mức nợ")

    muc_tieu = {}
    for r in khach:
        vals = {
            "name": r["ten"],
            "ref": r["ma_kh"],
            "is_company": True,
            "customer_rank": 1,
            "category_id": [(4, nhan[r["nhom_khach"]])],
            "street": r["dia_chi"],
            "street2": r["phuong"],
            "city": r["thanh_pho"],
            "country_id": vn[0]["id"] if vn else False,
            "partner_latitude": so(r["vi_do"]) or 0,
            "partner_longitude": so(r["kinh_do"]) or 0,
            "property_payment_term_id": han_tt[so(r["han_thanh_toan_ngay"], True) or 0],
            "property_product_pricelist": bang_gia_ids[r["nhom_khach"]],
        }
        if co_han_muc:
            han_muc = so(r["han_muc_no"], True)
            vals["use_partner_credit_limit"] = bool(han_muc)
            if han_muc:
                vals["credit_limit"] = han_muc
        if co_hsd:
            vals["pl_min_shelf_life_pct"] = so(r["han_dung_toi_thieu_pct"]) or 0
        muc_tieu[r["ma_kh"]] = vals
    return dong_bo(od, tk, "Khách hàng", "res.partner", muc_tieu,
                   [("ref", "in", list(muc_tieu)), ("parent_id", "=", False)], lambda r: r["ref"])


def nap_don_ban(od, tk, don_ban, kh_ids, kho_ids, sp):
    print("Đơn bán (báo giá)")
    theo_so = {}
    for r in don_ban:
        theo_so.setdefault(r["so_don"], []).append(r)
    da_co = {r["client_order_ref"] for r in od.search_read(
        "sale.order", [("client_order_ref", "in", list(theo_so))], ["client_order_ref"])}
    moi = []
    for so_don, dong in theo_so.items():
        if so_don in da_co:
            continue
        dau = dong[0]
        if dau["ma_kh"] not in kh_ids or dau["ma_kho"] not in kho_ids:
            tk.bao(f"{so_don}: không có khách {dau['ma_kh']} hoặc kho {dau['ma_kho']}, bỏ qua")
            continue
        thieu = [r["ma_sp"] for r in dong if r["ma_sp"] not in sp]
        if thieu:
            tk.bao(f"{so_don}: không có sản phẩm {', '.join(thieu)}, bỏ qua")
            continue
        lines = []
        for r in dong:
            x = sp[r["ma_sp"]]
            sl = so(r["so_luong"], True) or 0
            line = {"product_id": x["id"], "product_uom_qty": sl}
            if r["dvt"] == "thung":
                line["product_uom_qty"] = sl * x["n"]
                if x["thung"]:
                    line["product_packaging_id"] = x["thung"]
            lines.append((0, 0, line))
        ngay = dt.datetime.combine(dt.date.fromisoformat(dau["ngay"]), dt.time(GIO_DAT_HANG))
        moi.append({
            "partner_id": kh_ids[dau["ma_kh"]],
            "client_order_ref": so_don,
            "date_order": (ngay - dt.timedelta(hours=GIO_VN)).strftime("%Y-%m-%d %H:%M:%S"),
            "warehouse_id": kho_ids[dau["ma_kho"]],
            "order_line": lines,
        })
    if moi:
        od("sale.order", "create", moi)
    if da_co:
        print(f"  Bỏ qua {len(da_co)} đơn đã có")
    tk.them("Báo giá", len(moi), 0)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", default="http://localhost:8069")
    p.add_argument("--db", required=True)
    p.add_argument("--user", default="admin")
    p.add_argument("--dir", type=Path, default=ROOT / "seed" / "demo", help="thư mục bộ demo")
    p.add_argument("--orders", action="store_true", help="nạp cả don_ban.csv thành báo giá")
    args = p.parse_args()

    du_lieu = {}
    for ten in ["kho", "nha_cung_cap", "san_pham", "bang_gia", "khach_hang", "xe"] + (
            ["don_ban"] if args.orders else []):
        path = args.dir / f"{ten}.csv"
        if not path.exists():
            sys.exit(f"Thiếu {path}: chạy scripts/gen_seed.py trước")
        du_lieu[ten] = doc_csv(path)

    password = os.environ.get("ODOO_PASSWORD") or getpass.getpass(f"Mật khẩu Odoo của {args.user}: ")
    bat_dau = time.monotonic()
    od = Odoo(args.url.rstrip("/"), args.db, args.user, password)
    tk = ThongKe()

    digits_kg = bat_cai_dat(od, tk)
    kho_ids = nap_kho(od, tk, du_lieu["kho"])
    han_tt = nap_han_thanh_toan(od, tk, {so(r["han_thanh_toan_ngay"], True) or 0
                                         for r in du_lieu["nha_cung_cap"] + du_lieu["khach_hang"]})
    ncc_ids = nap_nha_cung_cap(od, tk, du_lieu["nha_cung_cap"], han_tt)
    sp = nap_san_pham(od, tk, du_lieu["san_pham"], ncc_ids, digits_kg)
    ds_nhom = list(dict.fromkeys([r["nhom_khach"] for r in du_lieu["khach_hang"]] +
                                 [r["nhom_khach"] for r in du_lieu["bang_gia"]]))
    bang_gia_ids = nap_bang_gia(od, tk, du_lieu["bang_gia"], ds_nhom, sp)
    kh_ids = nap_khach_hang(od, tk, du_lieu["khach_hang"], han_tt, bang_gia_ids)
    if args.orders:
        nap_don_ban(od, tk, du_lieu["don_ban"], kh_ids, kho_ids, sp)
    print(f"Bỏ qua xe.csv ({len(du_lieu['xe'])} xe): chờ module giao hàng")

    print(f"\n{'Loại':<20} {'Tạo mới':>8} {'Cập nhật':>9}")
    for loai, (tao, sua) in tk.dem.items():
        print(f"{loai:<20} {tao:>8} {sua:>9}")
    print(f"Cảnh báo: {tk.canh_bao}")
    print(f"Thời gian: {time.monotonic() - bat_dau:.1f} giây")


if __name__ == "__main__":
    try:
        main()
    except xmlrpc.client.Fault as e:
        dong = [d for d in e.faultString.strip().splitlines() if d.strip()]
        sys.exit(f"Lỗi từ Odoo: {dong[-1] if dong else e.faultString}")
    except (ConnectionError, OSError) as e:
        sys.exit(f"Không kết nối được Odoo: {e}. Kiểm tra docker compose ps và --url")
