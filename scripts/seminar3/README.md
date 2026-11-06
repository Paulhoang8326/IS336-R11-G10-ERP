# Database cho seminar 03

Demo nhập 2 bước, xuất 3 bước, định giá FIFO tự động và kiểm kê trên một sản phẩm mới, không đụng database chính.

| Database | Dùng để | Nhập / xuất |
| --- | --- | --- |
| `pl_moc` | Database chính của đồ án, không sửa ở đây | 1 bước / 1 bước |
| `phanlam_seminar3` | Demo trên lớp | 2 bước / 3 bước |
| `phanlam_seminar3_clean` | Bản sạch của database demo, để tạo lại khi cần | 2 bước / 3 bước |
| `phanlam_seminar3_check` | Chỉ tồn tại khi `check_flow.py` đang chạy | 2 bước / 3 bước |

## Tạo lại

Cần Odoo đang chạy và `pl_moc` đã nạp seed, đã chạy `scripts/setup_warehouse.py` ([docs/seed.md](../../docs/seed.md)).

~~~bash
export ODOO_PASSWORD='<mật khẩu admin Odoo>'
python3 scripts/seminar3/make_seminar_db.py --force
python3 scripts/seminar3/check_flow.py
python3 scripts/seminar3/make_seminar_db.py --backup-clean --force
~~~

- `make_seminar_db.py`: nhân bản `pl_moc` thành `phanlam_seminar3`, đổi kho sang nhập 2 bước, xuất 3 bước, cho admin group *Show Full Accounting Features*, tạo sản phẩm. `--force` xóa bản cũ.
- `check_flow.py`: chạy cả kịch bản trên `phanlam_seminar3_check`, in và so số sau mỗi bước, xong thì xóa bản check. `--keep` để giữ lại xem.
- `--backup-clean`: nhân bản `phanlam_seminar3` thành `phanlam_seminar3_clean`.

Mật khẩu admin lấy từ `ODOO_PASSWORD`, không có thì hỏi. Mật khẩu master lấy từ `ODOO_MASTER_PASSWORD`, không có thì đọc `admin_passwd` trong `config/odoo.conf`. Cả hai đều không nằm trong repo.

Demo xong muốn làm lại: chạy lại lệnh đầu tiên, hoặc ở `/web/database/manager` xóa `phanlam_seminar3` rồi duplicate `phanlam_seminar3_clean` thành tên đó.

## Sản phẩm demo

`[NCC01-SIM12] Dầu ăn Simply 1L (thùng 12 chai)`: nhà cung cấp Wilmar, nhóm Dầu ăn, theo lô, có hạn dùng, giá vốn 600.000, giá bán 660.000, VAT 8%, tồn 0. Đơn vị tính là thùng. Cost method FIFO, valuation Automated, removal FEFO lấy từ nhóm hàng.

Seed không có ô tên `A01`. Sơ đồ kệ của seed ghi mã ô là `dãy-kệ-tầng`, nên "A01" ở đây là ô `A-01-1` (dãy A, kệ 01, tầng 1, tầng dành cho hàng nặng), đường dẫn đầy đủ `PL/Stock/Dãy A - Wilmar/A-01-1`. Ô này đang có sẵn hàng của mã `NCC01-0010`.

## Kịch bản demo và menu

Giao diện tiếng Anh. Mỗi bước mở thêm hai màn hình để theo dõi: **Inventory > Reporting > Stock** (on hand, available) và **Inventory > Reporting > Valuation** (giá trị). Quant theo vị trí và lô ở **Inventory > Reporting > Locations**.

| # | Làm gì | Menu | On hand | Reserved | Giá trị | Bút toán mới |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Tạo PO cho Wilmar, 100 thùng, 600.000. *Confirm Order* | Purchase > Orders > Purchase Orders | 0 | 0 | 0 | |
| 2 | Mở phiếu `PL/IN/...` từ nút *Receipt* trên PO. Ở dòng hàng mở *Details*, nhập lô `SIM-2610-A`, hạn dùng 30/04/2027, 100. *Validate* | Inventory > Operations > Transfers > Receipts | 100 | 100 | 60.000.000 | Nợ 1560 / Có 1510: 60.000.000 |
| 3 | Mở phiếu `PL/STOR/...`, thấy gợi ý vào `A-01-1`. *Validate* | Inventory > Overview, thẻ Storage (hoặc Transfers > Internal) | 100 | 0 | 60.000.000 | |
| 4 | Tạo báo giá cho một khách nhãn Khách sạn, 30 thùng. *Confirm* | Sales > Orders > Quotations | 100 | 30 | 60.000.000 | |
| 5 | Mở phiếu `PL/PICK/...`. *Validate* | Inventory > Overview, thẻ Pick | 100 | 30 | 60.000.000 | |
| 6 | Mở phiếu `PL/PACK/...`. *Put in Pack*, rồi *Validate* | Inventory > Overview, thẻ Pack | 100 | 30 | 60.000.000 | |
| 7 | Mở phiếu `PL/OUT/...` (lọc theo số SO, vì danh sách còn 81 phiếu của seed). *Validate* | Inventory > Operations > Transfers > Deliveries | 70 | 0 | 42.000.000 | Nợ 1570 / Có 1560: 18.000.000 |
| 8 | Ở dòng `A-01-1`, lô `SIM-2610-A`, nhập Counted 68. *Apply* | Inventory > Operations > Adjustments > Physical Inventory | 68 | 0 | 40.800.000 | Nợ 13811 / Có 1560: 1.200.000 |

Bút toán xem ở **Invoicing > Accounting > Journal Entries** (hoặc *Journal Items* để lọc theo tài khoản). Sổ Inventory Valuation, số `STJ/...`.

Điểm dễ bị hỏi khi demo:

- Sau Receipt, reserved = 100, available = 0: phiếu Storage tự giữ hàng ở Input. Storage xong mới về 0.
- Pick và Pack chỉ đổi vị trí trong công ty, nên on hand và giá trị không đổi, không có bút toán. Giá trị chỉ đổi khi hàng ra khỏi công ty ở Delivery.
- On hand tính mọi vị trí nội bộ, gồm cả Input, Packing Zone và Output.
- Xác nhận SO chỉ giữ hàng, chưa ghi nhận giá vốn. Nợ 1570 được kết chuyển sang 632 khi xuất hóa đơn cho khách, kịch bản này không làm bước đó.

## Tài khoản kế toán đã dùng

Bộ `l10n_vn`, `anglo_saxon_accounting` bật. Cả 22 nhóm hàng của seed dùng chung bộ tài khoản này, gán bằng `scripts/setup_warehouse.py`.

| Vai trò | Trường trong Odoo | Tài khoản | Ghi chú |
| --- | --- | --- | --- |
| Tồn kho | Stock Valuation Account | `1560` Goods | Mặc định của `l10n_vn` là `1550` Finished Goods; nhà phân phối giữ hàng hóa nên đổi sang 1560 |
| Trung gian nhập | Stock Input Account | `1510` Goods in transit | `l10n_vn` không có sẵn. Đã bật cho đối soát |
| Trung gian xuất | Stock Output Account | `1570` Outward goods on consignment | `l10n_vn` không có sẵn. Đã bật cho đối soát |
| Kiểm kê | Valuation in/out của `Virtual Locations/Inventory adjustment` | `13811` Shortage of assets awaiting resolution - short term | COA không có đúng số 1381, 13811 là tài khoản con ngắn hạn. Dùng cho cả thiếu và thừa |
| Giá vốn | Expense Account | `6320` Costs of goods sold | Mặc định của `l10n_vn`, kịch bản không phát sinh |
| Sổ | Stock Journal | `STJ` Inventory Valuation | Mặc định |

Tồn đầu kỳ của seed nằm sẵn trong 150 bút toán `STJ/2026/11/0001` đến `0150`, tổng Nợ 1560 / Có 1510 là 1.833.616.300 đ, do Odoo sinh khi đổi định giá sang Automated. Vì vậy số dư 1510 có cả phần này, muốn xem riêng kịch bản thì lọc theo sản phẩm.

## Quyền xem bút toán

Trên Odoo 18 Community, admin có sẵn *Administrator* của kế toán nhưng không thấy menu **Invoicing > Accounting**, vì menu cần `account.group_account_readonly`. Bật `account.group_account_user` (*Show Full Accounting Features*) là thấy. `make_seminar_db.py` chỉ bật cho admin trên `phanlam_seminar3`, `pl_moc` chưa bật. Muốn bật tay: bật Developer Mode, Settings > Users > admin, tick *Show Full Accounting Features*.
