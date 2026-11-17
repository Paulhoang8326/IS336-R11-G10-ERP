# Nạp dữ liệu demo vào Odoo

Cả nhóm dùng chung một bộ dữ liệu demo, có sẵn trong `seed/demo/`. Làm 3 bước đầu dưới đây là database có đủ kho, tồn kho theo lô, sản phẩm, khách hàng và báo giá. Muốn biết bộ dữ liệu gồm những gì thì đọc [seed_data.md](seed_data.md).

Cần Odoo đang chạy bằng Docker ([docker_setup.md](docker_setup.md)) và Python 3.

## Trước buổi demo

Mọi ngày trong bộ dữ liệu (ngày đơn, ngày sản xuất, hạn dùng của lô) tính theo một ngày mốc. Bộ trong `seed/demo/` đang dùng ngày mốc 29/10/2026. Odoo xét lô hết hạn theo ngày thật, nên để lô cận date và lô hết hạn đúng như thiết kế, trước buổi demo chạy lại `gen_seed.py` với `--ngay-moc` là ngày demo, rồi nạp vào **database mới** theo 3 bước dưới đây:

~~~bash
python3 scripts/gen_seed.py --ngay-moc 2026-11-05
~~~

~~~powershell
python scripts/gen_seed.py --ngay-moc 2026-11-05
~~~

Bỏ `--ngay-moc` thì ngày mốc là hôm nay. Không nạp bộ ngày mốc mới vào database cũ: số đơn và số lô đổi theo ngày mốc, nên database sẽ có thêm 81 báo giá và các lô mới bên cạnh dữ liệu cũ. Với database chính `pl_moc`, làm theo mục [Dựng lại database chính](#dựng-lại-database-chính): script làm hết 4 bước dưới đây rồi đưa database mới lên thay.

## Bước 1. Tạo database

Công ty phải được đặt ở Việt Nam, tiền VND **trước khi** cài Sales và Purchase, vì Odoo chọn bộ thuế theo nước của công ty lúc cài kế toán. Làm sai thứ tự thì sản phẩm không có thuế 5%, 8%, 10%.

~~~bash
docker compose run --rm odoo odoo -d demo -i base --without-demo=all --stop-after-init
docker compose run --rm -T odoo odoo shell -d demo --no-http <<'EOF'
vnd = env.ref('base.VND')
vnd.active = True
env.company.write({'country_id': env.ref('base.vn').id, 'currency_id': vnd.id})
env.cr.commit()
EOF
docker compose run --rm odoo odoo -d demo -i stock,purchase_stock,sale_stock,product_expiry,pl_base --without-demo=all --stop-after-init
~~~

~~~powershell
docker compose run --rm odoo odoo -d demo -i base --without-demo=all --stop-after-init
@'
vnd = env.ref('base.VND')
vnd.active = True
env.company.write({'country_id': env.ref('base.vn').id, 'currency_id': vnd.id})
env.cr.commit()
'@ | docker compose run --rm -T odoo odoo shell -d demo --no-http
docker compose run --rm odoo odoo -d demo -i stock,purchase_stock,sale_stock,product_expiry,pl_base --without-demo=all --stop-after-init
~~~

`demo` là tên database, đổi tùy ý. Đăng nhập bằng `admin` / `admin`.

## Bước 2. Nạp dữ liệu

~~~bash
python3 scripts/seed_import.py --db demo --orders
~~~

~~~powershell
python scripts/seed_import.py --db demo --orders
~~~

Script hỏi mật khẩu (`admin`), hoặc lấy từ biến môi trường `ODOO_PASSWORD` nếu đã đặt. Chạy mất vài giây. Hạn dùng tối thiểu của khách chỉ ghi được khi đã cài module `pl_fefo_pick`; chưa cài thì script cảnh báo một dòng về `pl_min_shelf_life_pct` và bỏ qua trường này. Cài module rồi chạy lại script theo [fefo_pick.md](fefo_pick.md#cài).

Chạy lại bao nhiêu lần cũng được: thứ đã có thì không tạo thêm. Bỏ `--orders` nếu chưa muốn tạo báo giá.

Script đặt hóa đơn lập theo số lượng đã giao: bật *Invoice what is delivered* trong Sales Settings và ghi *Invoicing Policy* = *Delivered quantities* cho từng sản phẩm của seed (đổi setting không sửa sản phẩm đã có). Database nạp trước khi có phần này thì chạy lại script một lần: dòng *Cài đặt* cập nhật 1, dòng *Sản phẩm* cập nhật 150; lần sau không đổi gì nữa. Xem [seed_data.md](seed_data.md#dữ-liệu-vào-odoo-ở-đâu) và [o2c_check.md](o2c_check.md).

## Bước 3. Kiểm tra

| Menu | Thấy gì |
| --- | --- |
| Inventory > Configuration > Warehouses | Một kho duy nhất: Kho Phan Lâm (mã `PL`) |
| Inventory > Configuration > Locations | 6 dãy kệ `PL/Stock/Dãy A - Wilmar` đến `Dãy F`, mỗi nhãn một dãy; 240 ô `A-01-1`... trong các dãy. `PL/Stock` có *Removal Strategy* FEFO |
| Inventory > Configuration > Putaway Rules | 150 quy tắc, mỗi sản phẩm vào dãy của nhà cung cấp |
| Inventory > Reporting > Stock | 150 mã, 377 lô có hạn dùng, nằm trong ô của dãy đúng nhãn |
| Sales > Products > Products | 150 sản phẩm, mã dạng `NCC01-0005`, tab *Sales* có *Invoicing Policy* = *Delivered quantities* |
| Sales > Configuration > Settings > Invoicing | *Invoicing Policy* chọn *Invoice what is delivered* |
| Sales > Orders > Customers | 300 khách, gắn nhãn theo nhóm (Tạp hóa, Minimart...) |
| Sales > Products > Pricelists | 5 bảng giá "Giá sỉ - ..." |
| Sales > Orders > Quotations | 81 báo giá ngày mốc, số đơn dạng `DB20261029-001` |

Thử nhanh: tạo báo giá cho một khách nhãn Minimart, thêm sản phẩm bất kỳ, giá sẽ thấp hơn giá bán 3%. Thêm cả hàng Wilmar lẫn nhãn khác rồi xác nhận: chỉ ra một phiếu xuất `PL/OUT/...` ở trạng thái Ready.

## Bước 4. Cấu hình kho

Chạy sau khi nạp dữ liệu, chạy lại bao nhiêu lần cũng được:

~~~bash
python3 scripts/setup_warehouse.py --db demo
~~~

~~~powershell
python scripts/setup_warehouse.py --db demo
~~~

Script bật Storage Locations, Multi-Step Routes, Lots & Serial Numbers, Expiration Dates, Packages; giữ nguyên số bước nhập, xuất của kho. Cả 22 nhóm hàng chuyển sang xuất FEFO, giá vốn FIFO, định giá Automated. Tài khoản kho và tài khoản kiểm kê xem ở [scripts/seminar3/README.md](../scripts/seminar3/README.md#tài-khoản-kế-toán-đã-dùng). Tài khoản chạy script được bật *Show Full Accounting Features* để thấy menu Invoicing > Accounting > Journal Entries.

| Menu | Thấy gì |
| --- | --- |
| Inventory > Configuration > Putaway Rules | Thêm 22 quy tắc theo nhóm hàng cho sản phẩm thêm sau. 150 quy tắc theo sản phẩm vẫn được xét trước. Nhóm Dầu ăn vào ô `A-01-1`, nhóm khác vào dãy của nhà cung cấp nhiều mã nhất trong nhóm |
| Inventory > Configuration > Products > Product Categories | Từng nhóm có Force Removal Strategy FEFO, Costing Method FIFO, Inventory Valuation Automated |

Lần đầu chạy, Odoo xuất rồi nhập lại tồn hiện có để đổi định giá nên sinh mỗi sản phẩm một bút toán tồn đầu kỳ (bộ 150 mã: Nợ 1560 / Có 1510, tổng 1.833.616.300 đ, tổng giá trị tồn không đổi).

## Dựng lại database chính

Database chính `pl_moc` phải khớp đúng bộ seed đang có trong `seed/demo/`, vì `check_fefo.py`, `check_route.py`, `check_o2c.py` nhân bản `pl_moc` rồi kiểm theo số lô, số đơn của seed. Cần dựng lại khi:

- sinh lại seed, nhất là đổi ngày mốc trước buổi demo ([Trước buổi demo](#trước-buổi-demo));
- `pl_moc` lệch seed: lô không khớp `ton_kho.csv`, thiếu module của nhóm, có dữ liệu thử còn sót.

Không chạy `seed_import.py` lên `pl_moc` cũ cho khớp: lô đã có thì script không nhập lại tồn, lô mới thì cộng thêm, nên tồn bị chồng.

`scripts/rebuild_main_db.py` dựng database mới `pl_moc_new` từ đầu theo Bước 1–4 ở trên (cài thêm `sale_management`, `pl_fefo_pick`, `pl_delivery_route`, `stock_barcodes`, `pl_barcode_camera`, `pl_product_barcode`; gán *Barcode option group* cho Receipts, Delivery Orders, Internal Transfers như [barcode.md](barcode.md#cấu-hình-trong-database)), kiểm tra, rà soát `pl_moc` cũ, rồi mới đưa lên thay:

~~~bash
export ODOO_PASSWORD='<mật khẩu admin Odoo>'
python3 scripts/gen_seed.py --ngay-moc 2026-12-10     # chỉ khi cần đổi ngày mốc
python3 scripts/rebuild_main_db.py --skip-swap        # dựng và kiểm tra pl_moc_new, chưa thay
python3 scripts/rebuild_main_db.py                    # dựng lại, rà soát, hỏi rồi mới thay pl_moc
~~~

~~~powershell
$env:ODOO_PASSWORD = '<mật khẩu admin Odoo>'
python scripts/gen_seed.py --ngay-moc 2026-12-10
python scripts/rebuild_main_db.py --skip-swap
python scripts/rebuild_main_db.py
~~~

Mật khẩu như [scripts/seminar3/README.md](../scripts/seminar3/README.md#tạo-lại): admin lấy từ `ODOO_PASSWORD`, master từ `ODOO_MASTER_PASSWORD` hoặc `config/odoo.conf`. Mỗi lần chạy mất khoảng 40 giây.

| Bước | Script làm gì | Dừng khi |
| --- | --- | --- |
| 1. Dựng | Tạo `pl_moc_new`: base, công ty ở Việt Nam và VND, rồi cài các module | Module cài không được |
| 2. Seed | `seed_import.py --orders` | Có cảnh báo |
| 3. Kho | `setup_warehouse.py` | Script lỗi |
| 4. Barcode | Gán *Picking IN/OUT/Internal options* cho 3 loại thao tác, chạy lại không đổi gì thêm | Thiếu `stock_barcodes` |
| 5. Kiểm tra | 1 kho `PL`, 6 dãy, 240 ô; 150 sản phẩm *Invoicing Policy* = *Delivered quantities*; lô và tồn từng lô đúng ô, đúng số lượng trong `ton_kho.csv`; 300 khách đều có hạn dùng tối thiểu; 81 báo giá chưa xác nhận; 4 xe; Sales Settings *Invoice what is delivered* | Sai điều nào |
| 6. Rà soát | Đọc `pl_moc` cũ (không ghi gì), in những gì không đến từ seed: module, user, đơn bán/mua, phiếu kho, hóa đơn, bút toán, kho, loại thao tác, vị trí, route, quy tắc, và Settings khác giữa hai database | Danh sách khác rỗng: in ra rồi hỏi |
| 7. Thay | Backup `pl_moc` bằng `scripts/backup.sh` (Windows: `backup.ps1`) vào `backups/`, đổi tên `pl_moc` thành `pl_moc_old_<yyyymmdd_hhmm>`, đổi tên `pl_moc_new` thành `pl_moc` | Hỏi xác nhận, trả lời khác `y` |

Sai ở bước 1–6 thì `pl_moc` không bị đụng. Đổi tên làm qua database manager của Odoo nên filestore đổi theo. Script không xóa database chính nào: `pl_moc` cũ còn nguyên dưới tên `pl_moc_old_*`. Chỉ `pl_moc_new` do chính script dựng (có dấu `pl_rebuild.build_db` trong *System Parameters*, xóa đi lúc đổi tên) mới bị xóa để dựng lại khi chạy lần sau; trùng tên với database khác thì script dừng.

Tham số: `--target` (mặc định `pl_moc`), `--build-name` (mặc định `<target>_new`), `--skip-swap` (dừng sau bước 6), `--yes` (không hỏi), `--keep-old` (mặc định; `--no-keep-old` bị từ chối vì script không xóa database).

**Khôi phục `pl_moc` cũ.** Cách nhanh: ở http://localhost:8069/web/database/manager đổi tên `pl_moc` (bản mới) thành tên khác, rồi đổi `pl_moc_old_<yyyymmdd_hhmm>` về `pl_moc`. Database cũ đã bị xóa thì khôi phục từ backup (hỏi trước khi ghi đè nếu `pl_moc` đang có):

~~~bash
scripts/restore.sh backups/pl_moc_<yyyymmdd_hhmmss> pl_moc
~~~

~~~powershell
.\scripts\restore.ps1 backups\pl_moc_<yyyymmdd_hhmmss> pl_moc
~~~

**Database seminar.** `phanlam_seminar3` và `phanlam_seminar3_clean` được nhân bản từ `pl_moc` cũ, nên không đổi khi dựng lại `pl_moc`. Muốn chúng theo seed mới thì chạy lại `scripts/seminar3/make_seminar_db.py --force` (xóa và tạo lại `phanlam_seminar3`), xem [scripts/seminar3/README.md](../scripts/seminar3/README.md#tạo-lại).

## Database tạo từ trước

Database đã cài Sales, Purchase hoặc Invoicing khi công ty còn để nước khác thì cài `l10n_vn` cũng không đổi được bộ thuế. Nên tạo database mới theo Bước 1.

Nếu buộc phải giữ database cũ, chạy lệnh sau **trước khi** nạp dữ liệu. Lệnh chỉ chạy được khi database chưa có hóa đơn hay bút toán nào.

~~~bash
docker compose run --rm -T odoo odoo shell -d demo --no-http <<'EOF'
vnd = env.ref('base.VND')
vnd.active = True
env.company.write({'country_id': env.ref('base.vn').id, 'currency_id': vnd.id})
env['account.chart.template'].try_loading('vn', env.company)
env.cr.commit()
EOF
~~~

~~~powershell
@'
vnd = env.ref('base.VND')
vnd.active = True
env.company.write({'country_id': env.ref('base.vn').id, 'currency_id': vnd.id})
env['account.chart.template'].try_loading('vn', env.company)
env.cr.commit()
'@ | docker compose run --rm -T odoo odoo shell -d demo --no-http
~~~

## Lỗi thường gặp

| Script báo | Cách xử lý |
| --- | --- |
| `Đăng nhập thất bại` | Kiểm tra `--db` và mật khẩu. Đăng nhập bằng tài khoản khác `admin` thì thêm `--user <tên đăng nhập>` |
| `Không kết nối được Odoo` | Odoo chưa chạy: `docker compose up -d` |
| `CẢNH BÁO: không có thuế bán ...` | Database không dùng bộ thuế Việt Nam. Tạo database mới theo Bước 1 rồi nạp lại |
| `Thiếu seed/demo/....csv` | Chưa có bộ dữ liệu: chạy `python scripts/gen_seed.py` |

## Quy ước dữ liệu

Không ghi chú kiểu (giả lập), (demo), (test) vào giá trị dữ liệu. Phần nào là giả lập hay ước lượng thì ghi trong [seed_data.md](seed_data.md) hoặc cột `uoc_luong`.

## Đã kiểm tra

Ngày 29/10/2026 trên macOS, Odoo 18.0-20260926: làm đúng 3 bước trên với database mới, lần nạp đầu mất 7 giây, lần nạp thứ hai không tạo thêm bản ghi nào. Trong Odoo chỉ có 1 kho `PL`, 6 dãy, 240 ô; 377 lô có hạn dùng đều nằm trong ô của dãy đúng nhãn, không lô nào ở cấp dãy hay `PL/Stock`; 300 khách, 81 báo giá. Xác nhận cả 81 báo giá thì ra 81 phiếu xuất, đều Ready, lô được giữ theo đúng thứ tự FEFO và không giữ lô hết hạn. Ngày 17/11/2026 nạp lại bộ đã đổi mức hạn dùng tối thiểu (ngày mốc vẫn 29/10/2026) vào database mới `pl_seed_fefo`: cùng số bản ghi, 1 cảnh báo `pl_min_shelf_life_pct` khi chưa cài `pl_fefo_pick`, 0 cảnh báo sau khi cài. Đơn mua 1 mã Wilmar khi nhận hàng được gợi ý vào ô của mã đó trong dãy Wilmar. Lệnh PowerShell chưa chạy thử trên Windows.
