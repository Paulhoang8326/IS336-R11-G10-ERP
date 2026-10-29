# Nạp dữ liệu demo vào Odoo

Cả nhóm dùng chung một bộ dữ liệu demo, có sẵn trong `seed/demo/`. Làm 3 bước dưới đây là database có đủ kho, tồn kho theo lô, sản phẩm, khách hàng và báo giá. Muốn biết bộ dữ liệu gồm những gì thì đọc [seed_data.md](seed_data.md).

Cần Odoo đang chạy bằng Docker ([docker_setup.md](docker_setup.md)) và Python 3.

## Trước buổi demo

Mọi ngày trong bộ dữ liệu (ngày đơn, ngày sản xuất, hạn dùng của lô) tính theo một ngày mốc. Bộ trong `seed/demo/` đang dùng ngày mốc 29/10/2026. Odoo xét lô hết hạn theo ngày thật, nên để lô cận date và lô hết hạn đúng như thiết kế, trước buổi demo chạy lại `gen_seed.py` với `--ngay-moc` là ngày demo, rồi nạp vào **database mới** theo 3 bước dưới đây:

~~~bash
python3 scripts/gen_seed.py --ngay-moc 2026-11-05
~~~

~~~powershell
python scripts/gen_seed.py --ngay-moc 2026-11-05
~~~

Bỏ `--ngay-moc` thì ngày mốc là hôm nay. Không nạp bộ ngày mốc mới vào database cũ: số đơn và số lô đổi theo ngày mốc, nên database sẽ có thêm 81 báo giá và các lô mới bên cạnh dữ liệu cũ.

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

Script hỏi mật khẩu (`admin`), hoặc lấy từ biến môi trường `ODOO_PASSWORD` nếu đã đặt. Chạy mất vài giây. Có một cảnh báo về `pl_min_shelf_life_pct` là bình thường, vì module đó chưa làm.

Chạy lại bao nhiêu lần cũng được: thứ đã có thì không tạo thêm. Bỏ `--orders` nếu chưa muốn tạo báo giá.

## Bước 3. Kiểm tra

| Menu | Thấy gì |
| --- | --- |
| Inventory > Configuration > Warehouses | Một kho duy nhất: Kho Phan Lâm (mã `PL`) |
| Inventory > Configuration > Locations | 6 dãy kệ `PL/Stock/Dãy A - Wilmar` đến `Dãy F`, mỗi nhãn một dãy; 240 ô `A-01-1`... trong các dãy. `PL/Stock` có *Removal Strategy* FEFO |
| Inventory > Configuration > Putaway Rules | 150 quy tắc, mỗi sản phẩm vào dãy của nhà cung cấp |
| Inventory > Reporting > Stock | 150 mã, 377 lô có hạn dùng, nằm trong ô của dãy đúng nhãn |
| Sales > Products > Products | 150 sản phẩm, mã dạng `NCC01-0005` |
| Sales > Orders > Customers | 300 khách, gắn nhãn theo nhóm (Tạp hóa, Minimart...) |
| Sales > Products > Pricelists | 5 bảng giá "Giá sỉ - ..." |
| Sales > Orders > Quotations | 81 báo giá ngày mốc, số đơn dạng `DB20261029-001` |

Thử nhanh: tạo báo giá cho một khách nhãn Minimart, thêm sản phẩm bất kỳ, giá sẽ thấp hơn giá bán 3%. Thêm cả hàng Wilmar lẫn nhãn khác rồi xác nhận: chỉ ra một phiếu xuất `PL/OUT/...` ở trạng thái Ready.

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

Ngày 29/10/2026 trên macOS, Odoo 18.0-20260926: làm đúng 3 bước trên với database mới, lần nạp đầu mất 7 giây, lần nạp thứ hai không tạo thêm bản ghi nào. Trong Odoo chỉ có 1 kho `PL`, 6 dãy, 240 ô; 377 lô có hạn dùng đều nằm trong ô của dãy đúng nhãn, không lô nào ở cấp dãy hay `PL/Stock`; 300 khách, 81 báo giá. Xác nhận cả 81 báo giá thì ra 81 phiếu xuất, đều Ready, lô được giữ theo đúng thứ tự FEFO và không giữ lô hết hạn. Đơn mua 1 mã Wilmar khi nhận hàng được gợi ý vào ô của mã đó trong dãy Wilmar. Lệnh PowerShell chưa chạy thử trên Windows.
