# Bộ dữ liệu demo

Tài liệu này giải thích bộ dữ liệu trong `seed/demo/`: gồm những gì, chỗ nào là số tự đặt, các file CSV có cột gì và cách đổi số liệu. Cách nạp vào Odoo xem [seed.md](seed.md).

Sản phẩm và nhà cung cấp lấy từ danh mục của công ty (`seed/danh_muc/`, 795 mã, 6 nhà cung cấp); một số trường trong danh mục là số ước lượng. Khách hàng, bảng giá, xe và đơn hàng là giả lập, thầy đã cho phép.

| | Công ty | Bộ demo |
| --- | --- | --- |
| Khách hàng | 2.500 | 300 |
| Đơn mỗi ngày | 400–500 | 80, thêm 1 đơn quá tải |
| Xe | 10 | 4 |
| Kho | 2 | 2 |
| Mã hàng | 795 | 150 |

## Kho và xe

| Kho | Tên | Hàng của | Xe |
| --- | --- | --- | --- |
| K1 | Kho Wilmar - Võ Văn Kiệt | NCC01 Wilmar | XE01 1,5 tấn, XE02 2,5 tấn |
| K2 | Kho tổng - Nguyễn Văn Cừ nối dài | NCC02 đến NCC06 | XE03 1,5 tấn, XE04 2,5 tấn |

## Khách hàng

| Nhóm | Số khách | Hạn thanh toán | Hạn mức nợ | Hạn dùng còn lại khi giao | Giá riêng |
| --- | --- | --- | --- | --- | --- |
| Tạp hóa | 180 | trả ngay hoặc 7 ngày | 5–20 triệu | – | – |
| Minimart | 60 | 15 ngày | 30–80 triệu | ít nhất 50% | −3% mọi mã |
| Quán ăn | 30 | trả ngay hoặc 7 ngày | 5–15 triệu | – | – |
| Khách sạn | 15 | 30 ngày | 50–150 triệu | ít nhất 60% | −5% nước giải khát, nước suối khi mua từ 1 thùng |
| Căn tin KCN | 15 | 30 ngày | 50–200 triệu | ít nhất 60% | −7% nước giải khát, nước suối khi mua từ 5 thùng |

Khách trả ngay thì không có hạn mức nợ. Nhóm không có giá riêng thì mua theo giá bán.

## Đơn hàng

- 80 đơn ngày 20/10/2026, nửa ở K1, nửa ở K2. Mỗi đơn chỉ có hàng của một kho; một khách có tối đa 2 đơn, mỗi kho một đơn.
- Tạp hóa, quán ăn đặt ít mặt hàng, khoảng 1/4 số dòng là mua lẻ (vài chai, vài gói). Minimart và căn tin KCN đặt nhiều. Quán ăn và căn tin không mua đồ dùng cá nhân (dầu gội, khử mùi, pin...).
- Hàng mỗi kho nặng 70–85% sức chở của xe kho đó: K1 khoảng 3,0 tấn (75%), K2 khoảng 3,1 tấn (78%), so với 4 tấn sức chở mỗi kho.
- Đơn thứ 81, `DB20261020-081` ở K2, cố ý nặng khoảng 3 tấn, hơn xe lớn nhất 2,5 tấn, để thử trường hợp không xếp được lên xe.

## Số tự đặt

- Xe 1,5 và 2,5 tấn: nhóm tự đặt, chưa có số liệu thật.
- Tên và địa chỉ khách là giả lập; trong dữ liệu không gắn nhãn nào để phân biệt. Tọa độ là điểm ngẫu nhiên quanh trung tâm Cần Thơ, không khớp với địa chỉ.
- Giá nhập, giá bán trong danh mục phần lớn là ước lượng; mức giảm giá theo nhóm khách là tự đặt.
- 150 mã được chọn theo tỉ lệ số mã của từng nhà cung cấp (NCC01 40, NCC02 15, NCC03 6, NCC04 58, NCC05 22, NCC06 9), ưu tiên mã có số chai/gói mỗi thùng là số thật.
- Hạn dùng trong Odoo = số tháng hạn dùng × 30 ngày.

## Các file CSV

~~~text
seed/
├── danh_muc/          # danh mục gốc của công ty, không sửa
└── demo/              # do scripts/gen_seed.py tạo ra
    ├── san_pham.csv
    ├── nha_cung_cap.csv
    ├── khach_hang.csv
    ├── bang_gia.csv
    ├── kho.csv
    ├── xe.csv
    └── don_ban.csv
~~~

File CSV mã UTF-8, dòng đầu là tên cột. Sửa bằng Excel thì lưu dạng *CSV UTF-8*; số kiểu `12.000` hay `11,5` vẫn đọc đúng. Dưới đây "đơn vị lẻ" là chai, gói, hộp... và N là số đơn vị lẻ trong một thùng.

| File | Cột | Cần biết |
| --- | --- | --- |
| `san_pham.csv` | `ma_sp`, `ten`, `ma_ncc`, `nhom_hang`, `dvt`, `so_dvt_moi_thung`, `kg_moi_thung`, `ma_vach_le`, `ma_vach_thung`, `gia_nhap`, `gia_ban`, `vat_pct`, `han_dung_thang`, `uoc_luong` | Giữ nguyên cột của danh mục. `so_dvt_moi_thung` là N. Cân nặng tính cho một thùng, giá tính cho một đơn vị lẻ. `uoc_luong` liệt kê các cột là số ước lượng |
| `nha_cung_cap.csv` | `ma_ncc`, `ten`, `han_thanh_toan_ngay` | Chép nguyên từ danh mục |
| `khach_hang.csv` | `ma_kh`, `ten`, `nhom_khach`, `dia_chi`, `phuong`, `thanh_pho`, `vi_do`, `kinh_do`, `han_thanh_toan_ngay`, `han_muc_no`, `han_dung_toi_thieu_pct` | Hạn thanh toán 0 là trả ngay. Ô trống nghĩa là không có hạn mức nợ, không yêu cầu hạn dùng |
| `bang_gia.csv` | `nhom_khach`, `ma_sp`, `gia_ban`, `so_luong_toi_thieu` | Số lượng tính bằng đơn vị lẻ: thùng 12 chai, mua từ 1 thùng thì ghi 12 |
| `kho.csv` | `ma_kho`, `ten`, `vi_do`, `kinh_do`, `nha_cung_cap` | Các mã nhà cung cấp cách nhau bằng dấu cách |
| `xe.csv` | `ma_xe`, `loai_xe`, `tai_trong_kg`, `ma_kho` | |
| `don_ban.csv` | `so_don`, `ngay`, `ma_kh`, `ma_sp`, `so_luong`, `dvt`, `ma_kho` | Mỗi dòng là một mặt hàng của một đơn. `dvt` là `thung` hoặc `le` |

## Đổi số liệu

Bộ hiện tại tạo bằng lệnh mặc định `python scripts/gen_seed.py`; chạy lại lệnh này vẫn ra đúng các file cũ. Muốn đổi số liệu thì thêm tham số, rồi commit `seed/demo/` để cả nhóm dùng chung. Ví dụ đổi ngày đơn và thêm một xe 2,5 tấn cho K2:

~~~bash
python3 scripts/gen_seed.py --ngay 2026-11-02 --xe K1=1500,2500 K2=1500,2500,2500
~~~

~~~powershell
python scripts/gen_seed.py --ngay 2026-11-02 --xe K1=1500,2500 K2=1500,2500,2500
~~~

Cùng tham số thì máy nào chạy cũng ra file giống hệt. Cuối lệnh script in tóm tắt để kiểm tra: số mã mỗi nhà cung cấp, số khách mỗi nhóm, số đơn và tải của mỗi kho, cân nặng đơn quá tải.

| Tham số | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `--ngay` | `2026-10-20` | Ngày đơn hàng |
| `--so-ma`, `--so-khach`, `--so-don` | `150`, `300`, `80` | Số mã hàng, số khách, số đơn |
| `--ty-le-k1` | `50` | % số đơn ở K1 |
| `--xe` | `K1=1500,2500 K2=1500,2500` | Tải trọng xe (kg) theo kho |
| `--tai-min`, `--tai-max` | `70`, `85` | Tải mỗi kho, % sức chở của xe |
| `--vuot-tai` | `120` | Cân nặng đơn quá tải, % xe lớn nhất của K2 |
| `--seed` | `336` | Đổi số này là ra một bộ khác |

Đổi thông số một nhóm khách bằng `--nhom`, ví dụ `--nhom "Minimart.giam=4"` hay `--nhom "Tạp hóa.han_tt=0|7|15"`. Các thông số: `ty_le` (% số khách), `han_tt` (hạn thanh toán), `han_muc` (hạn mức nợ), `hsd` (% hạn dùng tối thiểu), `so_dong` (số mặt hàng mỗi đơn), `so_thung` (số thùng mỗi mặt hàng), `ty_le_le` (% dòng mua lẻ), `giam` (% giảm giá), `thung_gia` (mua từ bao nhiêu thùng thì được giảm). Xem thêm bằng `--help`.

## Dữ liệu vào Odoo ở đâu

Dành cho ai sửa `scripts/seed_import.py` hoặc viết module dùng dữ liệu này.

| File | Trong Odoo |
| --- | --- |
| `kho.csv` | Kho `stock.warehouse`, chỉ có tên và mã. Tọa độ kho chưa nạp |
| `nha_cung_cap.csv` | Đối tác `res.partner`, ô *Reference* là mã NCC, kèm hạn thanh toán |
| `san_pham.csv` | Sản phẩm `product.template` theo dõi theo lô và hạn dùng, có thuế theo `vat_pct`, cân nặng một đơn vị lẻ. Thêm quy cách "Thùng N" (`product.packaging`) và giá nhập theo nhà cung cấp (`product.supplierinfo`) |
| `bang_gia.csv` | Bảng giá `product.pricelist` "Giá sỉ - <nhóm>", mỗi dòng CSV là một dòng giá cố định |
| `khach_hang.csv` | Đối tác `res.partner`, ô *Reference* là mã KH, nhãn theo nhóm, hạn thanh toán, bảng giá, hạn mức nợ. Hạn dùng tối thiểu chờ module có trường `pl_min_shelf_life_pct` |
| `don_ban.csv` | Báo giá `sale.order` chưa xác nhận, ô *Customer Reference* là số đơn. Dòng mua theo thùng đổi ra số đơn vị lẻ và gắn quy cách thùng |
| `xe.csv` | Chưa nạp, chờ module giao hàng |

Script nhận ra bản ghi đã có qua mã (*Reference*, *Internal Reference*, mã kho, *Customer Reference*), chỉ sửa trường khác với CSV và không xóa gì. Ngoài ra script bật các cài đặt lô hàng, quy cách đóng gói, bảng giá, nhiều vị trí kho, hạn mức nợ, và tăng số chữ số thập phân của cân nặng từ 2 lên 4 để tổng cân nặng đơn trong Odoo khớp với file.
