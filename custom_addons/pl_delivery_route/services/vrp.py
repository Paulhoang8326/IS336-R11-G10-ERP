"""Lập tuyến giao hàng trong ngày cho đội xe không đồng nhất (bài toán CVRP).

File Python thuần: không import odoo, không dùng thư viện ngoài, nên chạy và kiểm thử được độc lập
(xem tests/test_vrp.py). Module Odoo chỉ gom dữ liệu, gọi `lap_tuyen` rồi ghi kết quả.

Bài toán
--------
Có một kho, một đội xe (mỗi xe một tải trọng, mỗi xe chạy đúng 1 chuyến/ngày, xuất phát và quay về kho)
và các điểm giao (mỗi điểm một tọa độ và một tải kg). Cần chia điểm giao vào các xe sao cho không xe nào
chở quá tải trọng, rồi sắp thứ tự điểm trong mỗi chuyến để tổng quãng đường ngắn.

Các bước (hàm `lap_tuyen`)
--------------------------
0. Gộp theo khách (`gop_theo_khach`): mọi phiếu xuất của cùng một khách thành một điểm giao, tải là tổng
   tải các phiếu. Hàng của một khách không bao giờ bị chia lên hai xe.
1. Loại điểm không xếp được ngay từ đầu: điểm thiếu tọa độ, và điểm nặng hơn xe lớn nhất (không xe nào
   chở nổi dù chỉ chở riêng điểm đó). Các điểm này vào danh sách chưa xếp kèm lý do.
2. Ma trận khoảng cách: khoảng cách chim bay theo công thức haversine (km) nhân hệ số đường đi
   `he_so_duong` (mặc định 1,3) để ước lượng đường bộ thực tế. Không gọi API bản đồ nào.
3. Clarke-Wright savings, bản song song:
   - Khởi đầu mỗi điểm là một tuyến riêng: kho → điểm → kho.
   - Tiết kiệm khi nối i và j vào cùng tuyến: s(i, j) = d(kho, i) + d(kho, j) − d(i, j), tức quãng đường
     bớt được khi xe đi thẳng từ i sang j thay vì quay về kho rồi đi lại.
   - Duyệt mọi cặp theo s giảm dần (bằng nhau thì theo id). Với mỗi cặp, chỉ gộp hai tuyến khi i và j
     thuộc hai tuyến khác nhau, và mỗi điểm đang nằm ở đầu hoặc cuối tuyến của nó (điểm ở giữa tuyến đã có
     hai hàng xóm, nối thêm sẽ phá tuyến). Tuyến mới là tuyến của i nối với tuyến của j qua cạnh i–j.
   - Điều kiện số điểm (`so_diem_toi_da`, None hoặc 0 là không giới hạn): nếu tổng số điểm của hai tuyến
     vượt giới hạn thì không gộp. Một tài xế chỉ giao được số điểm có hạn trong ngày; giới hạn số điểm
     dùng thay cho giới hạn thời gian làm việc. Điều kiện này xét trước điều kiện tải vì rẻ hơn.
   - Điều kiện tải: đội xe không đồng nhất, nên không chỉ so với một tải trọng chung. Sau khi gộp, xếp
     thử tập tải các tuyến lên đội xe bằng first-fit decreasing (`xep_xe`): tuyến nặng nhất vào xe lớn
     nhất. Nếu có tuyến không vừa xe nào trong khi vẫn còn xe trống thì gộp này làm hỏng khả năng xếp xe,
     bỏ qua. Nếu chỉ là hết xe (số tuyến còn nhiều hơn số xe) thì vẫn cho gộp, vì gộp tiếp sẽ giảm số tuyến.
   - Duyệt hết danh sách cặp (không còn cặp nào gộp được) thì dừng.
4. Gán tuyến cho xe bằng first-fit decreasing: tuyến sắp theo tải giảm dần, xe sắp theo tải trọng giảm
   dần; mỗi tuyến lấy xe chưa dùng đầu tiên chở nổi nó. Mỗi xe nhận nhiều nhất 1 tuyến (1 chuyến/ngày).
   Tuyến không còn xe: mọi điểm của tuyến vào danh sách chưa xếp, lý do "không đủ xe".
5. 2-opt trên từng tuyến (kho → điểm → … → kho): thử đảo ngược mọi đoạn con; nếu đảo làm tổng quãng
   đường giảm thật sự (hơn một sai số rất nhỏ) thì nhận, rồi lặp lại cho tới khi không còn đảo nào làm
   ngắn hơn. 2-opt chỉ đổi thứ tự trong tuyến, không đổi điểm nào thuộc xe nào, nên tải không đổi.
6. Kết quả: mỗi tuyến gồm xe, thứ tự điểm, tải, km từng chặng (kho → điểm 1, …, điểm cuối → kho) và tổng
   km; cùng danh sách điểm chưa xếp kèm lý do.

Tính tất định: mọi phép sắp xếp đều có khóa phụ là id (của điểm hoặc xe), các vòng lặp duyệt theo thứ tự
cố định, nên cùng đầu vào luôn cho cùng kết quả. Id điểm phải cùng kiểu và so sánh được (cùng là số
hoặc cùng là chuỗi); id xe cũng vậy.
"""

from dataclasses import dataclass, field
from math import asin, cos, radians, sin, sqrt

BAN_KINH_TRAI_DAT_KM = 6371.0088
HE_SO_DUONG_MAC_DINH = 1.3
SAI_SO = 1e-9

LY_DO_VUOT_TAI = "vượt tải trọng xe lớn nhất"
LY_DO_THIEU_XE = "không đủ xe"
LY_DO_THIEU_TOA_DO = "thiếu tọa độ"


@dataclass(frozen=True)
class Diem:
    """Một điểm giao: một khách hàng. `phieu` là các phiếu xuất được gộp vào điểm này."""
    id: object
    vi_do: float
    kinh_do: float
    tai_kg: float
    phieu: tuple = ()


@dataclass(frozen=True)
class Xe:
    id: object
    tai_trong_kg: float


@dataclass
class Tuyen:
    """Một chuyến: xe chạy kho → diem[0] → … → diem[-1] → kho.

    chang_km có len(diem) + 1 phần tử: chặng i là quãng đường đến diem[i], chặng cuối là về kho.
    """
    xe: object
    diem: list
    tai_kg: float
    chang_km: list = field(default_factory=list)
    tong_km: float = 0.0


@dataclass
class ChuaXep:
    id: object
    ly_do: str


@dataclass
class KetQua:
    tuyen: list
    chua_xep: list

    @property
    def tong_km(self):
        return sum(t.tong_km for t in self.tuyen)


def haversine_km(a, b):
    """Khoảng cách chim bay giữa hai tọa độ (vĩ độ, kinh độ) theo độ, tính bằng km."""
    lat1, lng1, lat2, lng2 = map(radians, (a[0], a[1], b[0], b[1]))
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lng2 - lng1) / 2) ** 2
    return 2 * BAN_KINH_TRAI_DAT_KM * asin(min(1.0, sqrt(h)))


def gop_theo_khach(phieu):
    """Bước 0. Gộp các phiếu xuất của cùng một khách thành một điểm giao.

    phieu: các dict {"khach", "vi_do", "kinh_do", "tai_kg", "phieu"} (phieu là id phiếu xuất). Tọa độ
    lấy từ phiếu đầu tiên của khách (mọi phiếu cùng khách có cùng tọa độ). Trả về list[Diem] theo id khách.
    """
    theo_khach = {}
    for p in sorted(phieu, key=lambda x: (x["khach"], x["phieu"])):
        k = p["khach"]
        if k not in theo_khach:
            theo_khach[k] = {"vi_do": p["vi_do"], "kinh_do": p["kinh_do"], "tai_kg": 0.0, "phieu": []}
        theo_khach[k]["tai_kg"] += p["tai_kg"]
        theo_khach[k]["phieu"].append(p["phieu"])
    return [Diem(k, v["vi_do"], v["kinh_do"], v["tai_kg"], tuple(v["phieu"])) for k, v in theo_khach.items()]


def xep_xe(tai_cac_tuyen, ds_xe):
    """First-fit decreasing: gán mỗi tuyến cho một xe, mỗi xe tối đa một tuyến.

    tai_cac_tuyen: list (khóa tuyến, tải kg); khóa dùng để phá hòa khi hai tuyến nặng bằng nhau.
    Tuyến sắp theo tải giảm dần, xe sắp theo tải trọng giảm dần; mỗi tuyến lấy xe chưa dùng đầu tiên chở
    nổi nó. Vì cả hai cùng sắp giảm dần, xe chưa dùng đầu tiên luôn là xe lớn nhất còn lại: nếu nó không
    chở nổi thì không xe nào còn lại chở nổi.

    Trả về (gan, khong_xep, qua_tai):
    - gan: {khóa tuyến: id xe};
    - khong_xep: khóa các tuyến không được xe nào nhận;
    - qua_tai: True nếu có tuyến bị bỏ khi vẫn còn xe trống (tức tuyến quá nặng so với các xe còn lại),
      False nếu tuyến bị bỏ chỉ vì đã hết xe.
    """
    tuyen = sorted(tai_cac_tuyen, key=lambda x: (-x[1], x[0]))
    xe = sorted(ds_xe, key=lambda x: (-x.tai_trong_kg, x.id))
    da_dung = [False] * len(xe)
    gan, khong_xep, qua_tai = {}, [], False
    for khoa, tai in tuyen:
        for i, x in enumerate(xe):
            if not da_dung[i] and x.tai_trong_kg + SAI_SO >= tai:
                da_dung[i] = True
                gan[khoa] = x.id
                break
        else:
            khong_xep.append(khoa)
            if not all(da_dung):
                qua_tai = True
    return gan, khong_xep, qua_tai


def do_dai(tuyen, kc):
    """Tổng quãng đường kho → tuyen[0] → … → tuyen[-1] → kho; chỉ số 0 trong ma trận kc là kho."""
    if not tuyen:
        return 0.0
    di = [0] + list(tuyen) + [0]
    return sum(kc[di[k]][di[k + 1]] for k in range(len(di) - 1))


def hai_opt(tuyen, kc):
    """Bước 5. Cải thiện thứ tự một tuyến bằng 2-opt.

    Xét tour đóng kho → p1 → … → pn → kho. Với mỗi cặp cạnh (a, b) và (c, d) không kề nhau, thay bằng
    (a, c) và (b, d), tức đảo ngược đoạn b…c. Nhận phép đảo nếu tổng quãng đường giảm hơn SAI_SO, rồi
    quét lại từ đầu; dừng khi một lượt quét không còn phép đảo nào làm ngắn hơn. Vì chỉ nhận phép đảo làm
    giảm quãng đường, kết quả không bao giờ dài hơn tuyến ban đầu.
    """
    di = [0] + list(tuyen) + [0]
    n = len(di)
    cai_thien = True
    while cai_thien:
        cai_thien = False
        for i in range(1, n - 2):
            for j in range(i + 1, n - 1):
                a, b, c, d = di[i - 1], di[i], di[j], di[j + 1]
                giam = kc[a][b] + kc[c][d] - kc[a][c] - kc[b][d]
                if giam > SAI_SO:
                    di[i:j + 1] = reversed(di[i:j + 1])
                    cai_thien = True
    return di[1:-1]


def clarke_wright(n_diem, tai, kc, ds_xe, khoa_diem, so_diem_toi_da=None):
    """Bước 3. Clarke-Wright savings song song.

    Điểm đánh số 1..n_diem (0 là kho); tai[i] là tải điểm i; khoa_diem[i] là id gốc để phá hòa.
    so_diem_toi_da: số điểm tối đa mỗi tuyến; None hoặc 0 là không giới hạn.
    Trả về list tuyến, mỗi tuyến là list chỉ số điểm.
    """
    tuyen_cua = {i: i for i in range(1, n_diem + 1)}   # điểm -> khóa tuyến chứa nó
    tuyen = {i: [i] for i in range(1, n_diem + 1)}      # khóa tuyến -> danh sách điểm
    tai_tuyen = {i: tai[i] for i in range(1, n_diem + 1)}

    cap = []
    for i in range(1, n_diem + 1):
        for j in range(i + 1, n_diem + 1):
            s = kc[0][i] + kc[0][j] - kc[i][j]
            a, b = sorted((khoa_diem[i], khoa_diem[j]))
            cap.append((-s, a, b, i, j))
    cap.sort(key=lambda x: (x[0], x[1], x[2]))

    for _s, _a, _b, i, j in cap:
        ri, rj = tuyen_cua[i], tuyen_cua[j]
        if ri == rj:
            continue
        ti, tj = tuyen[ri], tuyen[rj]
        if i not in (ti[0], ti[-1]) or j not in (tj[0], tj[-1]):
            continue
        if so_diem_toi_da and len(ti) + len(tj) > so_diem_toi_da:
            continue
        tai_moi = tai_tuyen[ri] + tai_tuyen[rj]
        thu = [(k, v) for k, v in tai_tuyen.items() if k not in (ri, rj)] + [(ri, tai_moi)]
        if xep_xe(thu, ds_xe)[2]:
            continue
        # Xoay hai tuyến để i ở cuối tuyến thứ nhất, j ở đầu tuyến thứ hai, rồi nối qua cạnh i–j.
        if ti[-1] != i:
            ti.reverse()
        if tj[0] != j:
            tj.reverse()
        ti.extend(tj)
        tai_tuyen[ri] = tai_moi
        for p in tj:
            tuyen_cua[p] = ri
        del tuyen[rj], tai_tuyen[rj]
    return [tuyen[k] for k in sorted(tuyen)]


def lap_tuyen(kho, ds_diem, ds_xe, he_so_duong=HE_SO_DUONG_MAC_DINH, so_diem_toi_da=None):
    """Lập tuyến cho một ngày giao. Xem các bước ở đầu file.

    kho: (vĩ độ, kinh độ). ds_diem: list[Diem] (đã gộp theo khách). ds_xe: list[Xe].
    so_diem_toi_da: số điểm dừng tối đa mỗi chuyến; None hoặc 0 là không giới hạn.
    Trả về KetQua: tuyen sắp theo id xe, chua_xep sắp theo id điểm.
    """
    ds_diem = sorted(ds_diem, key=lambda d: d.id)
    ds_xe = sorted((x for x in ds_xe if x.tai_trong_kg > 0), key=lambda x: x.id)
    if len({d.id for d in ds_diem}) != len(ds_diem):
        raise ValueError("id điểm giao bị trùng: gộp theo khách trước (gop_theo_khach)")
    xe_lon_nhat = max((x.tai_trong_kg for x in ds_xe), default=0.0)

    # Bước 1: loại điểm thiếu tọa độ hoặc nặng hơn xe lớn nhất.
    chua_xep, hop_le = [], []
    for d in ds_diem:
        if d.vi_do is None or d.kinh_do is None:
            chua_xep.append(ChuaXep(d.id, LY_DO_THIEU_TOA_DO))
        elif not ds_xe:
            chua_xep.append(ChuaXep(d.id, LY_DO_THIEU_XE))
        elif d.tai_kg > xe_lon_nhat + SAI_SO:
            chua_xep.append(ChuaXep(d.id, LY_DO_VUOT_TAI))
        else:
            hop_le.append(d)

    # Bước 2: ma trận khoảng cách, chỉ số 0 là kho.
    toa_do = [tuple(kho)] + [(d.vi_do, d.kinh_do) for d in hop_le]
    n = len(hop_le)
    kc = [[0.0] * (n + 1) for _ in range(n + 1)]
    for a in range(n + 1):
        for b in range(a + 1, n + 1):
            kc[a][b] = kc[b][a] = haversine_km(toa_do[a], toa_do[b]) * he_so_duong
    tai = [0.0] + [d.tai_kg for d in hop_le]
    khoa_diem = [None] + [d.id for d in hop_le]

    # Bước 3: Clarke-Wright.
    cac_tuyen = clarke_wright(n, tai, kc, ds_xe, khoa_diem, so_diem_toi_da) if n else []

    # Bước 4: gán xe bằng first-fit decreasing.
    khoa = {min(khoa_diem[p] for p in t): t for t in cac_tuyen}
    gan, khong_xep, _ = xep_xe([(k, sum(tai[p] for p in t)) for k, t in khoa.items()], ds_xe)
    for k in khong_xep:
        chua_xep.extend(ChuaXep(khoa_diem[p], LY_DO_THIEU_XE) for p in khoa[k])

    # Bước 5 và 6: 2-opt từng tuyến rồi tính km từng chặng.
    ket_qua = []
    for k, xe_id in gan.items():
        t = hai_opt(khoa[k], kc)
        di = [0] + t + [0]
        chang = [kc[di[m]][di[m + 1]] for m in range(len(di) - 1)]
        ket_qua.append(Tuyen(xe=xe_id, diem=[khoa_diem[p] for p in t], tai_kg=sum(tai[p] for p in t),
                             chang_km=chang, tong_km=sum(chang)))
    ket_qua.sort(key=lambda x: x.xe)
    chua_xep.sort(key=lambda c: c.id)
    return KetQua(tuyen=ket_qua, chua_xep=chua_xep)
