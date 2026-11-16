# Lập kế hoạch giao hàng

Module `pl_delivery_route` xếp các phiếu xuất kho trong ngày lên các xe giao hàng và sắp thứ tự điểm giao sao cho tổng quãng đường ngắn và không xe nào chở quá tải trọng. Mỗi chuyến có link Google Maps chỉ đường theo đúng thứ tự điểm.

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
├── tests/                      # unit test chạy bằng Python thuần
└── views/
~~~

## Cài đặt

Cần database đã nạp seed theo [seed.md](seed.md). Module chỉ phụ thuộc `stock`.

~~~bash
docker compose run --rm odoo odoo -d pl_moc -i pl_delivery_route --stop-after-init
python3 scripts/seed_import.py --db pl_moc
~~~

~~~powershell
docker compose run --rm odoo odoo -d pl_moc -i pl_delivery_route --stop-after-init
python scripts/seed_import.py --db pl_moc
~~~

Hoặc cài trên giao diện: Apps > Update Apps List, tìm *Phan Lam Delivery Route*. Chạy lại `seed_import.py` sau khi cài để nạp 4 xe trong `seed/demo/xe.csv` vào **Inventory > Configuration > Xe giao hàng**. Chưa cài module thì script bỏ qua `xe.csv` như trước.

## Dùng trên giao diện

| Menu | Làm gì |
| --- | --- |
| Inventory > Configuration > Xe giao hàng | Mã xe, loại xe, tải trọng (kg), kho xuất phát. Lưu trữ (archive) xe nghỉ thì xe không được xếp chuyến |
| Inventory > Giao hàng > Kế hoạch giao hàng | Tạo kế hoạch: chọn ngày giao, kho, hệ số đường đi (mặc định 1,3) |

Trên form kế hoạch:

- **Lập tuyến**: lấy các phiếu xuất (loại *Delivery*) của kho, đang *Ready*, có *Scheduled Date* không sau ngày giao và chưa thuộc kế hoạch đã xác nhận nào; chạy thuật toán; ghi kết quả vào thẻ *Chuyến* và *Chưa xếp*. Bấm lại thì xóa kết quả cũ và tính lại.
- **Xác nhận**: ghi chuyến và thứ tự điểm dừng vào từng phiếu xuất (thẻ *Additional Info* của phiếu, hoặc bật cột ở danh sách phiếu), rồi khóa kế hoạch. Phiếu đã thuộc kế hoạch đã xác nhận không được lấy vào kế hoạch khác.
- **Về nháp**: khi đã lập tuyến nhưng chưa xác nhận; xóa kết quả để sửa ngày, kho hoặc hệ số.

Thẻ *Chuyến* có mỗi xe một dòng: số điểm, tải (kg), % tải trọng, tổng km và nút **Google Maps**. Bấm vào dòng để xem các điểm dừng theo thứ tự, km từng chặng, km về kho và tất cả link Maps của chuyến. Thẻ *Chưa xếp* liệt kê phiếu không lên xe được kèm lý do.

Với bộ demo: các đơn được xác nhận ngày 29/10/2026 (ngày mốc), nên phiếu xuất có *Scheduled Date* là 29/10/2026. Tạo kế hoạch với ngày giao **29/10/2026** (hoặc sau đó) thì lấy được cả 81 phiếu. Database mới mà xác nhận đơn vào hôm nay thì phiếu mang ngày hôm nay, khi đó chọn ngày giao là hôm nay.

### Tải của phiếu

Tải phiếu = tổng (số lượng × cân nặng sản phẩm) của các dòng hàng chưa hủy. Số lượng dùng là `product_qty` của move, tức đã quy về đơn vị tính của sản phẩm; dòng bán theo thùng trong seed vẫn lưu số đơn vị lẻ (thùng 12 chai ghi 12), còn cân nặng sản phẩm là cân nặng một đơn vị lẻ (`kg_moi_thung / so_dvt_moi_thung`, 4 chữ số thập phân do `seed_import.py` tăng độ chính xác *Stock Weight*). Database cài cân nặng theo pound thì đổi sang kg.

### Google Maps

Link dạng [Maps URLs](https://developers.google.com/maps/documentation/urls/get-started#directions-action) `https://www.google.com/maps/dir/?api=1&origin=...&destination=...&waypoints=...&travelmode=driving`, đi từ kho qua các điểm theo thứ tự rồi về kho, mỗi điểm ghi bằng tọa độ. Google cho tối đa 9 waypoint mỗi link (chỉ 3 khi mở trên trình duyệt điện thoại; mở bằng app Google Maps hoặc máy tính thì được 9). Chuyến có hơn 9 điểm thì chia thành nhiều đoạn liên tiếp, đoạn sau bắt đầu từ điểm cuối của đoạn trước, mỗi đoạn một link; ví dụ chuyến 20 điểm có 22 vị trí (kể cả kho đi và về) thành 3 đoạn: kho → điểm 10, điểm 10 → 20, điểm 20 → kho.

## Thuật toán

Mã ở `custom_addons/pl_delivery_route/services/vrp.py`, docstring giải thích từng bước. Tóm tắt:

0. **Gộp theo khách**: mọi phiếu xuất của cùng một khách (cùng địa chỉ giao) thành một điểm giao, tải là tổng tải các phiếu.
1. **Loại điểm không xếp được**: điểm thiếu tọa độ; điểm nặng hơn xe lớn nhất, lý do "vượt tải trọng xe lớn nhất".
2. **Khoảng cách**: haversine (km, khoảng cách chim bay trên mặt cầu) × hệ số đường đi.
3. **Clarke-Wright savings, bản song song**: mỗi điểm khởi đầu là một tuyến kho → điểm → kho. Tính s(i, j) = d(kho, i) + d(kho, j) − d(i, j) cho mọi cặp, duyệt theo s giảm dần. Gộp tuyến của i và tuyến của j qua cạnh i–j khi hai điểm thuộc hai tuyến khác nhau và cùng nằm ở đầu hoặc cuối tuyến của mình. Vì đội xe không đồng nhất, trước khi gộp xếp thử tải các tuyến lên đội xe bằng first-fit decreasing (tuyến nặng nhất vào xe lớn nhất): nếu có tuyến không vừa xe nào trong khi còn xe trống thì không gộp. Số tuyến còn nhiều hơn số xe thì vẫn cho gộp tiếp, vì gộp làm giảm số tuyến. Hết danh sách cặp thì dừng.
4. **Gán xe**: first-fit decreasing, mỗi xe một tuyến. Tuyến không còn xe: các điểm của nó vào danh sách chưa xếp, lý do "không đủ xe".
5. **2-opt** trên từng tuyến kho → điểm → … → kho: đảo một đoạn con nếu làm tổng km giảm thật sự, lặp tới khi không còn đảo nào làm ngắn hơn.
6. **Kết quả**: mỗi tuyến có xe, thứ tự điểm, tải, km từng chặng, tổng km; danh sách chưa xếp kèm lý do.

Kết quả tất định: mọi phép sắp xếp có khóa phụ là id, nên cùng đầu vào luôn ra cùng kết quả.

Clarke-Wright ưu tiên ít quãng đường nên có thể không dùng hết xe: với bộ demo, 80 điểm (5,9 tấn) chỉ cần 3 xe, xe thứ tư không có chuyến.

## Các điểm đơn giản hóa

- Khoảng cách là đường chim bay × hệ số (mặc định 1,3), không phải đường bộ thật; không gọi API bản đồ. Km trên kế hoạch là ước lượng, Google Maps sẽ cho số khác.
- Không có khung giờ giao của khách, thời gian phục vụ ở mỗi điểm, giờ làm việc của tài xế hay tắc đường.
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

Kiểm tra: mỗi điểm xuất hiện đúng 1 lần (trong tuyến hoặc danh sách chưa xếp), không tuyến nào vượt tải xe được gán, điểm nặng hơn xe lớn nhất nằm trong danh sách chưa xếp, 2-opt không làm tăng km, chạy hai lần cùng kết quả, link Maps đúng thứ tự và không quá 9 waypoint; chạy cả trên bộ `seed/demo/`.

Chạy trọn luồng trên Odoo bằng `scripts/check_route.py` (cần Odoo đang chạy và `pl_moc` đã nạp seed, cách đặt mật khẩu như [scripts/seminar3/README.md](../scripts/seminar3/README.md)):

~~~bash
python3 scripts/check_route.py          # xong thì xóa database tạm
python3 scripts/check_route.py --keep   # giữ pl_route_check để xem trên giao diện
~~~

Script nhân bản `pl_moc` thành `pl_route_check` (không sửa `pl_moc`), cài module, nạp xe, xác nhận các đơn bán của ngày mốc và giữ hàng cho phiếu xuất, tạo kế hoạch cho ngày mốc, lập tuyến hai lần (phải ra cùng kết quả), in bảng theo xe (số điểm, tải, % tải, km, link Maps) và danh sách chưa xếp, rồi xác nhận kế hoạch. Dừng với `FAIL` nếu có xe quá tải, phiếu bị thiếu hoặc trùng, hay đơn 081 không nằm trong danh sách chưa xếp.

## Đã kiểm tra

Ngày 16/11/2026 trên macOS, Odoo 18.0-20260926, bản nhân bản của `pl_moc` (81 phiếu xuất Ready, ngày dự kiến 29/10/2026): module cài không có cảnh báo hay lỗi trong log, `check_route.py` pass.

| Xe | Tải trọng | Số điểm | Tải kg | % tải | Km | Số link Maps |
| --- | --- | --- | --- | --- | --- | --- |
| XE01 | 1.500 | 16 | 1.205,5 | 80,4 | 10,3 | 2 |
| XE02 | 1.500 | 0 | 0 | 0 | 0 | – |
| XE03 | 2.500 | 35 | 2.479,7 | 99,2 | 21,5 | 4 |
| XE04 | 2.500 | 29 | 2.254,1 | 90,2 | 16,5 | 3 |

Tổng 5.939,3 kg, 48,3 km. Chưa xếp: `PL/OUT/00001` (`DB20261029-081`, 3.019,8 kg), vượt tải trọng xe lớn nhất. Link đoạn 2 của XE01 mở trên Google Maps ra đúng điểm 10 → 16 → kho theo thứ tự; Google tính đoạn đó 11,9 km theo đường thật.
