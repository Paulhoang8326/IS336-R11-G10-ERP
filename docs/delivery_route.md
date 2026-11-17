# Lập kế hoạch giao hàng

Module `pl_delivery_route` xếp các phiếu xuất kho trong ngày lên các xe giao hàng và sắp thứ tự điểm giao sao cho tổng quãng đường ngắn, không xe nào chở quá tải trọng và không chuyến nào quá số điểm một tài xế giao được. Mỗi chuyến có link Google Maps chỉ đường theo đúng thứ tự điểm, một Batch Transfer gom các phiếu của chuyến, và một phiếu xếp hàng lên xe để in.

~~~text
custom_addons/pl_delivery_route/
├── __manifest__.py
├── models/
│   ├── pl_vehicle.py           # xe giao hàng
│   ├── pl_delivery_plan.py     # kế hoạch, chuyến, điểm dừng, phiếu chưa xếp
│   └── stock_picking.py        # chuyến và thứ tự điểm dừng trên phiếu xuất, tải phiếu (kg)
├── services/
│   ├── vrp.py                  # thuật toán lập tuyến, Python thuần
│   └── maps.py                 # link Google Maps, Python thuần
├── i18n/
│   ├── pl_delivery_route.pot   # mẫu: mọi chuỗi giao diện, Odoo xuất ra
│   └── vi.po                   # bản dịch tiếng Việt
├── report/
│   └── loading_sheet.xml       # phiếu xếp hàng lên xe (QWeb)
├── tests/                      # unit test chạy bằng Python thuần
└── views/
~~~

## Cài đặt

Cần database đã nạp seed theo [seed.md](seed.md). Module phụ thuộc `stock` và `stock_picking_batch` (Batch Transfers, có trong Odoo 18 Community); cài module thì Odoo tự cài `stock_picking_batch`.

~~~bash
docker compose run --rm odoo odoo -d pl_moc -i pl_delivery_route --stop-after-init
python3 scripts/seed_import.py --db pl_moc
~~~

~~~powershell
docker compose run --rm odoo odoo -d pl_moc -i pl_delivery_route --stop-after-init
python scripts/seed_import.py --db pl_moc
~~~

Hoặc cài trên giao diện: Apps > Update Apps List, tìm *Phan Lam Delivery Route*. Chạy lại `seed_import.py` sau khi cài để nạp 4 xe trong `seed/demo/xe.csv` vào **Inventory > Configuration > Delivery Vehicles**. Chưa cài module thì script bỏ qua `xe.csv` như trước.

## Dùng trên giao diện

| Menu | Làm gì |
| --- | --- |
| Inventory > Configuration > Delivery Vehicles | Mã xe, loại xe, tải trọng (kg), kho xuất phát. Lưu trữ (archive) xe nghỉ thì xe không được xếp chuyến |
| Inventory > Delivery Planning > Delivery Plans | Tạo kế hoạch: chọn ngày giao, kho, hệ số đường đi (mặc định 1,3), số điểm tối đa mỗi chuyến (*Max Stops per Trip*, mặc định 25; 0 là không giới hạn) |
| Inventory > Operations > Jobs > Batch Transfers | Các lô phiếu do kế hoạch tạo khi xác nhận, mỗi chuyến một lô |

Trên form kế hoạch:

- **Compute Routes** (lập tuyến): lấy các phiếu xuất (loại *Delivery*) của kho, đang *Ready*, có *Scheduled Date* không sau ngày giao và chưa thuộc kế hoạch đã xác nhận nào; chạy thuật toán; ghi kết quả vào thẻ *Trips* và *Unassigned*. Bấm lại thì xóa kết quả cũ và tính lại.
- **Confirm** (xác nhận): ghi chuyến và thứ tự điểm dừng vào từng phiếu xuất (thẻ *Additional Info* của phiếu, hoặc bật cột ở danh sách phiếu); mỗi chuyến tạo một Batch Transfer (`stock.picking.batch`) chứa các phiếu của chuyến, mô tả là mã xe và ngày giao (vd `XE01 - 29/10/2026`, ngày định dạng theo ngôn ngữ người xác nhận), phiếu trong lô sắp theo thứ tự giao, lô ở trạng thái *In progress*; rồi khóa kế hoạch. Phiếu đã thuộc kế hoạch đã xác nhận không được lấy vào kế hoạch khác. Có phiếu đã nằm trong một lô khác thì báo lỗi kèm số phiếu và số lô, không tạo lô nào; gỡ phiếu khỏi lô đó rồi xác nhận lại.
- **Reset to Draft** (về nháp): khi đã lập tuyến nhưng chưa xác nhận; xóa kết quả để sửa ngày, kho, hệ số hoặc số điểm tối đa.

Thẻ *Trips* có mỗi xe một dòng: số điểm, tải (kg), % tải trọng, tổng km và nút **Google Maps**. Bấm vào dòng để xem các điểm dừng theo thứ tự, km từng chặng, km về kho, tất cả link Maps và Batch Transfer của chuyến. Thẻ *Unassigned* liệt kê phiếu không lên xe được kèm lý do: *Heavier than the largest vehicle* (vượt tải trọng xe lớn nhất), *Not enough vehicles* (không đủ xe) hoặc *Missing coordinates* (thiếu tọa độ).

Với bộ demo: các đơn được xác nhận ngày 29/10/2026 (ngày mốc), nên phiếu xuất có *Scheduled Date* là 29/10/2026. Tạo kế hoạch với ngày giao **29/10/2026** (hoặc sau đó) thì lấy được cả 81 phiếu. Số kế hoạch dạng `DP/2026/0001`. Database mới mà xác nhận đơn vào hôm nay thì phiếu mang ngày hôm nay, khi đó chọn ngày giao là hôm nay.

### Phiếu xếp hàng lên xe

Nút **Print** trên form chuyến, hoặc chọn các chuyến ở danh sách rồi *Print > Loading Sheet*, in phiếu xếp hàng (PDF). Đầu phiếu: xe, tải trọng, ngày giao, tổng tải, tổng km, số điểm. Thân phiếu liệt kê điểm dừng **ngược thứ tự giao**: điểm giao cuối xếp lên xe trước, nằm trong cùng thùng xe; điểm giao đầu tiên xếp sau cùng, sát cửa xe. Mỗi điểm ghi thứ tự xếp, thứ tự giao, khách, địa chỉ, số phiếu xuất, tải kg và từng dòng hàng đã giữ (mã, tên, số lượng, đơn vị, lô) lấy từ move line của phiếu. Phiếu có dòng chú thích "Xếp theo thứ tự từ trên xuống; điểm giao đầu tiên nằm sát cửa xe." (bản tiếng Anh khi người dùng để giao diện tiếng Anh).

### Tải của phiếu

Tải phiếu = tổng (số lượng × cân nặng sản phẩm) của các dòng hàng chưa hủy. Số lượng dùng là `product_qty` của move, tức đã quy về đơn vị tính của sản phẩm; dòng bán theo thùng trong seed vẫn lưu số đơn vị lẻ (thùng 12 chai ghi 12), còn cân nặng sản phẩm là cân nặng một đơn vị lẻ (`kg_moi_thung / so_dvt_moi_thung`, 4 chữ số thập phân do `seed_import.py` tăng độ chính xác *Stock Weight*). Database cài cân nặng theo pound thì đổi sang kg.

### Google Maps

Link dạng [Maps URLs](https://developers.google.com/maps/documentation/urls/get-started#directions-action) `https://www.google.com/maps/dir/?api=1&origin=...&destination=...&waypoints=...&travelmode=driving`, đi từ kho qua các điểm theo thứ tự rồi về kho, mỗi điểm ghi bằng tọa độ. Google cho tối đa 9 waypoint mỗi link (chỉ 3 khi mở trên trình duyệt điện thoại; mở bằng app Google Maps hoặc máy tính thì được 9). Chuyến có hơn 9 điểm thì chia thành nhiều đoạn liên tiếp, đoạn sau bắt đầu từ điểm cuối của đoạn trước, mỗi đoạn một link; ví dụ chuyến 20 điểm có 22 vị trí (kể cả kho đi và về) thành 3 đoạn: kho → điểm 10, điểm 10 → 20, điểm 20 → kho.

## Ngôn ngữ giao diện

Chữ trên giao diện viết bằng tiếng Anh trong code; bản dịch tiếng Việt nằm ở `i18n/vi.po`. Menu, nút, nhãn trường, trạng thái, lý do chưa xếp và thông báo lỗi đều đổi theo ngôn ngữ của người dùng. Dữ liệu nhập vào (tên xe, tên khách) giữ nguyên.

| Ngôn ngữ | Menu |
| --- | --- |
| English | Inventory > Delivery Planning > Delivery Plans; Inventory > Configuration > Delivery Vehicles |
| Tiếng Việt | Tồn kho > Giao hàng > Kế hoạch giao hàng; Tồn kho > Cấu hình > Xe giao hàng |

**Đổi ngôn ngữ của một người dùng**: bấm avatar góc trên bên phải > *Preferences* (*Tùy chọn*) > *Language*, chọn *Vietnamese / Tiếng Việt* rồi lưu. Danh sách chưa có tiếng Việt thì thêm trước ở **Settings > General Settings > Languages > Add Languages**. Mỗi người dùng chọn ngôn ngữ riêng. Database `pl_moc` hiện chưa bật tiếng Việt, cần *Add Languages* trước.

**Sửa một bản dịch**: sửa dòng `msgstr` trong `vi.po`, rồi nạp lại:

~~~bash
docker compose run --rm odoo odoo -d <database> -u pl_delivery_route --i18n-overwrite --stop-after-init
docker compose restart odoo
~~~

Thiếu `--i18n-overwrite` thì Odoo giữ bản dịch cũ đã có trong database.

**Thêm chuỗi mới trong code**: chuỗi trong Python phải bọc `_("...")`; chuỗi trong view XML và tên trường thì Odoo tự lấy. Sau khi cài code mới, xuất lại mẫu ở **Settings > Translations > Import / Export > Export Translation** (bật Developer Mode; chọn *New Language (Empty translation template)*, định dạng PO, module `pl_delivery_route`), lưu đè `i18n/pl_delivery_route.pot`, rồi thêm các mục `msgid` mới cùng `msgstr` tiếng Việt vào `vi.po`. Chuỗi chưa có bản dịch thì hiện tiếng Anh.

## Thuật toán

Mã ở `custom_addons/pl_delivery_route/services/vrp.py`, docstring giải thích từng bước (giao diện Odoo hiện lý do bằng tiếng Anh như ở trên). Tóm tắt:

0. **Gộp theo khách**: mọi phiếu xuất của cùng một khách (cùng địa chỉ giao) thành một điểm giao, tải là tổng tải các phiếu.
1. **Loại điểm không xếp được**: điểm thiếu tọa độ; điểm nặng hơn xe lớn nhất, lý do "vượt tải trọng xe lớn nhất".
2. **Khoảng cách**: haversine (km, khoảng cách chim bay trên mặt cầu) × hệ số đường đi.
3. **Clarke-Wright savings, bản song song**: mỗi điểm khởi đầu là một tuyến kho → điểm → kho. Tính s(i, j) = d(kho, i) + d(kho, j) − d(i, j) cho mọi cặp, duyệt theo s giảm dần. Gộp tuyến của i và tuyến của j qua cạnh i–j khi hai điểm thuộc hai tuyến khác nhau và cùng nằm ở đầu hoặc cuối tuyến của mình. Không gộp nếu tổng số điểm của hai tuyến vượt số điểm tối đa mỗi chuyến (một tài xế chỉ giao được số điểm có hạn trong ngày); điều kiện này xét trước điều kiện tải. Vì đội xe không đồng nhất, trước khi gộp xếp thử tải các tuyến lên đội xe bằng first-fit decreasing (tuyến nặng nhất vào xe lớn nhất): nếu có tuyến không vừa xe nào trong khi còn xe trống thì không gộp. Số tuyến còn nhiều hơn số xe thì vẫn cho gộp tiếp, vì gộp làm giảm số tuyến. Hết danh sách cặp thì dừng.
4. **Gán xe**: first-fit decreasing, mỗi xe một tuyến. Tuyến không còn xe: các điểm của nó vào danh sách chưa xếp, lý do "không đủ xe".
5. **2-opt** trên từng tuyến kho → điểm → … → kho: đảo một đoạn con nếu làm tổng km giảm thật sự, lặp tới khi không còn đảo nào làm ngắn hơn.
6. **Kết quả**: mỗi tuyến có xe, thứ tự điểm, tải, km từng chặng, tổng km; danh sách chưa xếp kèm lý do.

Kết quả tất định: mọi phép sắp xếp có khóa phụ là id, nên cùng đầu vào luôn ra cùng kết quả.

Clarke-Wright chỉ tối ưu quãng đường nên khi không giới hạn số điểm sẽ dồn hàng lên ít xe nhất có thể: với bộ demo, 80 điểm (5,9 tấn) chỉ dùng 3 xe, XE03 giao 35 điểm và chở 99% tải, XE02 không có chuyến. Giới hạn số điểm buộc thuật toán chia nhỏ tuyến, đổi lại tổng km tăng.

Chọn mặc định 25 điểm: với bộ demo, 25 dùng đủ 4 xe và chỉ còn đơn 081 chưa xếp, nên giữ đúng giá trị đề ra. Kết quả thử trên seed (bằng `vrp.py`, không qua Odoo):

| Số điểm tối đa | Số xe dùng | Điểm mỗi xe (XE01/02/03/04) | Chưa xếp ngoài 081 | Tổng km |
| --- | --- | --- | --- | --- |
| Không giới hạn | 3 | 16 / 0 / 35 / 29 | 0 | 48,3 |
| 15 | 4 | 14 / 15 / 15 / 15 | 21 | 49,3 |
| 18 | 4 | 18 / 18 / 18 / 18 | 8 | 56,3 |
| 19 | 4 | 19 / 19 / 19 / 19 | 4 | 57,2 |
| **20** | 4 | 20 / 20 / 20 / 20 | 0 | 58,8 |
| 21 | 4 | 16 / 21 / 21 / 21 | 1 | 61,7 |
| 22 | 4 | 14 / 22 / 22 / 22 | 0 | 61,5 |
| 23 | 4 | 23 / 11 / 23 / 23 | 0 | 60,4 |
| 24 | 4 | 24 / 8 / 24 / 24 | 0 | 59,2 |
| **25** (mặc định) | 4 | 25 / 5 / 25 / 25 | 0 | 58,5 |
| 26–28 | 4 | XE02 còn 3–4 điểm | 0 | 55,1–56,0 |
| 29 | 3 | 22 / 0 / 29 / 29 | 0 | 51,1 |
| 30 | 4 | 19 / 1 / 30 / 30 | 0 | 52,6 |
| 31–35 | 3 | XE02 không chạy | 0 | 48,3–49,8 |

20 là giá trị nhỏ nhất đạt điều kiện và chia đều nhất (20 điểm mỗi xe), nhưng kết quả không đơn điệu: 21 lại sót 1 điểm, 29 và từ 31 trở lên lại bỏ XE02, vì Clarke-Wright gộp tham lam, tuyến chốt sớm không tách lại được. Đổi số điểm tối đa thì nên lập tuyến lại và xem thẻ *Unassigned*. Với 25, XE02 chỉ còn 5 điểm vì 3 xe kia đã chạm giới hạn; muốn chia đều hơn thì hạ xuống 20 trên form kế hoạch.

## Các điểm đơn giản hóa

- Khoảng cách là đường chim bay × hệ số (mặc định 1,3), không phải đường bộ thật; không gọi API bản đồ. Km trên kế hoạch là ước lượng, Google Maps sẽ cho số khác.
- Giới hạn số điểm mỗi chuyến thay cho giới hạn thời gian làm việc của tài xế. Chưa xét khung giờ giao của khách, thời gian dỡ hàng ở mỗi điểm, tắc đường, hay thể tích hàng.
- Mỗi xe chạy 1 chuyến/ngày, xuất phát và quay về kho của xe.
- Không chia hàng của một khách lên nhiều xe. Khách đặt nặng hơn xe lớn nhất thì cả khách nằm trong danh sách chưa xếp (đơn `DB<ngày mốc>-081` khoảng 3 tấn trong bộ demo), cần xử lý tay: tách phiếu, thuê xe ngoài hoặc giao 2 ngày.
- Chỉ xét tải theo kg, không xét thể tích thùng xe.
- Clarke-Wright và 2-opt là heuristic: kết quả tốt nhưng không bảo đảm ngắn nhất.
- Tọa độ khách trong seed là điểm ngẫu nhiên quanh Cần Thơ, không khớp địa chỉ ([seed_data.md](seed_data.md)).

## Kiểm thử

Unit test cho `vrp.py` và `maps.py`, không cần Odoo:

~~~bash
python3 -m unittest discover -s custom_addons/pl_delivery_route/tests -v
~~~

Kiểm tra: mỗi điểm xuất hiện đúng 1 lần (trong tuyến hoặc danh sách chưa xếp), không tuyến nào vượt tải xe được gán, không tuyến nào vượt số điểm tối đa, không giới hạn (None hoặc 0) cho kết quả y như trước khi có giới hạn, giới hạn 1 điểm với 4 xe và 10 điểm ra đúng 4 tuyến và 6 điểm "không đủ xe", điểm nặng hơn xe lớn nhất nằm trong danh sách chưa xếp, 2-opt không làm tăng km, chạy hai lần cùng kết quả, link Maps đúng thứ tự và không quá 9 waypoint; chạy cả trên bộ `seed/demo/`.

Chạy trọn luồng trên Odoo bằng `scripts/check_route.py` (cần Odoo đang chạy và `pl_moc` đã nạp seed, cách đặt mật khẩu như [scripts/seminar3/README.md](../scripts/seminar3/README.md)):

~~~bash
python3 scripts/check_route.py          # xong thì xóa database tạm
python3 scripts/check_route.py --keep   # giữ pl_route_check để xem trên giao diện
python3 scripts/check_route.py --max-stops 20   # số điểm tối đa mỗi chuyến, mặc định theo kế hoạch (25)
~~~

Script nhân bản `pl_moc` thành `pl_route_check` (không sửa `pl_moc`), cài module, nạp xe, xác nhận các đơn bán của ngày mốc và giữ hàng cho phiếu xuất, tạo kế hoạch cho ngày mốc, lập tuyến hai lần (phải ra cùng kết quả), in bảng theo xe (số điểm, tải, % tải, km, link Maps) và danh sách chưa xếp, rồi xác nhận kế hoạch. Dừng với `FAIL` nếu có xe quá tải, chuyến vượt số điểm tối đa, xe không có chuyến, phiếu bị thiếu hoặc trùng, phiếu chưa xếp ngoài đơn 081, hay sau khi xác nhận số Batch Transfer khác số chuyến hoặc phiếu nằm sai lô.

## Đã kiểm tra

Ngày 17/11/2026 trên macOS, Odoo 18.0-20260926, bản nhân bản của `pl_moc` (81 phiếu xuất Ready, ngày dự kiến 29/10/2026), tối đa 25 điểm mỗi chuyến: cài mới và nâng cấp (`-u pl_delivery_route`) không có cảnh báo hay lỗi trong log, `check_route.py` pass.

| Xe | Tải trọng | Số điểm | Tải kg | % tải | Km | Số link Maps | Batch |
| --- | --- | --- | --- | --- | --- | --- | --- |
| XE01 | 1.500 | 25 | 1.455,7 | 97,0 | 18,9 | 3 | BATCH/00001 |
| XE02 | 1.500 | 5 | 697,1 | 46,5 | 3,1 | 1 | BATCH/00002 |
| XE03 | 2.500 | 25 | 2.109,9 | 84,4 | 19,6 | 3 | BATCH/00003 |
| XE04 | 2.500 | 25 | 1.676,6 | 67,1 | 16,8 | 3 | BATCH/00004 |

Tổng 5.939,3 kg, 58,4 km. Chưa xếp: `PL/OUT/00001` (`DB20261029-081`, 3.019,8 kg), *Heavier than the largest vehicle*. So với khi chưa giới hạn số điểm (ngày 16/11/2026: XE01 16 điểm 10,3 km, XE02 không chạy, XE03 35 điểm 21,5 km, XE04 29 điểm 16,5 km, tổng 48,3 km), tổng quãng đường tăng 10,1 km (khoảng 21%), đổi lại cả 4 xe đều chạy và không tài xế nào giao quá 25 điểm.

Batch Transfer mở ở Inventory > Operations > Jobs > Batch Transfers thấy đủ phiếu của chuyến (BATCH/00001 có 25 phiếu Ready). Phiếu xếp hàng của XE02 in ra PDF đúng thứ tự ngược (điểm xếp 1 là điểm giao 5), mỗi dòng hàng có lô; bản tiếng Việt in đúng câu chú thích.
