"""Unit test cho services/shelf_life.py, chạy bằng Python thuần, không cần Odoo:

    python3 -m unittest discover -s custom_addons/pl_fefo_pick/tests -v

File không được tests/__init__.py import nên Odoo không chạy nó khi cài module.
"""

import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services"))

import shelf_life  # noqa: E402

# Ngày giao 08:00 giờ Việt Nam ngày 29/10/2026, lưu theo UTC như Odoo.
GIAO = dt.datetime(2026, 10, 29, 1, 0)
HAN_540 = 540  # Aquafina 18 tháng


def ngay(n):
    return GIAO + dt.timedelta(days=n)


class TestMinDays(unittest.TestCase):
    def test_lam_tron_len(self):
        self.assertEqual(shelf_life.min_days(50, 540), 270)
        self.assertEqual(shelf_life.min_days(60, 540), 324)
        self.assertEqual(shelf_life.min_days(30, 365), 110)  # 109,5 -> 110
        self.assertEqual(shelf_life.min_days(1, 1), 1)  # 0,01 -> 1
        self.assertEqual(shelf_life.min_days(33, 300), 99)  # đúng 99, không bị float đẩy lên 100

    def test_khong_ap(self):
        self.assertEqual(shelf_life.min_days(0, 540), 0)
        self.assertEqual(shelf_life.min_days(50, 0), 0)
        self.assertEqual(shelf_life.min_days(None, 540), 0)
        self.assertFalse(shelf_life.applies(0, 540))
        self.assertFalse(shelf_life.applies(50, 0))
        self.assertTrue(shelf_life.applies(100, 1))

    def test_100_phan_tram(self):
        self.assertEqual(shelf_life.min_days(100, 540), 540)


class TestMinExpirationDate(unittest.TestCase):
    def test_tinh_tu_ngay_giao(self):
        self.assertEqual(shelf_life.min_expiration_date(GIAO, 50, HAN_540), ngay(270))

    def test_kieu_date(self):
        self.assertEqual(shelf_life.min_expiration_date(dt.date(2026, 10, 29), 60, HAN_540), dt.date(2027, 9, 18))

    def test_khong_ap_tra_none(self):
        self.assertIsNone(shelf_life.min_expiration_date(GIAO, 0, HAN_540))
        self.assertIsNone(shelf_life.min_expiration_date(GIAO, 50, 0))
        self.assertIsNone(shelf_life.min_expiration_date(None, 50, HAN_540))


class TestLotOk(unittest.TestCase):
    def test_dung_bang_nguong_la_dat(self):
        self.assertTrue(shelf_life.lot_ok(ngay(270), GIAO, 50, HAN_540))

    def test_som_hon_nguong_mot_giay_la_khong_dat(self):
        self.assertFalse(shelf_life.lot_ok(ngay(270) - dt.timedelta(seconds=1), GIAO, 50, HAN_540))

    def test_pct_0_moi_lo_chua_het_han_deu_dat(self):
        # Quy tắc không áp, giữ hàng như Odoo chuẩn (Odoo tự loại lô hết hạn trước ngày giao).
        self.assertTrue(shelf_life.lot_ok(ngay(1), GIAO, 0, HAN_540))

    def test_expiration_time_0_bo_qua(self):
        self.assertTrue(shelf_life.lot_ok(ngay(1), GIAO, 60, 0))

    def test_lo_khong_co_han_la_dat(self):
        self.assertTrue(shelf_life.lot_ok(None, GIAO, 60, HAN_540))
        self.assertTrue(shelf_life.lot_ok(False, GIAO, 60, HAN_540))

    def test_ba_lo_aquafina(self):
        # Seed: lô hết hạn 00:00 giờ Việt Nam sau ngày mốc 7, 11, 17 tháng (210, 330, 510 ngày).
        lo = {thang: dt.datetime(2026, 10, 28, 17, 0) + dt.timedelta(days=thang * 30) for thang in (7, 11, 17)}
        dat = {pct: [t for t, han in lo.items() if shelf_life.lot_ok(han, GIAO, pct, HAN_540)]
               for pct in (0, 30, 50, 60)}
        self.assertEqual(dat, {0: [7, 11, 17], 30: [7, 11, 17], 50: [11, 17], 60: [11, 17]})


class TestRemainingPct(unittest.TestCase):
    def test_phan_tram(self):
        self.assertAlmostEqual(shelf_life.remaining_pct(ngay(270), GIAO, HAN_540), 50.0)
        self.assertAlmostEqual(shelf_life.remaining_pct(ngay(540), GIAO, HAN_540), 100.0)

    def test_het_han_thi_am(self):
        self.assertAlmostEqual(shelf_life.remaining_pct(ngay(-54), GIAO, HAN_540), -10.0)

    def test_khong_tinh_duoc(self):
        self.assertIsNone(shelf_life.remaining_pct(None, GIAO, HAN_540))
        self.assertIsNone(shelf_life.remaining_pct(ngay(10), GIAO, 0))

    def test_khop_voi_lot_ok(self):
        for pct in (1, 30, 50, 60, 99, 100):
            for n in range(0, 541, 7):
                han = ngay(n)
                con = shelf_life.remaining_pct(han, GIAO, HAN_540)
                if shelf_life.lot_ok(han, GIAO, pct, HAN_540):
                    self.assertGreaterEqual(con, pct - 1e-9)


if __name__ == "__main__":
    unittest.main()
