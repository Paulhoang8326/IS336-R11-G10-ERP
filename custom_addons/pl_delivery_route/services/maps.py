"""Tạo link Google Maps chỉ đường (Maps URLs, api=1) cho một chuyến. Python thuần, không import odoo.

Maps URLs: https://www.google.com/maps/dir/?api=1&origin=...&destination=...&waypoints=a|b|...
&travelmode=driving. Theo tài liệu của Google, số waypoint (điểm dừng giữa origin và destination) tối đa
là 9; riêng khi mở trên trình duyệt di động chỉ được 3 (mở bằng app Google Maps hoặc máy tính thì được 9).

Một chuyến là kho → điểm 1 → … → điểm n → kho, tức n + 2 điểm. Một link chứa tối đa 9 + 2 = 11 điểm.
Chuyến dài hơn thì chia thành nhiều đoạn liên tiếp: đoạn sau bắt đầu từ điểm cuối của đoạn trước.
"""

from urllib.parse import quote, urlencode

GOC = "https://www.google.com/maps/dir/"
SO_WAYPOINT_TOI_DA = 9


def toa_do(diem):
    return f"{diem[0]:.6f},{diem[1]:.6f}"


def chia_doan(cac_diem, so_waypoint=SO_WAYPOINT_TOI_DA):
    """Chia dãy điểm thành các đoạn, mỗi đoạn tối đa so_waypoint + 2 điểm, đoạn sau nối tiếp đoạn trước.

    Trả về list (chỉ số đầu, chỉ số cuối) theo chỉ số trong cac_diem, cả hai đầu đều thuộc đoạn.
    """
    if len(cac_diem) < 2:
        return []
    buoc = so_waypoint + 1
    doan, dau = [], 0
    while dau < len(cac_diem) - 1:
        cuoi = min(dau + buoc, len(cac_diem) - 1)
        doan.append((dau, cuoi))
        dau = cuoi
    return doan


def url_chi_duong(cac_diem):
    """Link chỉ đường lái xe qua cac_diem theo đúng thứ tự (điểm đầu là origin, điểm cuối là destination)."""
    tham_so = {"api": "1", "origin": toa_do(cac_diem[0]), "destination": toa_do(cac_diem[-1]),
               "travelmode": "driving"}
    if len(cac_diem) > 2:
        tham_so["waypoints"] = "|".join(toa_do(d) for d in cac_diem[1:-1])
    return GOC + "?" + urlencode(tham_so, quote_via=quote)


def link_chuyen(kho, cac_diem_dung, so_waypoint=SO_WAYPOINT_TOI_DA):
    """Các link của một chuyến kho → điểm dừng → kho.

    Trả về list (số thứ tự điểm dừng đầu, cuối, url). Số thứ tự tính từ 1; 0 và n + 1 là kho.
    """
    cac_diem = [kho] + list(cac_diem_dung) + [kho]
    return [(dau, cuoi, url_chi_duong(cac_diem[dau:cuoi + 1]))
            for dau, cuoi in chia_doan(cac_diem, so_waypoint)]
