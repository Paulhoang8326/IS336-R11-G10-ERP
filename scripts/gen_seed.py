#!/usr/bin/env python3
"""Sinh bộ dữ liệu demo từ danh mục sản phẩm có sẵn.

Đọc seed/danh_muc/, ghi seed/demo/. Cùng --seed (và cùng tham số) thì ra các
file giống hệt nhau trên mọi máy. Xem docs/seed.md.

    python scripts/gen_seed.py
    python scripts/gen_seed.py --seed 7 --ngay 2026-11-02 --so-don 100
    python scripts/gen_seed.py --nhom "Minimart.giam=4" --xe K1=1500,2500,2500
"""

import argparse
import csv
import datetime as dt
import math
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

NHOM_KHACH = ["Tạp hóa", "Minimart", "Quán ăn", "Khách sạn", "Căn tin KCN"]

# Thông số theo nhóm khách, đổi bằng --nhom "Nhóm.khóa=giá trị".
# Một số: "15"; khoảng: "2-5"; các lựa chọn: "0|7". Tiền tính bằng đồng.
#   ty_le     tỉ lệ số khách (%)
#   han_tt    hạn thanh toán (ngày), chọn ngẫu nhiên trong các giá trị
#   han_muc   hạn mức nợ min-max, chỉ đặt khi hạn thanh toán > 0
#   hsd       hạn dùng tối thiểu (%), 0 = để trống
#   so_dong   số dòng mỗi đơn min-max
#   so_thung  số thùng mỗi dòng min-max
#   ty_le_le  tỉ lệ dòng mua lẻ (%)
#   giam      mức giảm giá trong bảng giá (%), 0 = không có dòng giá riêng
#   thung_gia số thùng tối thiểu để được giá giảm
THONG_SO_NHOM = {
    "Tạp hóa": dict(ty_le=(60,), han_tt=(0, 7), han_muc=(5_000_000, 20_000_000), hsd=(0,),
                    so_dong=(2, 5), so_thung=(1, 3), ty_le_le=(25,), giam=(0,), thung_gia=(0,)),
    "Minimart": dict(ty_le=(20,), han_tt=(15,), han_muc=(30_000_000, 80_000_000), hsd=(50,),
                     so_dong=(5, 10), so_thung=(2, 5), ty_le_le=(0,), giam=(3,), thung_gia=(0,)),
    "Quán ăn": dict(ty_le=(10,), han_tt=(0, 7), han_muc=(5_000_000, 15_000_000), hsd=(0,),
                    so_dong=(2, 4), so_thung=(1, 3), ty_le_le=(25,), giam=(0,), thung_gia=(0,)),
    "Khách sạn": dict(ty_le=(5,), han_tt=(30,), han_muc=(50_000_000, 150_000_000), hsd=(60,),
                      so_dong=(3, 6), so_thung=(1, 4), ty_le_le=(0,), giam=(5,), thung_gia=(1,)),
    "Căn tin KCN": dict(ty_le=(5,), han_tt=(30,), han_muc=(50_000_000, 200_000_000), hsd=(60,),
                        so_dong=(4, 8), so_thung=(3, 8), ty_le_le=(0,), giam=(7,), thung_gia=(5,)),
}

# Khách sạn và căn tin KCN chỉ được giảm giá cho nước; minimart giảm mọi mã.
NHOM_NUOC = ("Nước giải khát", "Nước suối")
PHAM_VI_GIAM = {"Khách sạn": NHOM_NUOC, "Căn tin KCN": NHOM_NUOC}

# Quán ăn và căn tin không mua hàng chăm sóc cá nhân.
HANG_CA_NHAN = ("Bao cao su", "Chăm sóc da", "Chăm sóc răng miệng", "Dao cạo", "Dầu gội, sữa tắm",
                "Khử mùi, tạo kiểu tóc", "Pin", "Xịt phòng, sáp thơm")
KHONG_MUA = {"Quán ăn": HANG_CA_NHAN, "Căn tin KCN": HANG_CA_NHAN}

KHO = [
    dict(ma_kho="K1", ten="Kho Wilmar - Võ Văn Kiệt", vi_do="10.0519744", kinh_do="105.7524569",
         nha_cung_cap="NCC01"),
    dict(ma_kho="K2", ten="Kho tổng - Nguyễn Văn Cừ nối dài", vi_do="10.0274244", kinh_do="105.7466991",
         nha_cung_cap="NCC02 NCC03 NCC04 NCC05 NCC06"),
]

TEN_RIENG = ["An Khang", "Bảo Trân", "Bích Ngọc", "Bình An", "Diễm My", "Đại Lợi", "Gia Huy", "Hiệp Thành",
             "Hòa Bình", "Hoàng Long", "Hồng Nhung", "Hồng Phúc", "Hữu Nghĩa", "Khánh Vy", "Kim Cúc",
             "Kim Ngân", "Kim Phượng", "Mai Lan", "Minh Châu", "Minh Tâm", "Mỹ Linh", "Ngọc Ánh", "Ngọc Hân",
             "Như Ý", "Phú Quý", "Phước Lộc", "Phương Thảo", "Quốc Bảo", "Song Hỷ", "Tài Lộc", "Tấn Phát",
             "Thành Đạt", "Thanh Bình", "Thanh Hương", "Thanh Tâm", "Thiên Phúc", "Thu Hà", "Trung Kiên",
             "Tú Anh", "Vạn Phát"]
XUNG_HO = ["Anh", "Bà", "Chị", "Chú", "Cô", "Dì", "Dượng", "Thím"]
THU = ["Hai", "Ba", "Tư", "Năm", "Sáu", "Bảy", "Tám", "Chín", "Mười", "Út"]
LOAI_QUAN = ["Quán bánh canh", "Quán bún", "Quán cơm", "Quán cơm tấm", "Quán hủ tiếu", "Quán lẩu",
             "Quán nướng", "Quán phở"]
NGANH_KCN = ["Bao bì", "Cơ khí", "Chế biến gạo", "Giày da", "May mặc", "Nhựa", "Thủy sản",
             "Thức ăn chăn nuôi"]
DUONG = ["3 Tháng 2", "30 Tháng 4", "Cách Mạng Tháng 8", "Đề Thám", "Hai Bà Trưng", "Hòa Bình",
         "Hùng Vương", "Lê Hồng Phong", "Lê Lợi", "Lý Tự Trọng", "Mậu Thân", "Nguyễn Trãi",
         "Nguyễn Văn Cừ", "Nguyễn Văn Linh", "Nguyễn Việt Hồng", "Phan Đình Phùng", "Trần Hưng Đạo",
         "Trần Ngọc Quế", "Trần Phú", "Trần Quang Diệu", "Trần Văn Khéo", "Võ Văn Kiệt"]
PHUONG = ["Phường An Bình", "Phường Bình Thủy", "Phường Cái Khế", "Phường Hưng Phú", "Phường Ninh Kiều",
          "Phường Tân An"]


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
        cot = [c.strip() for c in reader.fieldnames]
        reader.fieldnames = cot
        return cot, [{k: (v or "").strip() for k, v in r.items() if k is not None} for r in reader]


def ghi_csv(path, cot, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cot)
        w.writeheader()
        w.writerows(rows)


def chia_ty_le(trong_so, tong):
    """Chia `tong` theo tỉ lệ `trong_so` (dict), phần dư cho phần lẻ lớn nhất."""
    tong_ts = sum(trong_so.values())
    if tong_ts <= 0:
        sys.exit("Tổng tỉ lệ phải lớn hơn 0")
    ket_qua = {k: v * tong // tong_ts for k, v in trong_so.items()}
    du = sorted(trong_so, key=lambda k: -(trong_so[k] * tong % tong_ts))
    for k in du[: tong - sum(ket_qua.values())]:
        ket_qua[k] += 1
    return ket_qua


def so_dvt(sp):
    return max(1, so(sp["so_dvt_moi_thung"], nguyen=True) or 1)


def kg_dong(sp, so_luong, dvt):
    kg = so(sp["kg_moi_thung"]) or 0.0
    return so_luong * kg if dvt == "thung" else so_luong * kg / so_dvt(sp)


def rai_deu(rows, k, rng):
    """Chọn k dòng, rải đều theo nhom_hang để mỗi nhóm hàng đều có mặt."""
    theo_nhom = defaultdict(list)
    for r in rows:
        theo_nhom[r["nhom_hang"]].append(r)
    co_khoa = []
    for nhom in sorted(theo_nhom):
        ds = theo_nhom[nhom]
        rng.shuffle(ds)
        co_khoa += [((i / len(ds), rng.random()), r) for i, r in enumerate(ds)]
    co_khoa.sort(key=lambda x: x[0])
    return [r for _, r in co_khoa[:k]]


def chon_san_pham(san_pham, so_ma, rng):
    theo_ncc = defaultdict(list)
    for r in san_pham:
        theo_ncc[r["ma_ncc"]].append(r)
    if so_ma < len(theo_ncc):
        sys.exit(f"--so-ma phải ít nhất bằng số nhãn ({len(theo_ncc)})")
    so_ma = min(so_ma, len(san_pham))
    chi_tieu = chia_ty_le({ncc: len(ds) for ncc, ds in sorted(theo_ncc.items())}, so_ma)
    for ncc in sorted(chi_tieu):
        if chi_tieu[ncc] == 0:
            lon_nhat = max(sorted(chi_tieu), key=chi_tieu.get)
            chi_tieu[lon_nhat] -= 1
            chi_tieu[ncc] = 1
    chon = []
    for ncc in sorted(theo_ncc):
        # Ưu tiên dòng có số đơn vị mỗi thùng là số thật, không phải ước lượng.
        that = [r for r in theo_ncc[ncc] if "so_dvt_moi_thung" not in r["uoc_luong"].split()]
        uoc = [r for r in theo_ncc[ncc] if "so_dvt_moi_thung" in r["uoc_luong"].split()]
        q = chi_tieu[ncc]
        chon += rai_deu(that, min(q, len(that)), rng)
        if q > len(that):
            chon += rai_deu(uoc, q - len(that), rng)
    return sorted(chon, key=lambda r: r["ma_sp"])


def tao_ten(nhom, rng):
    ong_ba = f"{rng.choice(XUNG_HO)} {rng.choice(THU)}"
    if nhom == "Tạp hóa":
        chu = ong_ba if rng.random() < 0.5 else rng.choice(TEN_RIENG)
        return f"{rng.choice(['Tạp hóa', 'Tiệm tạp hóa'])} {chu}"
    if nhom == "Minimart":
        return f"{rng.choice(['Minimart', 'Siêu thị mini', 'Cửa hàng tiện lợi'])} {rng.choice(TEN_RIENG)}"
    if nhom == "Quán ăn":
        chu = ong_ba if rng.random() < 0.6 else rng.choice(TEN_RIENG)
        return f"{rng.choice(LOAI_QUAN)} {chu}"
    if nhom == "Khách sạn":
        return f"Khách sạn {rng.choice(TEN_RIENG)}"
    return f"Căn tin Công ty {rng.choice(NGANH_KCN)} {rng.choice(TEN_RIENG)}"


def sinh_khach_hang(so_khach, thong_so, khung, rng):
    so_luong = chia_ty_le({n: thong_so[n]["ty_le"][0] for n in NHOM_KHACH}, so_khach)
    nhom_ds = [n for n in NHOM_KHACH for _ in range(so_luong[n])]
    rng.shuffle(nhom_ds)
    lat_min, lat_max, lon_min, lon_max = khung
    da_dung = set()
    khach = []
    for i, nhom in enumerate(nhom_ds, 1):
        ts = thong_so[nhom]
        for _ in range(50):
            ten = tao_ten(nhom, rng)
            if ten not in da_dung:
                break
        goc, stt = ten, 2
        while ten in da_dung:
            ten, stt = f"{goc} {stt}", stt + 1
        da_dung.add(ten)
        so_nha = str(rng.randint(1, 399))
        if rng.random() < 0.3:
            so_nha += f"/{rng.randint(1, 60)}"
        han_tt = rng.choice(ts["han_tt"])
        han_muc = ""
        if han_tt > 0:
            lo, hi = ts["han_muc"]
            han_muc = rng.randint(lo // 1_000_000, hi // 1_000_000) * 1_000_000
        khach.append(dict(
            ma_kh=f"KH{i:04d}",
            ten=ten,
            nhom_khach=nhom,
            dia_chi=f"{so_nha} {rng.choice(DUONG)}",
            phuong=rng.choice(PHUONG),
            thanh_pho="Cần Thơ",
            vi_do=f"{rng.uniform(lat_min, lat_max):.6f}",
            kinh_do=f"{rng.uniform(lon_min, lon_max):.6f}",
            han_thanh_toan_ngay=han_tt,
            han_muc_no=han_muc,
            han_dung_toi_thieu_pct=ts["hsd"][0] or "",
        ))
    return khach


def lam_tron(x):
    return int(x + 0.5)


def sinh_bang_gia(san_pham, thong_so):
    rows = []
    for nhom in NHOM_KHACH:
        giam = thong_so[nhom]["giam"][0]
        if not giam:
            continue
        pham_vi = PHAM_VI_GIAM.get(nhom)
        for sp in san_pham:
            if pham_vi and sp["nhom_hang"] not in pham_vi:
                continue
            rows.append(dict(
                nhom_khach=nhom,
                ma_sp=sp["ma_sp"],
                gia_ban=lam_tron(so(sp["gia_ban"], nguyen=True) * (100 - giam) / 100),
                so_luong_toi_thieu=thong_so[nhom]["thung_gia"][0] * so_dvt(sp),
            ))
    return rows


def sinh_dong(sp_kho, nhom, ts, rng):
    pool = [sp for sp in sp_kho if sp["nhom_hang"] not in KHONG_MUA.get(nhom, ())] or sp_kho
    k = min(len(pool), rng.randint(*ts["so_dong"]))
    dong = []
    for sp in sorted(rng.sample(pool, k), key=lambda s: s["ma_sp"]):
        n = so_dvt(sp)
        if n > 1 and rng.random() * 100 < ts["ty_le_le"][0]:
            dong.append(dict(sp=sp, so_luong=rng.randint(max(1, n // 6), max(1, n // 2)), dvt="le"))
        else:
            dong.append(dict(sp=sp, so_luong=rng.randint(*ts["so_thung"]), dvt="thung"))
    return dong


def tai_don(don):
    return sum(kg_dong(d["sp"], d["so_luong"], d["dvt"]) for d in don["dong"])


def can_tai(don_kho, lo, hi, rng):
    """Chỉnh số thùng cho tới khi tổng tải các đơn nằm trong [lo, hi] kg."""
    def tong():
        return sum(tai_don(d) for d in don_kho)

    def dong_thung():
        return [d for don in don_kho for d in don["dong"] if d["dvt"] == "thung"]

    t = tong()
    if not lo <= t <= hi:
        # Co giãn đều số thùng về giữa khoảng, giữ chênh lệch giữa các nhóm khách.
        tai_le = sum(kg_dong(d["sp"], d["so_luong"], d["dvt"])
                     for don in don_kho for d in don["dong"] if d["dvt"] == "le")
        he_so = ((lo + hi) / 2 - tai_le) / max(t - tai_le, 1e-9)
        for d in dong_thung():
            d["so_luong"] = max(1, int(d["so_luong"] * he_so + 0.5))
        t = tong()
    # Tinh chỉnh từng thùng cho tới khi vào nửa giữa của khoảng, tránh sát biên.
    bien = (hi - lo) / 4
    for _ in range(100_000):
        if lo + bien <= t <= hi - bien:
            return
        if t > hi - bien:
            giam_duoc = [d for d in dong_thung() if d["so_luong"] > 1]
            if giam_duoc:
                d = rng.choices(giam_duoc, weights=[kg_dong(x["sp"], 1, "thung") for x in giam_duoc])[0]
                d["so_luong"] -= 1
            elif t <= hi:
                return
            else:
                bo_duoc = [don for don in don_kho if len(don["dong"]) > 1]
                if not bo_duoc:
                    sys.exit("Không thể giảm tải xuống dưới mức tối đa: thêm xe hoặc giảm --so-don")
                don = rng.choice(bo_duoc)
                don["dong"].pop(rng.randrange(len(don["dong"])))
        else:
            ds = dong_thung()
            if not ds and t >= lo:
                return
            if not ds:
                sys.exit("Không có dòng mua theo thùng để tăng tải")
            rng.choice(ds)["so_luong"] += 1
        t = tong()
    if not lo <= t <= hi:
        sys.exit("Không cân được tải đơn hàng")


def sinh_don_ban(khach, san_pham, kho_cua_ncc, xe, thong_so, args, rng):
    sp_theo_kho = defaultdict(list)
    for sp in san_pham:
        sp_theo_kho[kho_cua_ncc[sp["ma_ncc"]]].append(sp)
    ma_kho = [k["ma_kho"] for k in KHO]
    so_don_kho = chia_ty_le({ma_kho[0]: args.ty_le_k1, ma_kho[1]: 100 - args.ty_le_k1}, args.so_don)
    don = []
    for kho in ma_kho:
        if so_don_kho[kho] > len(khach):
            sys.exit(f"Số đơn của {kho} vượt số khách: mỗi khách tối đa một đơn mỗi kho")
        if so_don_kho[kho] and not sp_theo_kho[kho]:
            sys.exit(f"Kho {kho} không có sản phẩm nào trong bộ demo")
        for kh in rng.sample(khach, so_don_kho[kho]):
            nhom = kh["nhom_khach"]
            don.append(dict(kho=kho, kh=kh, dong=sinh_dong(sp_theo_kho[kho], nhom, thong_so[nhom], rng)))
    for kho in ma_kho:
        suc_chua = sum(xe[kho])
        can_tai([d for d in don if d["kho"] == kho],
                suc_chua * args.tai_min / 100, suc_chua * args.tai_max / 100, rng)
    rng.shuffle(don)

    # Đơn vượt tải: ở kho cuối (K2), khách chưa có đơn ở kho đó, nặng hơn xe lớn nhất.
    kho_vuot = ma_kho[-1]
    da_co = {d["kh"]["ma_kh"] for d in don if d["kho"] == kho_vuot}
    con_lai = [kh for kh in khach if kh["ma_kh"] not in da_co]
    if not con_lai:
        sys.exit("Không còn khách nào chưa có đơn ở kho cuối để làm đơn vượt tải")
    ung_vien = [kh for kh in con_lai if kh["nhom_khach"] == "Căn tin KCN"] or con_lai
    kh = rng.choice(ung_vien)
    nhom = kh["nhom_khach"]
    pool = [sp for sp in sp_theo_kho[kho_vuot] if sp["nhom_hang"] not in KHONG_MUA.get(nhom, ())] \
        or sp_theo_kho[kho_vuot]
    muc = max(xe[kho_vuot]) * args.vuot_tai / 100
    # Lấy hàng nặng để số thùng hợp lý (vài chục thùng mỗi dòng).
    nang = sorted(pool, key=lambda s: (-(so(s["kg_moi_thung"]) or 0), s["ma_sp"]))[:10]
    chon = sorted(rng.sample(nang, min(4, len(nang))), key=lambda s: s["ma_sp"])
    dong = [dict(sp=sp, so_luong=math.ceil(muc / len(chon) / max(so(sp["kg_moi_thung"]) or 0.01, 0.01)),
                 dvt="thung") for sp in chon]
    don.append(dict(kho=kho_vuot, kh=kh, dong=dong))

    ngay = args.ngay.strftime("%Y%m%d")
    for i, d in enumerate(don, 1):
        d["so_don"] = f"DB{ngay}-{i:03d}"
    return don


def doc_nhom(gia_tri, thong_so):
    m = re.fullmatch(r"\s*(.+?)\.(\w+)\s*=\s*(.+?)\s*", gia_tri)
    if not m or m.group(1) not in thong_so or m.group(2) not in thong_so[m.group(1)]:
        sys.exit(f"--nhom không hợp lệ: {gia_tri!r}. Dạng: \"Nhóm.khóa=giá trị\", "
                 f"nhóm trong {NHOM_KHACH}, khóa trong {list(THONG_SO_NHOM['Tạp hóa'])}")
    nhom, khoa, gt = m.groups()
    so_hang = [int(re.sub(r"[._,\s]", "", x)) for x in re.split(r"[|-]", gt)]
    if khoa in ("han_muc", "so_dong", "so_thung") and len(so_hang) == 1:
        so_hang *= 2
    thong_so[nhom][khoa] = tuple(so_hang)


def doc_xe(ds):
    xe = {}
    for muc in ds:
        m = re.fullmatch(r"(\w+)=([\d,]+)", muc)
        if not m:
            sys.exit(f"--xe không hợp lệ: {muc!r}. Dạng: K1=1500,2500")
        xe[m.group(1)] = [int(x) for x in m.group(2).split(",") if x]
    for k in KHO:
        if not xe.get(k["ma_kho"]):
            sys.exit(f"Thiếu xe cho kho {k['ma_kho']}")
    return xe


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--danh-muc", type=Path, default=ROOT / "seed" / "danh_muc", help="thư mục danh mục đầu vào")
    p.add_argument("--out", type=Path, default=ROOT / "seed" / "demo", help="thư mục ghi bộ demo")
    p.add_argument("--seed", type=int, default=336, help="hạt giống ngẫu nhiên (mặc định 336)")
    p.add_argument("--ngay", type=dt.date.fromisoformat, default=dt.date(2026, 10, 20),
                   help="ngày của đơn bán, YYYY-MM-DD (mặc định 2026-10-20)")
    p.add_argument("--so-ma", type=int, default=150, help="số mã hàng (mặc định 150)")
    p.add_argument("--so-khach", type=int, default=300, help="số khách (mặc định 300)")
    p.add_argument("--so-don", type=int, default=80, help="số đơn trong ngày, chưa tính đơn vượt tải (mặc định 80)")
    p.add_argument("--ty-le-k1", type=int, default=50, help="%% số đơn thuộc K1 (mặc định 50)")
    p.add_argument("--tai-min", type=float, default=70, help="tải tối thiểu, %% tải xe của kho (mặc định 70)")
    p.add_argument("--tai-max", type=float, default=85, help="tải tối đa, %% tải xe của kho (mặc định 85)")
    p.add_argument("--vuot-tai", type=float, default=120,
                   help="tải đơn vượt tải, %% xe lớn nhất của K2 (mặc định 120)")
    p.add_argument("--xe", nargs="+", default=["K1=1500,2500", "K2=1500,2500"], metavar="KHO=KG,KG",
                   help="tải trọng xe theo kho (mặc định K1=1500,2500 K2=1500,2500)")
    p.add_argument("--khung", nargs=4, type=float, default=[10.015, 10.055, 105.745, 105.782],
                   metavar=("VD_MIN", "VD_MAX", "KD_MIN", "KD_MAX"), help="khung tọa độ khách")
    p.add_argument("--nhom", action="append", default=[], metavar="NHÓM.KHÓA=GIÁ_TRỊ",
                   help="đổi thông số nhóm khách, ví dụ \"Tạp hóa.han_tt=0|7\" hoặc \"Minimart.so_thung=2-6\"")
    args = p.parse_args()
    if not 0 <= args.ty_le_k1 <= 100 or not 0 < args.tai_min <= args.tai_max:
        sys.exit("--ty-le-k1 phải trong 0-100 và 0 < --tai-min <= --tai-max")
    if args.vuot_tai <= 100:
        sys.exit("--vuot-tai phải lớn hơn 100")

    thong_so = {n: dict(ts) for n, ts in THONG_SO_NHOM.items()}
    for gt in args.nhom:
        doc_nhom(gt, thong_so)
    xe = doc_xe(args.xe)
    rng = random.Random(args.seed)

    cot_sp, danh_muc = doc_csv(args.danh_muc / "san_pham.csv")
    cot_ncc, ncc = doc_csv(args.danh_muc / "nha_cung_cap.csv")
    kho_cua_ncc = {m: k["ma_kho"] for k in KHO for m in k["nha_cung_cap"].split()}
    thieu = sorted({r["ma_ncc"] for r in danh_muc} - set(kho_cua_ncc))
    if thieu:
        sys.exit(f"Nhà cung cấp chưa gán kho: {thieu}")

    san_pham = chon_san_pham(danh_muc, args.so_ma, rng)
    khach = sinh_khach_hang(args.so_khach, thong_so, args.khung, rng)
    bang_gia = sinh_bang_gia(san_pham, thong_so)
    don = sinh_don_ban(khach, san_pham, kho_cua_ncc, xe, thong_so, args, rng)

    args.out.mkdir(parents=True, exist_ok=True)
    ghi_csv(args.out / "san_pham.csv", cot_sp, san_pham)
    ghi_csv(args.out / "nha_cung_cap.csv", cot_ncc, ncc)
    ghi_csv(args.out / "khach_hang.csv",
            ["ma_kh", "ten", "nhom_khach", "dia_chi", "phuong", "thanh_pho", "vi_do", "kinh_do",
             "han_thanh_toan_ngay", "han_muc_no", "han_dung_toi_thieu_pct"], khach)
    ghi_csv(args.out / "bang_gia.csv", ["nhom_khach", "ma_sp", "gia_ban", "so_luong_toi_thieu"], bang_gia)
    ghi_csv(args.out / "kho.csv", ["ma_kho", "ten", "vi_do", "kinh_do", "nha_cung_cap"], KHO)
    xe_rows = []
    for k in KHO:
        for tai in xe[k["ma_kho"]]:
            xe_rows.append(dict(ma_xe=f"XE{len(xe_rows) + 1:02d}",
                                loai_xe=f"Xe tải {tai / 1000:g} tấn".replace(".", ","),
                                tai_trong_kg=tai, ma_kho=k["ma_kho"]))
    ghi_csv(args.out / "xe.csv", ["ma_xe", "loai_xe", "tai_trong_kg", "ma_kho"], xe_rows)
    ghi_csv(args.out / "don_ban.csv", ["so_don", "ngay", "ma_kh", "ma_sp", "so_luong", "dvt", "ma_kho"],
            [dict(so_don=d["so_don"], ngay=args.ngay.isoformat(), ma_kh=d["kh"]["ma_kh"], ma_sp=x["sp"]["ma_sp"],
                  so_luong=x["so_luong"], dvt=x["dvt"], ma_kho=d["kho"])
             for d in don for x in d["dong"]])

    in_tom_tat(args, ncc, san_pham, khach, bang_gia, don, kho_cua_ncc, xe)


def in_tom_tat(args, ncc, san_pham, khach, bang_gia, don, kho_cua_ncc, xe):
    ten_ncc = {r["ma_ncc"]: r["ten"] for r in ncc}
    print(f"Đã ghi 7 file vào {args.out} (seed={args.seed}, ngày {args.ngay.isoformat()})")
    dem_ncc = Counter(sp["ma_ncc"] for sp in san_pham)
    print(f"\nSản phẩm: {len(san_pham)} mã, {len(dem_ncc)} nhãn")
    for m in sorted(dem_ncc):
        print(f"  {m} {ten_ncc.get(m, ''):<18} {dem_ncc[m]:>4}  -> {kho_cua_ncc[m]}")
    dem_nhom = Counter(kh["nhom_khach"] for kh in khach)
    print(f"\nKhách hàng: {len(khach)}")
    for n in NHOM_KHACH:
        print(f"  {n:<12} {dem_nhom[n]:>4}")
    print(f"\nBảng giá: {len(bang_gia)} dòng " +
          ", ".join(f"{n} {c}" for n, c in Counter(r['nhom_khach'] for r in bang_gia).items()))

    don_thuong, vuot = don[:-1], don[-1]
    print(f"\nĐơn bán: {len(don_thuong)} đơn + 1 đơn vượt tải")
    for k in KHO:
        kho = k["ma_kho"]
        ds = [d for d in don_thuong if d["kho"] == kho]
        tai = sum(tai_don(d) for d in ds)
        suc_chua = sum(xe[kho])
        print(f"  {kho}: {len(ds):>3} đơn, {sum(len(d['dong']) for d in ds):>4} dòng, "
              f"{tai:,.1f} kg / {suc_chua:,} kg xe = {tai / suc_chua:.1%} "
              f"(yêu cầu {args.tai_min:g}-{args.tai_max:g}%)")
    print(f"  Dòng mua lẻ: {sum(x['dvt'] == 'le' for d in don_thuong for x in d['dong'])}")
    kg_vuot = tai_don(vuot)
    print(f"  Đơn vượt tải {vuot['so_don']} ({vuot['kho']}, {vuot['kh']['ma_kh']} {vuot['kh']['nhom_khach']}): "
          f"{kg_vuot:,.1f} kg, xe lớn nhất của {vuot['kho']} {max(xe[vuot['kho']]):,} kg")

    mot_kho = all(len({kho_cua_ncc[x["sp"]["ma_ncc"]] for x in d["dong"]} | {d["kho"]}) == 1 for d in don)
    so_don_kh = Counter((d["kh"]["ma_kh"], d["kho"]) for d in don)
    print(f"\nKiểm tra: mỗi đơn một kho {'OK' if mot_kho else 'LỖI'}; "
          f"mỗi khách tối đa 1 đơn mỗi kho {'OK' if max(so_don_kh.values()) == 1 else 'LỖI'}")


if __name__ == "__main__":
    main()
