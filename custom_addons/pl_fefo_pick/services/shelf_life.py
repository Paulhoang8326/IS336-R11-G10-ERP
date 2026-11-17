"""Hạn dùng tối thiểu khi giao, viết bằng Python thuần để unit test không cần Odoo.

Tổng hạn dùng của lô lấy theo `expiration_time` của sản phẩm (số ngày), vì lô chưa có ngày sản xuất.
Ngày mốc là ngày giao dự kiến của stock.move, không phải hôm nay. Mọi hàm nhận date hoặc datetime,
miễn là cùng một kiểu.

Lô đạt khi:  expiration_date >= ngày mốc + ceil(pct / 100 × expiration_time) ngày.
"""

import datetime as dt


def applies(pct, expiration_time):
    """Quy tắc chỉ áp khi khách có yêu cầu và sản phẩm có tổng hạn dùng."""
    return bool(pct) and pct > 0 and bool(expiration_time) and expiration_time > 0


def min_days(pct, expiration_time):
    """Số ngày hạn dùng còn lại tối thiểu, làm tròn lên. 0 khi quy tắc không áp."""
    if not applies(pct, expiration_time):
        return 0
    # Tính bằng số nguyên để tránh sai số float: ceil(a / b) = -(-a // b).
    return -(-int(pct) * int(expiration_time) // 100)


def min_expiration_date(reference, pct, expiration_time):
    """Hạn dùng sớm nhất được chấp nhận khi giao vào `reference`, None khi quy tắc không áp."""
    if not reference or not applies(pct, expiration_time):
        return None
    return reference + dt.timedelta(days=min_days(pct, expiration_time))


def remaining_pct(expiration_date, reference, expiration_time):
    """Phần hạn dùng còn lại tại `reference`, tính bằng % của expiration_time (có thể âm khi đã hết hạn).

    None khi lô không có hạn dùng hoặc sản phẩm không có tổng hạn dùng.
    """
    if not expiration_date or not reference or not expiration_time or expiration_time <= 0:
        return None
    con = expiration_date - reference
    return con.total_seconds() / 86400 / expiration_time * 100


def lot_ok(expiration_date, reference, pct, expiration_time):
    """Lô giao được cho khách cần còn `pct`% không. Lô không có hạn dùng thì coi như đạt."""
    if not expiration_date:
        return True
    toi_thieu = min_expiration_date(reference, pct, expiration_time)
    return toi_thieu is None or expiration_date >= toi_thieu
