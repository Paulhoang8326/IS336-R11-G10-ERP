"""Unit test cho services/maps.py, chạy bằng Python thuần:

    python3 -m unittest discover -s custom_addons/pl_delivery_route/tests -v
"""

import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services"))

import maps  # noqa: E402

KHO = (10.0274244, 105.7466991)


def diem(n):
    return [(10.0 + i / 100, 105.7 + i / 100) for i in range(1, n + 1)]


def doc_url(url):
    q = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
    ds = [q["origin"]] + (q["waypoints"].split("|") if "waypoints" in q else []) + [q["destination"]]
    return q, ds


class TestMaps(unittest.TestCase):
    def test_mot_doan(self):
        links = maps.link_chuyen(KHO, diem(9))
        self.assertEqual(len(links), 1)
        q, ds = doc_url(links[0][2])
        self.assertEqual(q["api"], "1")
        self.assertEqual(q["travelmode"], "driving")
        self.assertEqual(ds, [maps.toa_do(p) for p in [KHO] + diem(9) + [KHO]])
        self.assertIn("%2C", links[0][2])
        self.assertIn("%7C", links[0][2])

    def test_chia_doan_noi_tiep(self):
        for n in (1, 9, 10, 18, 19, 20, 35):
            cac_diem = [KHO] + diem(n) + [KHO]
            links = maps.link_chuyen(KHO, diem(n))
            ghep = []
            for k, (dau, cuoi, url) in enumerate(links):
                q, ds = doc_url(url)
                self.assertLessEqual(len(ds) - 2, maps.SO_WAYPOINT_TOI_DA)
                self.assertEqual(ds, [maps.toa_do(p) for p in cac_diem[dau:cuoi + 1]])
                if k:
                    self.assertEqual(dau, links[k - 1][1], "đoạn sau bắt đầu từ điểm cuối đoạn trước")
                ghep += ds if not k else ds[1:]
            self.assertEqual(ghep, [maps.toa_do(p) for p in cac_diem], f"n={n}")

    def test_so_doan(self):
        self.assertEqual(len(maps.link_chuyen(KHO, diem(9))), 1)
        self.assertEqual(len(maps.link_chuyen(KHO, diem(10))), 2)
        self.assertEqual(len(maps.link_chuyen(KHO, diem(19))), 2)
        self.assertEqual(len(maps.link_chuyen(KHO, diem(20))), 3)


if __name__ == "__main__":
    unittest.main()
