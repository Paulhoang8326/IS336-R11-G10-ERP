"""Unit test cho services/vrp.py, chạy bằng Python thuần, không cần Odoo:

    python3 -m unittest discover -s custom_addons/pl_delivery_route/tests -v

File không được tests/__init__.py import nên Odoo không chạy nó khi cài module.
"""

import csv
import random
import sys
import unittest
from pathlib import Path

THU_MUC = Path(__file__).resolve().parent
sys.path.insert(0, str(THU_MUC.parent / "services"))

import vrp  # noqa: E402

ROOT = THU_MUC.parents[2]
SEED = ROOT / "seed" / "demo"
KHO = (10.0274244, 105.7466991)
DOI_XE = [vrp.Xe("XE01", 1500), vrp.Xe("XE02", 1500), vrp.Xe("XE03", 2500), vrp.Xe("XE04", 2500)]


def diem_ngau_nhien(so_diem, seed, tai_min=20, tai_max=300):
    rnd = random.Random(seed)
    return [vrp.Diem(i, KHO[0] + rnd.uniform(-0.06, 0.06), KHO[1] + rnd.uniform(-0.06, 0.06),
                     round(rnd.uniform(tai_min, tai_max), 2), (i,)) for i in range(1, so_diem + 1)]


def doc_seed():
    """Đọc bộ demo: một phiếu xuất mỗi đơn, tải tính như Odoo (cân nặng mỗi đơn vị lẻ làm tròn 4 chữ số)."""
    def doc(ten):
        with open(SEED / f"{ten}.csv", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    sp = {r["ma_sp"]: r for r in doc("san_pham")}
    kh = {r["ma_kh"]: r for r in doc("khach_hang")}
    tai = {}
    for r in doc("don_ban"):
        n = int(sp[r["ma_sp"]]["so_dvt_moi_thung"])
        kg = round(float(sp[r["ma_sp"]]["kg_moi_thung"]) / n, 4)
        sl = int(r["so_luong"]) * (n if r["dvt"] == "thung" else 1)
        tai[(r["ma_kh"], r["so_don"])] = tai.get((r["ma_kh"], r["so_don"]), 0) + sl * kg
    phieu = [{"khach": k, "vi_do": float(kh[k]["vi_do"]), "kinh_do": float(kh[k]["kinh_do"]), "tai_kg": t,
              "phieu": so} for (k, so), t in tai.items()]
    xe = [vrp.Xe(r["ma_xe"], float(r["tai_trong_kg"])) for r in doc("xe")]
    return vrp.gop_theo_khach(phieu), xe


class KiemTraChung:
    """Các bất biến phải đúng với mọi kết quả."""

    def kiem_bat_bien(self, ds_diem, ds_xe, kq):
        xuat_hien = [d for t in kq.tuyen for d in t.diem] + [c.id for c in kq.chua_xep]
        self.assertEqual(sorted(xuat_hien), sorted(d.id for d in ds_diem), "mỗi điểm đúng 1 lần")
        tai_trong = {x.id: x.tai_trong_kg for x in ds_xe}
        tai = {d.id: d.tai_kg for d in ds_diem}
        self.assertEqual(len({t.xe for t in kq.tuyen}), len(kq.tuyen), "mỗi xe tối đa 1 chuyến")
        for t in kq.tuyen:
            self.assertAlmostEqual(t.tai_kg, sum(tai[d] for d in t.diem), places=6)
            self.assertLessEqual(t.tai_kg, tai_trong[t.xe] + 1e-6, f"xe {t.xe} quá tải")
            self.assertEqual(len(t.chang_km), len(t.diem) + 1)
            self.assertAlmostEqual(t.tong_km, sum(t.chang_km), places=9)


class TestVrp(unittest.TestCase, KiemTraChung):
    def test_haversine(self):
        self.assertAlmostEqual(vrp.haversine_km(KHO, KHO), 0.0)
        # 1 độ vĩ ≈ 111,2 km
        self.assertAlmostEqual(vrp.haversine_km((10, 105), (11, 105)), 111.19, delta=0.05)

    def test_moi_diem_dung_mot_lan_va_khong_qua_tai(self):
        for seed in range(20):
            ds = diem_ngau_nhien(60, seed)
            kq = vrp.lap_tuyen(KHO, ds, DOI_XE)
            self.kiem_bat_bien(ds, DOI_XE, kq)

    def test_diem_nang_hon_xe_lon_nhat(self):
        ds = diem_ngau_nhien(30, 1) + [vrp.Diem(999, KHO[0] + 0.01, KHO[1], 3000.0, (999,))]
        kq = vrp.lap_tuyen(KHO, ds, DOI_XE)
        self.kiem_bat_bien(ds, DOI_XE, kq)
        self.assertIn(vrp.ChuaXep(999, vrp.LY_DO_VUOT_TAI), kq.chua_xep)

    def test_khong_du_xe(self):
        # 12 điểm × 1000 kg, 4 xe: mỗi xe chở được 1 hoặc 2 điểm, tối đa 1+1+2+2 = 6 điểm.
        ds = [vrp.Diem(i, KHO[0] + 0.01 * i, KHO[1], 1000.0) for i in range(1, 13)]
        kq = vrp.lap_tuyen(KHO, ds, DOI_XE)
        self.kiem_bat_bien(ds, DOI_XE, kq)
        self.assertEqual(sum(len(t.diem) for t in kq.tuyen), 6)
        self.assertTrue(all(c.ly_do == vrp.LY_DO_THIEU_XE for c in kq.chua_xep))

    def test_thieu_toa_do(self):
        ds = diem_ngau_nhien(5, 2) + [vrp.Diem(99, None, None, 10.0)]
        kq = vrp.lap_tuyen(KHO, ds, DOI_XE)
        self.assertIn(vrp.ChuaXep(99, vrp.LY_DO_THIEU_TOA_DO), kq.chua_xep)

    def test_gop_theo_khach(self):
        phieu = [
            {"khach": 7, "vi_do": 10.0, "kinh_do": 105.7, "tai_kg": 100.0, "phieu": 2},
            {"khach": 7, "vi_do": 10.0, "kinh_do": 105.7, "tai_kg": 50.0, "phieu": 1},
            {"khach": 3, "vi_do": 10.1, "kinh_do": 105.8, "tai_kg": 10.0, "phieu": 5},
        ]
        ds = vrp.gop_theo_khach(phieu)
        self.assertEqual([(d.id, d.tai_kg, d.phieu) for d in ds], [(3, 10.0, (5,)), (7, 150.0, (1, 2))])

    def test_hai_opt_khong_lam_tang_km(self):
        for seed in range(30):
            ds = diem_ngau_nhien(15, seed)
            toa_do = [KHO] + [(d.vi_do, d.kinh_do) for d in ds]
            kc = [[vrp.haversine_km(a, b) * 1.3 for b in toa_do] for a in toa_do]
            tuyen = list(range(1, len(ds) + 1))
            random.Random(seed).shuffle(tuyen)
            moi = vrp.hai_opt(tuyen, kc)
            self.assertEqual(sorted(moi), sorted(tuyen))
            self.assertLessEqual(vrp.do_dai(moi, kc), vrp.do_dai(tuyen, kc) + 1e-9)

    def test_hai_opt_go_cheo(self):
        # Hình vuông đi chéo 1-3-2-4 phải được gỡ thành vòng quanh cạnh.
        toa_do = [(0, 0), (0, 1), (1, 1), (1, 0)]
        kc = [[vrp.haversine_km(a, b) for b in toa_do] for a in toa_do]
        moi = vrp.hai_opt([2, 1, 3], kc)
        self.assertLess(vrp.do_dai(moi, kc), vrp.do_dai([2, 1, 3], kc))

    def test_tat_dinh(self):
        ds = diem_ngau_nhien(60, 7)
        kq1 = vrp.lap_tuyen(KHO, ds, DOI_XE)
        kq2 = vrp.lap_tuyen(KHO, list(reversed(ds)), list(reversed(DOI_XE)))
        self.assertEqual(kq1, kq2)

    def test_tai_bang_nhau_van_tat_dinh(self):
        # Mọi điểm cùng tải và cùng khoảng cách tới kho: chỉ id phá hòa.
        ds = [vrp.Diem(i, KHO[0] + 0.01, KHO[1], 100.0) for i in range(1, 21)]
        self.assertEqual(vrp.lap_tuyen(KHO, ds, DOI_XE), vrp.lap_tuyen(KHO, ds[::-1], DOI_XE))

    def test_khong_co_xe(self):
        ds = diem_ngau_nhien(3, 3)
        kq = vrp.lap_tuyen(KHO, ds, [])
        self.assertEqual(kq.tuyen, [])
        self.assertEqual({c.ly_do for c in kq.chua_xep}, {vrp.LY_DO_THIEU_XE})

    def test_xep_xe_ffd(self):
        gan, khong, qua_tai = vrp.xep_xe([("a", 1400), ("b", 2400), ("c", 2000)], DOI_XE)
        self.assertEqual(gan, {"b": "XE03", "c": "XE04", "a": "XE01"})
        self.assertEqual((khong, qua_tai), ([], False))
        # Ba tuyến trên 1500 kg: tuyến thứ ba không vừa xe 1,5 tấn còn trống -> quá tải.
        self.assertTrue(vrp.xep_xe([("a", 1600), ("b", 1700), ("c", 1800)], DOI_XE)[2])
        # Năm tuyến nhẹ: tuyến thứ năm thiếu xe, không phải quá tải.
        _g, khong, qua_tai = vrp.xep_xe([(k, 10) for k in "abcde"], DOI_XE)
        self.assertEqual((khong, qua_tai), (["e"], False))


class TestSoDiemToiDa(unittest.TestCase, KiemTraChung):
    def test_khong_tuyen_nao_vuot_gioi_han(self):
        for seed in range(10):
            ds = diem_ngau_nhien(60, seed, tai_min=5, tai_max=60)
            for gioi_han in (3, 7, 15, 25):
                kq = vrp.lap_tuyen(KHO, ds, DOI_XE, so_diem_toi_da=gioi_han)
                self.kiem_bat_bien(ds, DOI_XE, kq)
                self.assertTrue(all(len(t.diem) <= gioi_han for t in kq.tuyen), f"seed={seed}, giới hạn {gioi_han}")

    def test_khong_gioi_han_giong_code_cu(self):
        # None, 0 và một giới hạn không bao giờ chạm tới (bằng số điểm) phải cho cùng một kết quả.
        for seed in range(10):
            ds = diem_ngau_nhien(50, seed)
            goc = vrp.lap_tuyen(KHO, ds, DOI_XE)
            self.assertEqual(vrp.lap_tuyen(KHO, ds, DOI_XE, so_diem_toi_da=None), goc)
            self.assertEqual(vrp.lap_tuyen(KHO, ds, DOI_XE, so_diem_toi_da=0), goc)
            self.assertEqual(vrp.lap_tuyen(KHO, ds, DOI_XE, so_diem_toi_da=len(ds)), goc)

    def test_gioi_han_qua_nho(self):
        ds = [vrp.Diem(i, KHO[0] + 0.005 * i, KHO[1], 10.0) for i in range(1, 11)]
        kq = vrp.lap_tuyen(KHO, ds, DOI_XE, so_diem_toi_da=1)
        self.kiem_bat_bien(ds, DOI_XE, kq)
        self.assertEqual(len(kq.tuyen), 4)
        self.assertTrue(all(len(t.diem) == 1 for t in kq.tuyen))
        self.assertEqual(len(kq.chua_xep), 6)
        self.assertEqual({c.ly_do for c in kq.chua_xep}, {vrp.LY_DO_THIEU_XE})


@unittest.skipUnless((SEED / "don_ban.csv").exists(), "không có seed/demo")
class TestSeed(unittest.TestCase, KiemTraChung):
    def test_bo_demo(self):
        ds, xe = doc_seed()
        kq = vrp.lap_tuyen(KHO, ds, xe)
        self.kiem_bat_bien(ds, xe, kq)
        don_081 = [d.id for d in ds if any(p.endswith("-081") for p in d.phieu)]
        self.assertEqual(len(don_081), 1)
        self.assertIn(vrp.ChuaXep(don_081[0], vrp.LY_DO_VUOT_TAI), kq.chua_xep)
        self.assertEqual(kq, vrp.lap_tuyen(KHO, ds, xe))
        # Kết quả trước khi có giới hạn số điểm (PR #6): 3 xe, 16/35/29 điểm, 48,3 km.
        self.assertEqual([(t.xe, len(t.diem)) for t in kq.tuyen], [("XE01", 16), ("XE03", 35), ("XE04", 29)])
        self.assertAlmostEqual(kq.tong_km, 48.3, delta=0.05)

    def test_bo_demo_gioi_han_25_diem(self):
        ds, xe = doc_seed()
        kq = vrp.lap_tuyen(KHO, ds, xe, so_diem_toi_da=25)
        self.kiem_bat_bien(ds, xe, kq)
        self.assertEqual(sorted(t.xe for t in kq.tuyen), ["XE01", "XE02", "XE03", "XE04"])
        self.assertTrue(all(len(t.diem) <= 25 for t in kq.tuyen))
        self.assertEqual([c.ly_do for c in kq.chua_xep], [vrp.LY_DO_VUOT_TAI])


if __name__ == "__main__":
    unittest.main()
