# Bộ dữ liệu demo

Tài liệu này giải thích bộ dữ liệu trong `seed/demo/`: gồm những gì, chỗ nào là số tự đặt, các file CSV có cột gì và cách đổi số liệu. Cách nạp vào Odoo xem [seed.md](seed.md).

Sản phẩm và nhà cung cấp lấy từ danh mục của công ty (`seed/danh_muc/`, 795 mã, 6 nhà cung cấp); một số trường trong danh mục là số ước lượng. Khách hàng, bảng giá, xe và đơn hàng là giả lập, thầy đã cho phép.

| | Công ty | Bộ demo |
| --- | --- | --- |
| Khách hàng | 2.500 | 300 |
| Đơn mỗi ngày | 400–500 | 80, thêm 1 đơn quá tải |
| Xe | 10 | 4 |
| Kho | 2 | 1 |
| Mã hàng | 795 | 150 |

Thực tế công ty có 2 điểm kho; đồ án gộp thành 1 kho để đơn giản hóa phạm vi.

## Kho và xe

| Mã | Kho | Địa chỉ | Tọa độ | Xe |
| --- | --- | --- | --- | --- |
| PL | Kho Phan Lâm | Nguyễn Văn Cừ nối dài, Cần Thơ | 10.0274244, 105.7466991 | XE01, XE02 1,5 tấn; XE03, XE04 2,5 tấn |

Đây là điểm xuất phát duy nhất của mọi chuyến giao hàng: cả 4 xe cùng xuất phát từ kho này. Hàng mọi nhãn nằm chung kho, mỗi nhãn một dãy kệ:

| Dãy | Mã vị trí | Hàng của | Kệ × tầng | Số ô |
| --- | --- | --- | --- | --- |
| Dãy A - Wilmar | `PL-A` | NCC01 | 16 × 4 | 64 |
| Dãy B - PepsiCo | `PL-B` | NCC02 | 6 × 4 | 24 |
| Dãy C - Ajinomoto | `PL-C` | NCC03 | 2 × 4 | 8 |
| Dãy D - DKSH | `PL-D` | NCC04 | 23 × 4 | 92 |
| Dãy E - Marico | `PL-E` | NCC05 | 9 × 4 | 36 |
| Dãy F - Energizer (pin) | `PL-F` | NCC06 | 4 × 4 | 16 |

### Mã ô kệ

Mỗi dãy chia thành các ô, tổng cộng 240 ô. Mã ô là `dãy-kệ-tầng`: `A-01-1` là dãy A, kệ 01, tầng 1 (tầng sát sàn). Kệ ghi 2 chữ số, tầng ghi 1 chữ số. 60 kệ chia cho các dãy theo số mã hàng của nhãn, mỗi kệ 4 tầng.

- Đường đi lấy hàng hình chữ S: vào dãy A từ đầu dãy, đi hết dãy, sang dãy B từ cuối dãy, đi ngược về đầu, rồi sang dãy C... Kệ được đánh số theo đúng chiều đi, nên dãy A, C, E có kệ 01 ở đầu dãy, còn dãy B, D, F có kệ 01 ở cuối dãy. Nhờ vậy sắp ô theo tên (Odoo sắp vị trí theo tên đầy đủ, vd `PL/Stock/Dãy A - Wilmar/A-01-1`) là đúng thứ tự đi lấy hàng.
- Trong Odoo, ô cũng ghi dãy/kệ/tầng ở các ô *Corridor (X)*, *Shelves (Y)*, *Height (Z)*; ô *Barcode* là mã ô.
- Mỗi mã hàng nằm ở một ô. Hàng nặng (dầu ăn, nước giải khát, nước suối) luôn ở tầng 1; dãy B có 13 mã nặng mà chỉ 6 ô tầng 1 nên vài ô dùng chung 2–3 mã. Hàng nhẹ xếp từ tầng 2 trở lên trước. Ô chưa có hàng để dành cho hàng nhập sau.

## Tồn kho

Tồn đầu ngày mốc, theo lô và hạn dùng, nằm trong ô của dãy đúng nhãn; không có tồn ở cấp dãy hay `PL/Stock`. Ngày sản xuất và hạn dùng tính lùi, tiến từ ngày mốc (`--ngay-moc`, xem [seed.md](seed.md)), nên đổi ngày mốc thì mọi khoảng cách dưới đây giữ nguyên. Ngày sản xuất của mọi lô đều trước ngày mốc, và hạn dùng trừ ngày sản xuất đúng bằng hạn dùng của mã (số tháng × 30 ngày).

- Mỗi mã có 2 hoặc 3 lô thường, hạn dùng khác nhau. Hai lô: lô cũ còn 30–60% hạn dùng, lô mới còn 70–95%. Ba lô: còn 25–45%, 50–70%, 75–95%. Lô cũ có thể dưới mức hạn dùng tối thiểu của minimart (50%) hay khách sạn, căn tin (60%), để thử chọn lô khi giao.
- Riêng các lô thường đã đủ hàng cho mọi đơn trong ngày (kể cả đơn quá tải), dư thêm 3–12 thùng mỗi mã.
- Thêm 5 lô cận date (còn 5–30 ngày tới hạn) và 2 lô đã hết hạn 3–30 ngày, mỗi lô 1–3 thùng, ở 7 mã khác nhau. Mã có lô thêm thì chỉ có 2 lô thường, nên vẫn tối đa 3 lô.
- Aquafina 1500 ml (`NCC02-0002`, mã PepsiCo hạn dùng dài nhất, 18 tháng) có đúng 3 lô, hết hạn sau ngày mốc 5, 11 và 17 tháng (150, 330, 510 ngày), tức còn khoảng 28%, 61% và 94% hạn dùng. Với ngày mốc 29/10/2026 là các hạn 28/03/2027, 24/09/2027 và 22/03/2028. Kịch bản demo: khách minimart cần hàng còn ít nhất 50% hạn dùng, nên lô hết hạn gần nhất không đạt và phải lấy lô thứ hai.
- Số lô là `L` + ngày sản xuất dạng `yymmdd`. Cột `ngay_sx` trong `ton_kho.csv` chưa nạp vào Odoo vì Odoo chưa có trường ngày sản xuất; sẽ nạp khi có module `pl_stock_lot`.
- Kho xuất theo FEFO: lô hết hạn sớm nhất được lấy trước. Odoo chuẩn (`product_expiry`) không giữ lô có hạn dùng trước ngày của phiếu xuất. Ngày đó là lúc xác nhận đơn, không phải ngày mốc, nên muốn lô cận date và lô hết hạn đúng như trên thì ngày mốc phải là ngày demo. Giữ hạn dùng tối thiểu theo nhóm khách là việc của module `pl_fefo_pick`.

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

- 80 đơn vào ngày mốc, đều xuất từ Kho Phan Lâm. Số đơn là `DB` + ngày mốc + số thứ tự, vd `DB20261029-001`. Một đơn có thể có hàng của nhiều nhãn (75 trên 81 đơn như vậy). Mỗi khách có tối đa 1 đơn.
- Tạp hóa, quán ăn đặt ít mặt hàng, khoảng 1/4 số dòng là mua lẻ (vài chai, vài gói). Minimart và căn tin KCN đặt nhiều. Quán ăn và căn tin không mua đồ dùng cá nhân (dầu gội, khử mùi, pin...).
- Tổng hàng nặng 70–85% sức chở của 4 xe: khoảng 5,9 tấn (74%) so với 8 tấn.
- Đơn thứ 81 (`DB<ngày mốc>-081`) cố ý nặng khoảng 3 tấn, hơn xe lớn nhất 2,5 tấn, để thử trường hợp không xếp được lên xe.

## Số tự đặt

- Xe 1,5 và 2,5 tấn: nhóm tự đặt, chưa có số liệu thật.
- Cách chia dãy, số kệ, số tầng, vị trí từng mã, số lượng tồn, số lô và ngày sản xuất là tự đặt.
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
    ├── vi_tri.csv
    ├── ton_kho.csv
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
| `kho.csv` | `ma_kho`, `ten`, `dia_chi`, `thanh_pho`, `vi_do`, `kinh_do` | Đúng một dòng |
| `vi_tri.csv` | `ma_vi_tri`, `ten`, `ma_cha`, `ma_ncc`, `day`, `ke`, `tang` | Dòng dãy có `ma_cha` trống; dòng ô có `ma_cha` là mã dãy. `day`, `ke`, `tang` là số thứ tự |
| `ton_kho.csv` | `ma_sp`, `ma_vi_tri`, `so_lo`, `ngay_sx`, `han_dung`, `so_luong` | Mỗi dòng là một lô, `ma_vi_tri` là mã ô. `so_luong` tính bằng đơn vị lẻ, luôn là số thùng chẵn. Ngày dạng `YYYY-MM-DD`. `ngay_sx` chưa nạp vào Odoo |
| `xe.csv` | `ma_xe`, `loai_xe`, `tai_trong_kg`, `ma_kho` | `ma_kho` là kho xe xuất phát |
| `don_ban.csv` | `so_don`, `ngay`, `ma_kh`, `ma_sp`, `so_luong`, `dvt` | Mỗi dòng là một mặt hàng của một đơn. `dvt` là `thung` hoặc `le` |

## Đổi số liệu

Bộ hiện tại tạo bằng lệnh `python scripts/gen_seed.py --ngay-moc 2026-10-29`; chạy lại lệnh này vẫn ra đúng các file cũ. Muốn đổi số liệu thì thêm tham số, rồi commit `seed/demo/` để cả nhóm dùng chung. Ví dụ đổi ngày mốc và thêm một xe 2,5 tấn:

~~~bash
python3 scripts/gen_seed.py --ngay-moc 2026-11-02 --xe 1500,1500,2500,2500,2500
~~~

~~~powershell
python scripts/gen_seed.py --ngay-moc 2026-11-02 --xe 1500,1500,2500,2500,2500
~~~

Cùng ngày mốc và cùng tham số thì máy nào chạy cũng ra file giống hệt. Đổi ngày mốc thì chỉ các ngày (và số đơn, số lô vốn ghép từ ngày) dời theo; khách, mặt hàng, số lượng và vị trí giữ nguyên. Cuối lệnh script in tóm tắt để kiểm tra: số mã và dãy kệ của mỗi nhà cung cấp, số khách mỗi nhóm, số đơn và tổng tải, cân nặng đơn quá tải, số lô tồn kho, lô cận date và hết hạn, 3 lô Aquafina, và tồn có đủ cho mọi đơn không.

| Tham số | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `--ngay-moc` | hôm nay | Ngày đơn hàng; ngày sản xuất và hạn dùng của lô tính theo ngày này |
| `--so-ma`, `--so-khach`, `--so-don` | `150`, `300`, `80` | Số mã hàng, số khách, số đơn |
| `--xe` | `1500,1500,2500,2500` | Tải trọng từng xe (kg), mọi xe xuất phát từ Kho Phan Lâm |
| `--tai-min`, `--tai-max` | `70`, `85` | Tổng tải các đơn, % sức chở của tất cả xe |
| `--vuot-tai` | `120` | Cân nặng đơn quá tải, % xe lớn nhất |
| `--seed` | `336` | Đổi số này là ra một bộ khác |

Đổi thông số một nhóm khách bằng `--nhom`, ví dụ `--nhom "Minimart.giam=4"` hay `--nhom "Tạp hóa.han_tt=0|7|15"`. Các thông số: `ty_le` (% số khách), `han_tt` (hạn thanh toán), `han_muc` (hạn mức nợ), `hsd` (% hạn dùng tối thiểu), `so_dong` (số mặt hàng mỗi đơn), `so_thung` (số thùng mỗi mặt hàng), `ty_le_le` (% dòng mua lẻ), `giam` (% giảm giá), `thung_gia` (mua từ bao nhiêu thùng thì được giảm). Xem thêm bằng `--help`.

## Dữ liệu vào Odoo ở đâu

Dành cho ai sửa `scripts/seed_import.py` hoặc viết module dùng dữ liệu này.

| File | Trong Odoo |
| --- | --- |
| `kho.csv` | Kho `stock.warehouse` duy nhất. Database mới có sẵn kho mặc định `WH`: script đổi tên và mã kho đó thành `PL` chứ không tạo kho thứ hai. Địa chỉ và tọa độ nằm ở đối tác `res.partner` "Kho Phan Lâm" (*Reference* `PL`), là địa chỉ của kho |
| `vi_tri.csv` | Vị trí `stock.location`: dãy là con của `PL/Stock`, ô là con của dãy. Ô *Barcode* là mã vị trí |
| `ton_kho.csv` | Lô `stock.lot` có hạn dùng, cùng tồn đầu kỳ (`stock.quant`) ở ô kệ. Chỉ nhập tồn cho lô mới tạo: chạy lại script không cộng thêm tồn cho lô đã có. Chưa nạp `ngay_sx` |
| (cấu hình kho) | `PL/Stock` xuất theo FEFO (*Removal Strategy*), áp dụng cho mọi ô bên dưới. Mỗi sản phẩm một quy tắc cất hàng (`stock.putaway.rule`): nhập vào `PL/Stock` thì gợi ý dãy của nhà cung cấp, cụ thể là ô nhập gần nhất của mã đó trong dãy (*Last Used*) |
| `nha_cung_cap.csv` | Đối tác `res.partner`, ô *Reference* là mã NCC, kèm hạn thanh toán |
| `san_pham.csv` | Sản phẩm `product.template` theo dõi theo lô và hạn dùng, có thuế theo `vat_pct`, cân nặng một đơn vị lẻ. Thêm quy cách "Thùng N" (`product.packaging`) và giá nhập theo nhà cung cấp (`product.supplierinfo`) |
| `bang_gia.csv` | Bảng giá `product.pricelist` "Giá sỉ - <nhóm>", mỗi dòng CSV là một dòng giá cố định |
| `khach_hang.csv` | Đối tác `res.partner`, ô *Reference* là mã KH, nhãn theo nhóm, hạn thanh toán, bảng giá, hạn mức nợ. Hạn dùng tối thiểu chờ module có trường `pl_min_shelf_life_pct` |
| `don_ban.csv` | Báo giá `sale.order` chưa xác nhận, xuất từ Kho Phan Lâm, ô *Customer Reference* là số đơn. Dòng mua theo thùng đổi ra số đơn vị lẻ và gắn quy cách thùng |
| `xe.csv` | Chưa nạp, chờ module giao hàng |

Script nhận ra bản ghi đã có qua mã (*Reference*, *Internal Reference*, mã kho, *Barcode* vị trí, số lô, *Customer Reference*), chỉ sửa trường khác với CSV và không xóa gì. Ngoài ra script bật các cài đặt lô hàng, quy cách đóng gói, bảng giá, nhiều vị trí kho, hạn mức nợ, và tăng số chữ số thập phân của cân nặng từ 2 lên 4 để tổng cân nặng đơn trong Odoo khớp với file.
