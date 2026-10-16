# Quét mã vạch

App **Barcodes** đến từ module OCA `stock_barcodes`. Nhóm có thêm hai module:

- `pl_product_barcode`: nút **Generate Barcode** trên form sản phẩm, sinh mã EAN-13 nội bộ.
- `pl_barcode_camera`: quét bằng camera máy tính, giống luồng "Quét hoặc chạm" của bản Odoo Enterprise.

## Cài module

~~~powershell
docker compose run --rm odoo odoo -d <db> -i stock_barcodes,pl_barcode_camera,pl_product_barcode --stop-after-init
docker compose restart odoo
~~~

Sửa file JS, XML template hoặc SCSS trong `static/` thì phải `docker compose restart odoo`, vì Odoo chỉ build lại bundle asset khi khởi động. Sửa file Python hoặc view XML thì chạy lại lệnh trên với `-u <tên module>` thay cho `-i`.

## Cấu hình trong database

Module chỉ tạo sẵn các nhóm tùy chọn (*Picking IN options*, *Picking OUT options*...), không gán vào loại thao tác nào. Chưa gán thì ô *Picking IN* trong app Barcodes hiện danh sách trống. Vào **Inventory > Configuration > Operation Types**, mở từng loại rồi chọn **Barcode option group** ở mục *Barcodes*:

| Operation Type | Barcode option group |
| --- | --- |
| Receipts | Picking IN options |
| Delivery Orders | Picking OUT options |
| Internal Transfers | Picking Internal options |

## Mã vạch cho sản phẩm

Hàng mua về đã có mã EAN in sẵn trên bao bì thì gõ hoặc quét mã đó vào ô **Barcode** của sản phẩm.

Hàng chưa có mã thì bấm **Generate Barcode** trên form sản phẩm (nút ở hàng trên, cạnh *Print Labels*). Module `pl_product_barcode` ghép `200` với 9 chữ số lấy từ sequence `pl_product_barcode.ean13`, rồi thêm chữ số kiểm tra. Sản phẩm đầu tiên nhận `2000000000015`, sản phẩm sau nhận `2000000000022`, cứ thế tăng dần. GS1 dành tiền tố `200`–`299` cho mã nội bộ, nên mã sinh ra không trùng mã EAN thật của nhà sản xuất. Với bộ quy tắc *Default Nomenclature*, tiền tố này không đụng các quy tắc mã cân (`21`), vị trí (`414`), lot (`10`) hay package (`PACK`).

Nút chỉ hiện khi sản phẩm chưa có mã, thuộc loại *Goods* và không có nhiều biến thể. Sản phẩm nhiều biến thể thì sinh mã trên form của từng biến thể. Odoo Community không có sẵn nút này. Module OCA `barcodes_generator_product` làm được việc tương tự nhưng cần thư viện `python-barcode`, mà official image không có.

Sinh mã xong, bấm **Print Labels**, chọn khổ tem rồi **Confirm** để lấy file PDF in tem.

## Quét bằng camera

Có hai chỗ mở camera:

- Menu chính của app Barcodes: bấm hình mã vạch "Scan or tap". Ở màn hình này `stock_barcodes` chỉ nhận mã của *Barcode Actions* (in tại **Inventory > Configuration > Barcodes > Barcode Actions > Print barcodes**). Quét mã sản phẩm ở đây sẽ báo "No action found".
- Màn hình quét của phiếu: nút 📷 trên thanh tím. Mở phiếu bằng nút **Scan barcodes** trên form phiếu, hoặc qua *Barcodes > Picking IN > Receipts*.

Hộp thoại có video camera và ô *Enter a barcode...*. Camera đọc được mã thì hộp thoại tự đóng. Không đọc được thì gõ mã vào ô rồi bấm *Apply*. Mã đi vào Odoo giống hệt mã từ máy quét USB, nên âm báo, số lượng và kiểm tra sản phẩm vẫn do `stock_barcodes` xử lý.

Mã EAN-13 cần khoảng trắng hai bên vạch mới đọc được. Tem từ *Print Labels* đã có sẵn lề trắng. Còn ảnh lấy từ link `/report/barcode/EAN13/<mã>` thì cắt sát vạch, nên khi đưa lên màn hình điện thoại phải để nền trắng xung quanh, đừng để nền đen của trình xem ảnh.

Trình duyệt chỉ cho dùng camera trên `localhost` hoặc HTTPS, nên mở Odoo bằng http://localhost:8069. Lần đầu trình duyệt sẽ hỏi quyền camera; lỡ chặn thì bật lại ở biểu tượng bên trái thanh địa chỉ. Camera MacBook lấy nét cố định, nên tem nhỏ khó đọc: in tem to và giữ cách camera khoảng 15–25 cm.

Không dùng camera thì có thể quét bằng app điện thoại gửi mã sang máy tính như bàn phím. App phải gửi kèm Enter sau mỗi mã và gõ cả chuỗi một lần, vì Odoo chỉ coi là mã quét khi các phím cách nhau dưới 150 ms (tham số hệ thống `barcode.max_time_between_keys_in_ms`).

## Kiểm thử

Ngày 2026-10-16 trên `erp_smoke` (macOS, Odoo 18.0-20260926): cài `pl_barcode_camera` không lỗi. Hộp thoại mở được từ menu chính và từ màn hình quét của `WH/IN/00001`. Nhập mã sản phẩm qua ô *Enter a barcode...* làm số lượng của phiếu tăng từ 0/5 lên 1/5. Ở menu chính, một mã không gắn action nào báo "No action found". Phần đọc mã từ video chưa kiểm được trong lần này, vì trình duyệt dùng để test chặn camera.

Cùng ngày, `pl_product_barcode` sinh mã `2000000000015` cho sản phẩm mới tạo trên giao diện; Odoo xác nhận đây là EAN-13 hợp lệ. *Print Labels* khổ `2 x 7 with price` in ra tem có đúng mã đó. Thư viện ZXing (thư viện hộp thoại camera dùng) đọc được ảnh mã này khi có lề trắng, và không đọc được khi ảnh cắt sát vạch.
