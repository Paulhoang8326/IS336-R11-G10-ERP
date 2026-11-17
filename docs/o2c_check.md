# Kiểm tra Order-to-Cash

`scripts/check_o2c.py` chạy trọn quy trình mua hàng, bán hàng, lập tuyến, giao hàng, lập hóa đơn, thu tiền trên bản nhân bản của database chính, kiểm từng bước rồi xóa bản đó. Mục đích là biết sau mỗi thay đổi (module nhóm, seed, cài đặt) thì quy trình Order-to-Cash theo BPMN TO-BE vẫn chạy được từ đầu đến cuối, không phải bấm tay lại.

Không ghi gì lên `pl_moc`: script chỉ đọc danh sách module của `pl_moc`, mọi thao tác khác làm trên `pl_o2c_check`.

## Chạy

~~~bash
python3 scripts/check_o2c.py                  # nhân bản pl_moc thành pl_o2c_check, xong thì xóa
python3 scripts/check_o2c.py --keep           # giữ pl_o2c_check để xem trên giao diện
python3 scripts/check_o2c.py --src pl_seed_fefo   # nhân bản database khác
python3 scripts/check_o2c.py --policy-order   # thử âm: phải FAIL ở bước 5
~~~

~~~powershell
python scripts/check_o2c.py
python scripts/check_o2c.py --keep
~~~

Mật khẩu như `scripts/seminar3`: admin lấy từ `ODOO_PASSWORD` (không có thì hỏi), master từ `ODOO_MASTER_PASSWORD` hoặc `admin_passwd` trong `config/odoo.conf`. Chạy mất khoảng 25 giây. Sai điều nào thì in `FAIL: ...`, bảng tóm tắt và mã thoát khác 0; database check vẫn bị xóa, trừ khi có `--keep`.

## Các bước

Ngày mốc lấy từ `seed/demo/don_ban.csv` (bộ hiện tại: 29/10/2026). Mọi đơn bán có *Delivery Date* 08:00 ngày mốc, như `check_fefo.py`, để hạn dùng còn lại tính theo ngày giao chứ không theo hôm nay.

| Bước | Làm gì | Kiểm tra |
| --- | --- | --- |
| 0. Module, seed | In module `pl_moc` đang thiếu trong số `sale_management`, `purchase_stock`, `sale_stock`, `account`, `product_expiry`, `pl_fefo_pick`, `pl_delivery_route`; cài phần thiếu trên bản nhân bản. Chạy lại `seed_import.py` lên bản nhân bản | `seed_import.py` không cảnh báo; Sales Settings để *Invoicing Policy* = `delivery` |
| 1. Mua hàng | Đơn mua 10 thùng một mã dầu ăn Wilmar (`NCC01`), xác nhận, nhận hàng với lô mới `LO2CCHECK`, hạn dùng = ngày mốc + *Expiration Time* | Lô mới nằm trong một ô của `Dãy A - Wilmar` theo quy tắc cất hàng, không ở `PL/Stock`, không ở cấp dãy |
| 2. Bán hàng | 3 đơn cùng mã cho 3 khách lấy từ `khach_hang.csv`: X tạp hóa trả ngay (2 thùng), Y căn tin KCN hạn thanh toán 30 ngày (4 thùng), Z minimart có hạn mức nợ thấp nhất (3 thùng). Trước khi đặt đơn Z, tạo và post một hóa đơn chưa thu cho Z bằng hạn mức trừ nửa giá trị đơn mới | Phiếu xuất Ready đủ hàng, ngày dự kiến 08:00 ngày mốc; mọi lô được giữ còn hạn dùng lúc giao không dưới mức của khách (30%, 60%, 50%); báo giá Z có `partner_credit_warning`, X và Y không có |
| 3. Lập tuyến | Kế hoạch giao hàng ngày mốc ở kho `PL`, *Compute Routes*, *Confirm* | 3 phiếu của X, Y, Z nằm trong chuyến (không ở danh sách chưa xếp); sau khi xác nhận phiếu có chuyến và thứ tự điểm dừng |
| 4. Giao hàng | X giao đủ 2 thùng. Y giao 3/4 thùng, *Create Backorder*. Z giao 2/3 thùng, *No Backorder* | X không backorder; Y có đúng một backorder còn 1 thùng; đơn Z không còn move mở; *Delivered* trên dòng đơn bằng số đã giao |
| 5. Hóa đơn | *Create Invoice* > *Regular invoice* trên từng đơn, post | Số lượng trên hóa đơn = số đã giao (X 2, Y 3, Z 2 thùng), không phải số đặt; tạo hóa đơn lần nữa cho Y trước khi giao backorder bị Odoo từ chối (`UserError`) |
| 6. Thu tiền | X: *Register Payment* toàn bộ vào sổ *Cash*. Mô phỏng tài xế thu tiền mặt khi giao, kế toán ghi nhận lúc đối chiếu cuối ngày; tài xế không thao tác trên Odoo. Y: không thu | Hóa đơn X *Paid*, còn nợ 0. Hóa đơn Y *Not Paid*, còn nợ bằng tổng hóa đơn, hạn thanh toán là của khách, ngày đến hạn = ngày hóa đơn + 30 ngày |
| 7. Backorder Y | Giao nốt 1 thùng, xuất hóa đơn lần 2, post | Đơn Y đã xuất hóa đơn 4/4 thùng, bằng tổng hai hóa đơn |

Cuối cùng script in bảng tóm tắt từng bước PASS/FAIL kèm số đơn, số phiếu, số hóa đơn, kế hoạch giao hàng. Chạy với `--keep` rồi tìm các số này trên giao diện để xem lại.

### Hóa đơn theo số lượng giao

BPMN TO-BE lập hóa đơn theo số lượng giao thực tế, sau khi giao. Odoo 18 mặc định ngược lại, đọc trong source của image `odoo:18.0-20260926`:

- `addons/sale/models/product_template.py`: `invoice_policy` là trường tính, lưu (`compute='_compute_invoice_policy'`, `precompute=True`), lựa chọn `order` (*Ordered quantities*) và `delivery` (*Delivered quantities*). `_compute_invoice_policy` đặt `order` cho sản phẩm `type == 'consu'` (mọi hàng hóa, kể cả hàng tồn kho) hoặc chưa có giá trị.
- `addons/sale/wizard/res_config_settings.py`: setting `default_invoice_policy`, nhãn *Invoicing Policy*, lựa chọn *Invoice what is ordered* / *Invoice what is delivered*, `default='order'`, `default_model='product.template'`. Nằm ở Sales > Configuration > Settings > Invoicing. Setting chỉ ghi `ir.default` cho sản phẩm tạo sau; sản phẩm đã có giữ nguyên.

Vì vậy `seed_import.py` vừa bật *Invoice what is delivered* vừa ghi `invoice_policy = delivery` cho từng sản phẩm của seed ([seed_data.md](seed_data.md#dữ-liệu-vào-odoo-ở-đâu)). Với `delivery`, `sale.order.line.qty_to_invoice` = đã giao - đã xuất hóa đơn; với `order` là đã đặt - đã xuất hóa đơn (`_compute_qty_to_invoice`).

`--policy-order` ghi lại `invoice_policy = order` cho sản phẩm trên bản nhân bản sau khi chạy `seed_import.py`, để chắc bước 5 bắt được lỗi này.

### Cảnh báo hạn mức nợ

Trường là `sale.order.partner_credit_warning` (Text, tính, không lưu), hiện thành dải vàng đầu báo giá. `_compute_partner_credit_warning` (`addons/sale/models/sale_order.py`) chỉ tính khi đơn ở trạng thái *Quotation* (`draft`, `sent`) và công ty bật *Sales Credit Limit* (`account_use_credit_limit`, `seed_import.py` đã bật). Nội dung lấy từ `account.move._build_credit_warning_message`: có cảnh báo khi nợ đã post (`credit`) + đơn đã xác nhận chưa xuất hóa đơn (`credit_to_invoice`) + giá trị báo giá này vượt `credit_limit` của khách. Hóa đơn nháp cũng có trường cùng tên `account.move.partner_credit_warning`.

Odoo 18 Community chỉ cảnh báo, không chặn: không có kiểm tra nào trong `action_confirm`. Script đọc cảnh báo trước khi xác nhận (sau khi xác nhận trường trống vì đơn không còn là báo giá), ghi nhận đơn Z vẫn xác nhận được và không coi đó là lỗi.

## Kết quả

Chạy ngày 17/11/2026 trên macOS, Odoo 18.0-20260926, database nguồn `pl_moc`. `pl_moc` đang thiếu `sale_management`, `pl_fefo_pick`, `pl_delivery_route`; script cài 3 module này trên bản nhân bản.

Mã dùng: `NCC01-0027` Dầu Ô-liu Pomace Olivoilà 750ML, thùng 6 chai, hạn dùng 540 ngày (script chọn mã dầu ăn Wilmar có lô còn 30-60% hạn dùng lúc giao, để thấy khách 30% lấy được lô mà khách 60% không lấy). Khách: X `KH0005` tạp hóa trả ngay, Y `KH0006` căn tin KCN 30 ngày, Z `KH0102` minimart hạn mức 30.000.000 đ.

| Bước | Kết quả | Chứng từ | Chi tiết |
| --- | --- | --- | --- |
| 0. Module, seed | PASS | | Cài `sale_management`, `pl_fefo_pick`, `pl_delivery_route`; `seed_import.py` 0 cảnh báo, bật *Invoice what is delivered*, cập nhật 150 sản phẩm, tạo 4 xe |
| 1. Mua hàng | PASS | `P00001`, `PL/IN/00001` | 10 thùng lô `LO2CCHECK` hạn 21/04/2028 vào `PL/Stock/Dãy A - Wilmar/A-03-1` |
| 2. Bán hàng | PASS | X `S00082` `PL/OUT/00082`; Y `S00083` `PL/OUT/00083`; Z `S00084` `PL/OUT/00084`, nợ cũ `INV/2026/00001` | X (30%) giữ lô 31,6% và 39,9%; Y (60%) giữ lô 67,5% và 67,7%; Z (50%) giữ lô 89,4%. Z có nợ cũ 29.601.178 đ, báo giá 797.643 đ: `partner_credit_warning` = "Siêu thị mini An Khang has reached its credit limit of: 30,000,000 ₫"; đơn vẫn xác nhận được |
| 3. Lập tuyến | PASS | `DP/2026/0001` | 4 chuyến; X ở `XE04` điểm 15 (`BATCH/00004`), Y ở `XE01` điểm 2, Z ở `XE01` điểm 23 (`BATCH/00001`) |
| 4. Giao hàng | PASS | backorder `PL/OUT/00085` | X giao 2/2 thùng; Y 3/4 thùng, backorder còn 1 thùng; Z 2/3 thùng, không backorder, không move mở |
| 5. Hóa đơn | PASS | X `INV/2026/00002`, Y `INV/2026/00003`, Z `INV/2026/00004` | 2, 3, 2 thùng = số đã giao. Tạo hóa đơn lần nữa cho Y: "Cannot create an invoice. No items are available to invoice." |
| 6. Thu tiền | PASS | `PCSH1/2026/00001` | X thu 548.208 đ vào *Cash*, hóa đơn *Paid*. Y còn nợ 822.312/822.312 đ, hóa đơn 17/11/2026, đến hạn 17/12/2026 (30 ngày) |
| 7. Backorder Y | PASS | `PL/OUT/00085`, `INV/2026/00005` | Giao 1 thùng, hóa đơn lần 2 1 thùng; đơn `S00083` đặt 4, giao 4, đã xuất hóa đơn 4 thùng |

Chạy 3 lần liên tiếp đều PASS, mã thoát 0, ra cùng số chứng từ (mỗi lần nhân bản lại từ `pl_moc`); sau mỗi lần không còn database `pl_o2c_check`.

Thử âm với `--policy-order` (150 sản phẩm để `invoice_policy = order` trên bản nhân bản): bước 0-4 PASS, bước 5 FAIL, mã thoát 1:

~~~text
FAIL: INV/2026/00003 (Y) lập 4 thùng, đã giao 3 thùng (đặt 4): hóa đơn không theo số lượng giao
~~~

Cùng ngày: `check_route.py` và `scripts/seminar3/check_flow.py` pass. `check_fefo.py` trên `pl_moc` FAIL ("Khách sạn (60%) không giữ lô 11 tháng"), bản trên `main` cũng FAIL y như vậy nên không do thay đổi này; với `--src pl_seed_fefo` (database đã dùng khi ghi kết quả trong [fefo_pick.md](fefo_pick.md#kiểm-tra)) thì pass. Nguyên nhân nằm ở dữ liệu `pl_moc` (81 đơn đã xác nhận, lô của bộ seed cũ), chưa tra cụ thể.

Ngày 18/11/2026 `pl_moc` được dựng lại từ seed hiện tại bằng `scripts/rebuild_main_db.py` ([seed.md](seed.md#dựng-lại-database-chính)): đủ module, 81 đơn ngày mốc còn là báo giá, lô khớp `ton_kho.csv`. Trên `pl_moc` mới cả `check_o2c.py`, `check_route.py`, `check_fefo.py` đều pass, mã thoát 0. Hai giới hạn về `pl_moc` dưới đây chỉ đúng với bản cũ, nay là `pl_moc_old_20261118_0028`.

## Giới hạn

- Kiểm tra chạy qua XML-RPC bằng tài khoản admin, không qua giao diện. Nút trên giao diện gọi cùng phương thức (`button_validate`, `stock.backorder.confirmation`, `sale.advance.payment.inv`, `account.payment.register`), nhưng quyền của người dùng thật (nhân viên kho, kế toán) chưa được thử.
- `pl_moc` đã có 81 đơn ngày mốc được xác nhận, phiếu xuất Ready, nên kế hoạch ở bước 3 xếp cả 84 phiếu. Script chỉ kiểm 3 phiếu của X, Y, Z; xếp tuyến cho 81 phiếu kia do `check_route.py` kiểm.
- `pl_moc` được nạp từ bộ seed trước khi đổi dải lô (commit `65cc8e0`): chỉ 161/377 lô trùng số lô với `seed/demo/ton_kho.csv`. Chạy `seed_import.py` lên bản nhân bản (hay lên `pl_moc`) tạo thêm 216 lô kèm tồn đầu kỳ bên cạnh lô cũ. Kết quả các bước không phụ thuộc chuyện này, nhưng tồn trên bản nhân bản nhiều hơn `pl_moc`.
- Thu tiền chỉ thử *Register Payment* vào sổ *Cash* trên một hóa đơn. Đối chiếu cuối ngày nhiều hóa đơn, chênh lệch tiền tài xế nộp, trả trước, giảm trừ chưa có.
- Hóa đơn ghi ngày chạy script, không phải ngày mốc, nên ngày đến hạn tính từ hôm nay.
- Công nợ có sẵn của Z là một hóa đơn không có sản phẩm, chỉ để đẩy công nợ lên gần hạn mức.
