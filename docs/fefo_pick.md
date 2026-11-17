# Giữ hàng theo hạn dùng tối thiểu của khách

Module `pl_fefo_pick` ("Phan Lam FEFO Pick", `custom_addons/pl_fefo_pick/`). Khi giữ hàng (reserve) cho đơn bán, Odoo chỉ lấy các lô còn đủ hạn dùng mà khách yêu cầu vào ngày giao. Giữa các lô đạt, vẫn lấy lô hết hạn sớm nhất trước (FEFO).

Ví dụ: minimart nhận hàng còn ít nhất 50% hạn dùng. Kho có Aquafina 1500 ml lô còn 39%, lô còn 61% và lô còn 94%. Odoo chuẩn giữ lô 39% vì hết hạn sớm nhất; có module thì giữ lô 61%.

## Quy tắc

- Mỗi khách có trường *Min. Shelf Life at Delivery (%)* (`res.partner.pl_min_shelf_life_pct`, số nguyên 0–100, mặc định 0) ở tab *Sales & Purchase*. 0 là không yêu cầu, giữ hàng như Odoo chuẩn. Địa chỉ giao hàng con luôn dùng mức của công ty mẹ (`commercial_partner_id`); Odoo tự chép mức này xuống địa chỉ con và khóa không cho sửa ở đó.
- Ngày mốc là ngày giao dự kiến của dòng hàng (`stock.move.date`, chính là *Scheduled Date* của phiếu), không phải hôm nay. Đơn bán có *Delivery Date* thì ngày giao dự kiến là ngày đó; không có thì Odoo lấy lúc xác nhận đơn cộng thời gian giao của sản phẩm.
- Chỉ áp cho dòng hàng của đơn bán. Khách lấy theo dòng bán (`sale_line_id.order_id`), không có thì theo procurement group của đơn bán, nên bước Pick, Pack của kho xuất nhiều bước cũng được lọc. Phiếu nhập, nội bộ, trả nhà cung cấp, kiểm kê, hủy hàng không bị ảnh hưởng.
- Sản phẩm không bật *Expiration Date* hoặc *Expiration Time* = 0 thì bỏ qua quy tắc. Lô không có hạn dùng thì coi như đạt, giống Odoo chuẩn.
- Không đủ lô đạt thì chỉ giữ phần đạt, phiếu thiếu hàng như bình thường. Không báo lỗi lúc xác nhận đơn hay lúc *Check Availability*. Giao thiếu thì tạo backorder hoặc bỏ phần thiếu theo luồng chuẩn của Odoo.
- Khi *Validate* phiếu của đơn bán, dòng nào có lô không đạt (chọn tay hoặc quét barcode) thì Odoo báo lỗi, liệt kê sản phẩm, lô, % còn lại vào ngày giao và % khách yêu cầu. App Barcodes (OCA `stock_barcodes`) validate qua cùng nút này nên cũng bị chặn. Chỉ xét hàng rời vị trí nội bộ, không xét hàng khách trả về.
- Hiển thị: lô có cột *Remaining Shelf Life (%)* (tính theo hôm nay, không lưu) ở danh sách lô và tab *Dates* của lô; đơn bán và phiếu kho hiện mức tối thiểu của khách (chỉ xem, ẩn khi bằng 0).

## Công thức

~~~text
số ngày tối thiểu = ceil(pct / 100 × expiration_time)
lô đạt khi:       expiration_date >= ngày giao dự kiến + số ngày tối thiểu
% còn lại       = (expiration_date - ngày) / expiration_time × 100
~~~

`expiration_time` là *Expiration Time* của sản phẩm (ngày); seed đặt bằng số tháng hạn dùng × 30. Đúng bằng ngưỡng là đạt. So sánh theo thời điểm như Odoo: hạn dùng trong seed là 00:00 giờ Việt Nam ngày hết hạn, phiếu giao lúc 08:00, nên lô hết hạn đúng ngày tối thiểu đã quá hạn 8 giờ khi giao và không đạt. Các hàm này nằm trong `services/shelf_life.py`, viết bằng Python thuần.

Ví dụ với Aquafina 1500 ml (`NCC02-0002`, 540 ngày), giao 08:00 ngày 29/10/2026:

| Lô | Hết hạn | Còn lúc giao | Tạp hóa, quán ăn 30% (≥ 162 ngày) | Minimart 50% (≥ 270 ngày) | Khách sạn, căn tin 60% (≥ 324 ngày) |
| --- | --- | --- | --- | --- | --- |
| `L251203` | 27/05/2027 (7 tháng) | 38,8% | đạt, giữ trước | không | không |
| `L260402` | 24/09/2027 (11 tháng) | 61,0% | đạt | đạt, giữ trước | đạt, giữ trước |
| `L260929` | 22/03/2028 (17 tháng) | 94,4% | đạt | đạt | đạt |

## Cách làm trong Odoo

Odoo 18 giữ hàng qua `stock.move._update_reserved_quantity` và tính tồn có thể giữ qua `stock.move._get_available_quantity`. Hai hàm này gọi `stock.quant._get_reserve_quantity` / `_get_available_quantity`, rồi `_gather` lấy các quant theo domain của `_get_gather_domain` và sắp theo chiến lược xuất (FEFO: `removal_date, in_date, id`). `product_expiry` loại lô hết hạn đúng ở chỗ này: `stock.move` (product_expiry) đặt context `with_expiration=move.date`, `_get_gather_domain` (stock) thêm điều kiện `expiration_date >= with_expiration hoặc trống`.

Module làm cùng cách, không override `_action_assign`:

| Hàm override | Làm gì | Vì sao |
| --- | --- | --- |
| `stock.move._update_reserved_quantity` | Tính hạn tối thiểu từ khách và `move.date`, đặt vào context `pl_min_expiration_date` rồi gọi super | Điểm giữ hàng của từng move, dùng chung cho xác nhận đơn, *Check Availability*, giữ lại sau khi bỏ giữ, bước Pick của kho nhiều bước |
| `stock.move._get_available_quantity` | Như trên | Odoo dùng hàm này để biết còn giữ được bao nhiêu (trạng thái thiếu hàng, giữ một phần); thiếu thì Odoo tưởng còn hàng ở lô không đạt |
| `stock.quant._get_gather_domain` | Có `pl_min_expiration_date` trong context thì thêm `expiration_date >= ngày đó hoặc trống` vào domain | Đúng chỗ product_expiry lọc lô hết hạn. Chỉ bớt quant, thứ tự FEFO và mọi logic giữ hàng khác (gói, đơn vị, quy cách đóng gói) giữ nguyên |
| `stock.picking.button_validate` | Kiểm các dòng có lô trước khi gọi super, có lô không đạt thì `UserError` | Bắt lô chọn tay, quét barcode; app Barcodes cũng gọi hàm này |

Thêm trường: `res.partner.pl_min_shelf_life_pct` (thêm vào `_commercial_fields`), `sale.order.pl_min_shelf_life_pct` và `stock.picking.pl_min_shelf_life_pct` (related, chỉ xem), `stock.lot.pl_remaining_shelf_life_pct` (tính, không lưu). Không có model mới nên không cần `ir.model.access`.

## Cài

~~~bash
docker compose run --rm odoo odoo -d pl_moc -i pl_fefo_pick --stop-after-init
python3 scripts/seed_import.py --db pl_moc
~~~

~~~powershell
docker compose run --rm odoo odoo -d pl_moc -i pl_fefo_pick --stop-after-init
python scripts/seed_import.py --db pl_moc
~~~

Chạy lại `seed_import.py` để ghi mức hạn dùng tối thiểu của 300 khách từ cột `han_dung_toi_thieu_pct` của `khach_hang.csv` (tạp hóa, quán ăn 30%, minimart 50%, khách sạn, căn tin KCN 60%). Đã cài module thì script không còn cảnh báo `pl_min_shelf_life_pct`. Sửa code Python của module thì `docker compose restart odoo`.

Hàng đã giữ trước khi cài module không tự giữ lại. Muốn áp quy tắc cho phiếu đang chờ thì *Unreserve* rồi *Check Availability*.

## Kiểm tra

Unit test, không cần Odoo:

~~~bash
python3 -m unittest discover -s custom_addons/pl_fefo_pick/tests -v
~~~

Chạy thử trên bản nhân bản của database chính, xong thì xóa bản đó:

~~~bash
python3 scripts/check_fefo.py          # nhân bản pl_moc thành pl_fefo_check
python3 scripts/check_fefo.py --keep   # giữ pl_fefo_check để xem trên giao diện
python3 scripts/check_fefo.py --src pl_seed_fefo   # nhân bản database khác
~~~

Script cài module vào bản nhân bản, chạy lại `seed_import.py` (phải không còn cảnh báo), lấy mã NCC02 có đúng 3 lô trong seed, tạo đơn mới cùng mã, giao 08:00 ngày mốc cho 4 khách: tạp hóa, khách sạn, căn tin KCN (mỗi đơn 2 thùng) và minimart (đặt hơn phần còn giữ được của các lô đạt 5 thùng). Sau đó chọn tay 1 thùng lô 7 tháng cho phiếu minimart rồi *Validate*, làm một phiếu nhập lô mới và một phiếu nội bộ cùng mã, hủy các đơn thử, rồi xác nhận 81 đơn của ngày mốc với *Delivery Date* 08:00 ngày mốc. Sai điều nào thì in `FAIL`, mã thoát khác 0. Đơn của ngày mốc phải có *Delivery Date*: không có thì ngày giao dự kiến là lúc chạy script, hạn dùng còn lại tính theo hôm nay chứ không theo ngày mốc.

Kết quả chạy ngày 17/11/2026 trên macOS, Odoo 18.0-20260926, database nguồn `pl_seed_fefo` (seed ngày mốc 29/10/2026 nạp theo [seed.md](seed.md)):

| Kiểm tra | Phiếu | Trạng thái phiếu / move | Kết quả |
| --- | --- | --- | --- |
| Tạp hóa 30% | `PL/OUT/00001` | Ready / đủ | 2/2 thùng, lô 7 tháng |
| Khách sạn 60% | `PL/OUT/00002` | Ready / đủ | 2/2 thùng, lô 11 tháng |
| Căn tin KCN 60% | `PL/OUT/00003` | Ready / đủ | 2/2 thùng, lô 11 tháng |
| Minimart 50% | `PL/OUT/00004` | Ready / giữ một phần | 39/44 thùng: lô 11 tháng 6, lô 17 tháng 33; không lỗi |
| Minimart chọn tay lô 7 tháng rồi Validate | `PL/OUT/00004` | Ready | `UserError`: lô `L251203` còn 38,8% vào 29/10/2026, khách yêu cầu 50% |
| Phiếu nhập | `PL/IN/00001` | Done | 2 thùng lô mới |
| Phiếu nội bộ | `PL/INT/00001` | Done | 1 thùng lô 7 tháng (FEFO chuẩn, không lọc) |
| 80 đơn ngày mốc, khách 30% | 55 phiếu | 55 Ready, đủ hàng | 209 dòng giữ lô, lô thấp nhất còn 36,0% |
| 80 đơn ngày mốc, khách 50% | 20 phiếu | 20 Ready, đủ hàng | 188 dòng giữ lô, lô thấp nhất còn 50,2% |
| 80 đơn ngày mốc, khách 60% | 5 phiếu | 5 Ready, đủ hàng | 29 dòng giữ lô, lô thấp nhất còn 61,4% |

Không đơn nào giữ lô cận date hay lô hết hạn. Phiếu minimart giữ một phần vẫn hiện Ready vì phiếu giao *As soon as possible*; dòng hàng ở trạng thái giữ một phần. Đơn quá tải `DB20261029-081` không tính trong 80 đơn (lần chạy này cũng Ready).

Cùng ngày: `check_route.py` và `scripts/seminar3/check_flow.py` vẫn pass; `check_route.py` pass cả trên database mới chưa cài và đã cài `pl_fefo_pick`. Trên bản nhân bản của `phanlam_seminar3` (xuất 3 bước) đã cài module, bước Pick của khách 50% giữ lô 11 tháng, khách 0% giữ lô gần hạn nhất; phần này thử tay, chưa có trong script.

## Giới hạn

- Tổng hạn dùng lấy theo *Expiration Time* của sản phẩm, vì lô chưa có ngày sản xuất. Lô có tổng hạn dùng khác của mã (nhà cung cấp đổi hạn dùng) thì % còn lại lệch. Khi có module `pl_stock_lot` ghi ngày sản xuất thì nên tính theo hạn dùng - ngày sản xuất của chính lô.
- Quy tắc tính theo ngày giao dự kiến của từng dòng. Đổi *Scheduled Date* sau khi đã giữ hàng thì hàng đã giữ không đổi theo; cần *Unreserve* rồi *Check Availability*.
- Phiếu xuất của kho nhiều bước nhận hàng từ bước trước (Pick → Out) giữ đúng lô đã lấy ở bước trước; lô đó đã được lọc ở bước Pick.
- `check_route.py` xác nhận đơn không có *Delivery Date*, nên khi đã cài module, hạn dùng còn lại tính theo ngày chạy script. Chạy càng xa ngày mốc thì càng nhiều lô cũ rớt mức; nếu script báo phiếu chưa Ready thì tạo lại seed với ngày mốc gần hơn.
