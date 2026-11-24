# Kiểm tra Procure-to-Pay

`scripts/check_p2p.py` chạy quy trình mua hàng, nhận hàng, hóa đơn nhà cung cấp (NCC), trả tiền và các ngoại lệ phía mua (giao thiếu, trả hàng, chưa nhận hàng) trên bản nhân bản của database chính, kiểm từng bước rồi xóa bản đó. Phía bán có [check_o2c.py](o2c_check.md).

Không ghi gì lên `pl_moc`: script chỉ đọc danh sách module của `pl_moc`, mọi thao tác khác làm trên `pl_p2p_check`.

## Chạy

~~~bash
python3 scripts/check_p2p.py                      # nhân bản pl_moc thành pl_p2p_check, xong thì xóa
python3 scripts/check_p2p.py --keep               # giữ pl_p2p_check để xem trên giao diện
python3 scripts/check_p2p.py --src pl_seed_fefo   # nhân bản database khác
python3 scripts/check_p2p.py --method-purchase    # thử âm: phải FAIL ở bước 2
~~~

~~~powershell
python scripts/check_p2p.py
python scripts/check_p2p.py --keep
~~~

Mật khẩu như `scripts/seminar3`: admin lấy từ `ODOO_PASSWORD` (không có thì hỏi), master từ `ODOO_MASTER_PASSWORD` hoặc `admin_passwd` trong `config/odoo.conf`. Chạy mất khoảng 5 giây. Sai điều nào thì in `FAIL: ...`, bảng tóm tắt và mã thoát khác 0; database check vẫn bị xóa, trừ khi có `--keep`.

## Các bước

Ngày mốc lấy từ `seed/demo/don_ban.csv` (bộ hiện tại: 29/10/2026), như `check_o2c.py`. Hạn dùng của mọi lô nhận = ngày mốc + *Expiration Time*. Mỗi đơn mua 10 thùng của cùng một mã: mã dầu ăn Wilmar (`NCC01`) đầu tiên trong `san_pham.csv` có quy cách thùng.

| Bước | Làm gì | Kiểm tra |
| --- | --- | --- |
| 0. Module, seed | In module nguồn đang thiếu trong số `purchase_stock`, `account`, `product_expiry`, `pl_fefo_pick` (`pl_fefo_pick` chỉ để `seed_import.py` ghi được hạn dùng tối thiểu của khách); cài phần thiếu trên bản nhân bản. Chạy lại `seed_import.py` lên bản nhân bản | `seed_import.py` không cảnh báo; Purchase Settings để *Bill Control* = `receive`; 150 sản phẩm seed có `purchase_method = receive` |
| 1. Ca chuẩn | Đơn A: nhận đủ 10 thùng, lô `LP2PA`, hạn dùng; *Create Bill*, ghi *Bill Date*, post; *Register Payment* toàn bộ từ sổ *Bank* | Lô vào một ô của `Dãy A - Wilmar` theo quy tắc cất hàng (các lần nhận sau cũng kiểm điều này); hóa đơn 10 thùng, tiền hàng = số lượng × giá nhập của seed, đến hạn = ngày hóa đơn + hạn thanh toán của NCC; hóa đơn *Paid*; công nợ phải trả NCC về 0 |
| 2. Giao thiếu, có backorder | Đơn B: nhận 6/10, *Create Backorder*, lập hóa đơn. Nhận nốt 4 từ backorder, lập hóa đơn lần 2 | Hóa đơn đầu 6 thùng, không phải 10; đúng một backorder còn 4 thùng; hóa đơn lần 2 là 4 thùng, tổng 10 |
| 3. Giao thiếu, không backorder | Đơn C: nhận 7/10, *No Backorder*, lập hóa đơn | Hóa đơn 7 thùng; đơn không còn move mở, *Billing Status* là *Fully Billed* |
| 4. Trả hàng lỗi | Sau bước 1: *Return* trên phiếu nhập của đơn A, 2 thùng, validate phiếu trả. *Create Bill* trên đơn A, post | Phiếu trả lấy đúng lô `LP2PA`, về *Vendors*; tồn lô giảm 2 thùng; Odoo lập vendor credit note 2 thùng, post được; công nợ ròng trên sổ = hóa đơn - credit note - đã trả |
| 5. Chưa nhận hàng | Đơn D: xác nhận, chưa nhận, *Create Bill* | Odoo từ chối (`UserError`), không có hóa đơn nào sinh ra |

Cuối cùng script in bảng tóm tắt từng bước PASS/FAIL kèm số đơn mua, phiếu nhập, phiếu trả, hóa đơn, payment, credit note. Chạy với `--keep` rồi tìm các số này trên giao diện để xem lại.

### Bill Control theo số lượng thực nhận

Nhóm lập hóa đơn NCC theo số lượng thực nhận. Khác với bên bán, đây đã là mặc định của Odoo 18, đọc trong source của image `odoo:18.0-20260926`:

- `addons/purchase/models/product.py`: `product.template.purchase_method`, nhãn *Control Policy*, lựa chọn `purchase` (*On ordered quantities*) và `receive` (*On received quantities*), là trường tính, lưu, sửa được (`compute='_compute_purchase_method'`, `precompute=True`, `store=True`, `readonly=False`). `_compute_purchase_method` đặt `purchase` cho sản phẩm `type == 'service'`; loại khác lấy giá trị mặc định của trường, không có thì `receive`.
- `addons/purchase/models/res_config_settings.py`: setting `default_purchase_method`, nhãn *Bill Control*, lựa chọn `purchase` (*Ordered quantities*) / `receive` (*Received quantities*), `default="receive"`, `default_model="product.template"`. Nằm ở Purchase > Configuration > Settings > Invoicing. Setting chỉ ghi `ir.default` cho sản phẩm tạo sau; sản phẩm đã có giữ nguyên.
- `addons/purchase/models/purchase_order_line.py`, `_compute_qty_invoiced`: `qty_to_invoice` = đã nhận - đã lập hóa đơn với `receive`, = đã đặt - đã lập hóa đơn với `purchase`.

`seed_import.py` vẫn đặt *Bill Control* = `receive` và ghi `purchase_method = receive` cho từng sản phẩm của seed ([seed_data.md](seed_data.md#dữ-liệu-vào-odoo-ở-đâu)), để kết quả không phụ thuộc mặc định của Odoo hay ai đó đã đổi tay. Database đang để mặc định thì script không đổi gì (`pl_moc`: 0 cài đặt, 0 sản phẩm phải sửa).

`--method-purchase` ghi `purchase_method = purchase` cho sản phẩm trên bản nhân bản sau khi chạy `seed_import.py`, để chắc bước 2 bắt được lỗi này.

### Vendor credit note khi trả hàng

Credit note được tạo từ đơn mua, bằng chính nút *Create Bill*. Các điểm đọc trong source:

1. *Return* trên phiếu nhập mở `stock.return.picking`, số lượng mặc định 0, người dùng điền số trả. `addons/stock_account/wizard/stock_picking_return.py` thêm `to_refund` (*Update quantities on SO/PO*), mặc định bật, chỉ hiện ở developer mode. Phiếu trả nối với move nhập gốc nên Odoo giữ đúng lô đã nhận, không chọn lô khác theo FEFO.
2. Validate phiếu trả thì `qty_received` giảm từ 10 còn 8 thùng (`addons/purchase_stock/models/purchase_order_line.py`, chỉ trừ khi `to_refund`). Đã lập hóa đơn 10 nên `qty_to_invoice` = -2, đơn về *Waiting Bills*.
3. *Create Bill* trên đơn lập chứng từ có tổng âm, `action_create_invoice` (`addons/purchase/models/purchase_order.py`) đổi nó thành credit note (`action_switch_move_type`): `move_type = in_refund`, số lượng dương 2 thùng.

Cách còn lại là nút *Credit Note* trên hóa đơn gốc (`account.move.reversal`). Cách này chép nguyên số lượng hóa đơn (thử trên hóa đơn 7 thùng: credit note nháp 7 thùng), phải sửa tay thành số trả. Nháp đó cũng được tính vào số đã lập hóa đơn của đơn mua. Vì vậy script làm từ đơn mua: số lượng do Odoo tính theo phiếu trả.

Hóa đơn A đã trả đủ từ trước nên credit note để lại công nợ ròng âm: NCC nợ lại 475.632 đ, cấn trừ vào hóa đơn sau hoặc nhận hoàn tiền.

### Trả tiền NCC

*Register Payment* từ sổ *Bank* ra hóa đơn *Paid* ngay, vì bản Community không có đối soát sao kê: khi phương thức thanh toán chưa có tài khoản trung gian, `account.payment` tự lấy tài khoản *Outstanding Payments* để sinh bút toán (`addons/account/models/account_payment.py`, `create`).

## Ngoại lệ quy trình mua hàng

| Ngoại lệ | Xử lý nghiệp vụ | Thao tác trên Odoo | Đã kiểm ở bước |
| --- | --- | --- | --- |
| NCC giao thiếu, chờ giao bù | Nhận số thực giao, trả tiền phần đã nhận, phần thiếu chờ đợt sau | Phiếu nhập: sửa số lượng thực nhận, *Validate* > *Create Backorder*; *Create Bill* ra hóa đơn theo số đã nhận. Đợt sau nhận trên backorder rồi *Create Bill* lần nữa | 2 |
| NCC giao thiếu, hủy phần thiếu | Nhận số thực giao, không chờ phần thiếu, trả tiền phần đã nhận | Phiếu nhập: sửa số lượng thực nhận, *Validate* > *No Backorder*; *Create Bill* | 3 |
| Hàng lỗi hoặc cận date lúc nhận, đã nhập kho | Trả NCC, yêu cầu ghi giảm công nợ; đã trả tiền thì cấn trừ vào hóa đơn sau hoặc nhận hoàn tiền | Phiếu nhập: *Return*, điền số trả, kiểm lô, *Validate*; đơn mua: *Create Bill* ra vendor credit note, ghi ngày, *Confirm* | 4 |
| Hàng lỗi hoặc cận date lúc nhận, từ chối ngay | Không nhập phần bị từ chối, xử lý như giao thiếu. Odoo không tự chặn lô cận date khi nhận, nhân viên kho kiểm hạn dùng | Chỉ nhập số lượng đạt, *Validate* > *Create Backorder* (đổi hàng) hoặc *No Backorder* (không lấy nữa) | 2, 3 (cùng thao tác) |
| Hóa đơn NCC đến trước hàng | Chưa nhận hàng thì chưa ghi hóa đơn từ đơn mua, chờ nhận hàng | *Create Bill* bị Odoo từ chối; nhận hàng xong mới lập | 5 |
| NCC giao trễ | Theo dõi ngày dự kiến nhận, nhắc NCC, dời ngày hoặc hủy đơn | Đơn mua: *Expected Arrival* (`date_planned`); phiếu nhập quá *Scheduled Date* nằm ở mục *Late* của Receipts; đổi *Expected Arrival* khi NCC hẹn lại | Chỉ mô tả |
| Sai giá trên hóa đơn NCC | Đối chiếu giá hóa đơn với đơn mua; giá NCC đúng theo thỏa thuận thì ghi theo hóa đơn, không đúng thì yêu cầu NCC xuất lại | Sửa *Price* trên hóa đơn nháp trước khi *Confirm*; đã post thì *Reset to Draft* hoặc lập credit note | Chỉ mô tả |

## Kết quả

Chạy ngày 24/11/2026 trên macOS, Odoo 18.0-20260926, database nguồn `pl_moc` (dựng lại 18/11/2026, không thiếu module nào).

Mã dùng: `NCC01-0027` Dầu Ô-liu Pomace Olivoilà 750ML, thùng 6 chai, giá nhập 36.700 đ/chai, VAT 8%, hạn dùng 540 ngày. NCC: `NCC01` Wilmar, hạn thanh toán 30 ngày.

| Bước | Kết quả | Chứng từ | Chi tiết |
| --- | --- | --- | --- |
| 0. Module, seed | PASS | | Không cần cài thêm; `seed_import.py` 0 cảnh báo, 0 cài đặt và 0 sản phẩm phải sửa; *Bill Control* `receive`, 150 sản phẩm `receive` |
| 1. Ca chuẩn | PASS | `P00001`, `PL/IN/00001`, `BILL/2026/11/0001`, `PBNK1/2026/00001` | 10 thùng lô `LP2PA` vào `PL/Stock/Dãy A - Wilmar/A-03-1`; hóa đơn 10 thùng 2.378.160 đ, đến hạn 24/12/2026, *Paid*; công nợ 0 |
| 2. Giao thiếu, có backorder | PASS | `P00002`, `PL/IN/00002`, `BILL/2026/11/0002`; backorder `PL/IN/00003`, `BILL/2026/11/0003` | Nhận 6, hóa đơn 6 thùng (1.426.896 đ); backorder 4 thùng, hóa đơn 4 thùng (951.264 đ); tổng 10 |
| 3. Giao thiếu, không backorder | PASS | `P00003`, `PL/IN/00004`, `BILL/2026/11/0004` | Nhận 7, hóa đơn 7 thùng (1.664.712 đ), không move mở |
| 4. Trả hàng lỗi | PASS | `PL/OUT/00001`, `RBILL/2026/11/0001` | Trả 2 thùng lô `LP2PA`, tồn lô 10 còn 8; credit note 2 thùng 475.632 đ; công nợ ròng 2.378.160 - 475.632 - 2.378.160 = -475.632 đ |
| 5. Chưa nhận hàng | PASS | `P00004`, `PL/IN/00005` | *Create Bill* bị từ chối: "There is no invoiceable line. If a product has a control policy based on received quantity, please make sure that a quantity has been received." |

Chạy 3 lần liên tiếp đều PASS, mã thoát 0, ra cùng số chứng từ; sau mỗi lần không còn database `pl_p2p_check`.

Thử âm với `--method-purchase`: bước 0–1 PASS, bước 2 FAIL, mã thoát 1:

~~~text
FAIL: BILL/2026/11/0002 (P00002) lập 10 thùng, cần 6 thùng (đặt 10, đã nhận 6): hóa đơn không theo số lượng thực nhận
~~~

Thử riêng `seed_import.py` trên một bản nhân bản đã bị đổi sang *Ordered quantities* (cả setting lẫn 150 sản phẩm): script đưa về `receive` (1 cài đặt, 150 sản phẩm), chạy lần hai không sửa gì, 0 cảnh báo.

Cùng ngày, `check_o2c.py`, `check_fefo.py`, `check_route.py` trên `pl_moc` và `scripts/seminar3/check_flow.py` (mặc định nhân bản `phanlam_seminar3`) đều pass, mã thoát 0. Ba script đầu cũng pass trên bản nhân bản tạm của `pl_moc` đã chạy `seed_import.py` mới (đã xóa). `seed_import.py` mới chưa chạy lên `pl_moc` thật.

`check_flow.py` trên database seminar dựng lại từ `pl_moc` mới (`make_seminar_db.py`) thì FAIL ở bước xác nhận đơn bán ("reserved 0, mong đợi 30"). Không do thay đổi này: dựng từ `pl_moc` chưa chạy `seed_import.py` mới cũng FAIL y như vậy. Nguyên nhân: `pl_moc` mới có `pl_fefo_pick`, còn `phanlam_seminar3` hiện có thì không; lô của kịch bản hạn 30/04/2027, ngày 24/11/2026 chỉ còn khoảng 29% hạn dùng, dưới mức 60% của khách sạn nên không được giữ. `check_flow.py` chưa sửa; đừng chạy `make_seminar_db.py --force` khi chưa xử lý việc này.

## Giới hạn

- Kiểm tra chạy qua XML-RPC bằng tài khoản admin, không qua giao diện; quyền của nhân viên kho, kế toán chưa được thử. Script tự ghi hạn thanh toán vào đơn mua, vì trên giao diện trường này do `onchange_partner_id` điền.
- Một NCC, một mã hàng. Đơn nhiều dòng, giao dư, trả hàng nhiều lần chưa thử.
- Nhận một bước thẳng vào `PL/Stock`, như cấu hình của `pl_moc`. Nhận hai bước do `check_flow.py` kiểm.
- Hóa đơn B, C và credit note của A để ngỏ: chưa thử cấn trừ credit note vào hóa đơn khác hay nhận hoàn tiền.
- Chưa kiểm bút toán kho (1560, 1510) của phiếu trả và credit note, chỉ kiểm công nợ phải trả.
- Hóa đơn, credit note ghi ngày chạy script, không phải ngày mốc.
- Giao trễ và sai giá trên hóa đơn chỉ mô tả, chưa có bước kiểm.
- 3-way matching (*module_account_3way_match*) là tính năng Enterprise, Community không có.
- Lệnh PowerShell chưa chạy thử trên Windows.
