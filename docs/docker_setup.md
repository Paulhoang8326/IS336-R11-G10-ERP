# Chạy Odoo 18 bằng Docker Compose

## Yêu cầu và phạm vi

Cài Docker Desktop với Linux containers và Docker Engine đang chạy. Trong repository nhóm, kiểm tra `docker version` và `docker compose version`. Compose sử dụng official Odoo 18 Community image và PostgreSQL 15 image, hai service `odoo` và `db`. Không cần source Odoo local hoặc build image riêng để chạy môi trường này.

Môi trường đã chạy thử đầy đủ ngày 2026-10-16; kết quả ở cuối tài liệu. Các máy khác cần tự kiểm tra lại.

## Clone và tạo cấu hình local

~~~powershell
git clone --recurse-submodules https://github.com/Paulhoang8326/IS336-R11-G10-ERP.git
cd IS336-R11-G10-ERP
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
if (-not (Test-Path config/odoo.conf)) { Copy-Item config/odoo.example.conf config/odoo.conf }
~~~

Đã clone mà thiếu submodule thì chạy `git submodule update --init`; nếu không, các thư mục trong `oca/` rỗng. Máy đã clone từ hồi repository dùng Odoo 19 thì làm theo mục cập nhật trong [setup.md](setup.md#cập-nhật-file-local-đã-tạo-từ-trước).

Trong `.env`, đặt `POSTGRES_PASSWORD` mạnh và riêng cho máy. Nếu `.env` và `config/odoo.conf` đã có từ trước, chép lại dòng `ODOO_IMAGE` từ `.env.example` và dòng `addons_path` từ `config/odoo.example.conf`; file local bị ignore sẽ không tự đổi khi Git pull. Trong `config/odoo.conf`, thay `REPLACE_WITH_LOCAL_MASTER_PASSWORD` bằng mật khẩu master mạnh. `admin_passwd` bảo vệ quản trị database Odoo, khác mật khẩu PostgreSQL. Không để placeholder khi chạy. Hai file local bị Git ignore; chỉ commit các mẫu không chứa secret. Không ghi đè file local đã tồn tại.

Nếu PostgreSQL volume đã được khởi tạo, đổi `POSTGRES_PASSWORD` trong `.env` không tự đổi mật khẩu role trong database. Giữ credential khớp với volume hiện có hoặc chủ động làm quy trình đổi mật khẩu PostgreSQL; không xóa volume khi chưa sao lưu.

**Database tạo bằng Odoo 19 không mở được bằng Odoo 18, vì Odoo không hạ cấp database.** Ai đã tạo database thử bằng 19 thì xóa đi; nếu có dữ liệu cần giữ thì báo nhóm trước.

## Validate và chạy

~~~powershell
docker compose config --quiet
docker compose pull
docker compose up -d
docker compose ps
docker compose logs --tail=100 db odoo
~~~

`config --quiet` xác thực Compose mà không in secrets đã nội suy. Khi pull, đối chiếu lại tag/digest trong `.env` và image thực nhận; nếu digest hoặc kiến trúc không sẵn có, dừng kiểm tra thay vì tự đổi image. `db` có healthcheck; `odoo` phụ thuộc trạng thái healthy. Mở http://localhost:8069/ khi Odoo running và HTTP sẵn sàng. Cổng chỉ publish trên localhost.

Lần đầu mở Odoo có thể hiển thị màn hình tạo database. Thành viên chủ động nhập master password local khi cần; task setup này không tạo database nghiệp vụ, tài khoản Odoo hoặc cài module.

## Kiểm tra runtime và volumes

~~~powershell
docker compose ps
docker compose exec db pg_isready -U odoo -d postgres
curl.exe -I http://localhost:8069/
docker compose logs --tail=100 db odoo
docker compose config --volumes
docker volume ls
docker inspect (docker compose ps -q odoo)
docker inspect (docker compose ps -q db)
~~~

Đối chiếu mounts: Odoo dùng `odoo_data` tại `/var/lib/odoo`, `custom_addons/` read-only tại `/mnt/extra-addons`, `oca/` read-only tại `/mnt/oca`, `config/odoo.conf` read-only tại `/etc/odoo/odoo.conf`. PostgreSQL dùng `db_data` tại `/var/lib/postgresql/data`. Kiểm tra HTTP phản hồi và logs không có lỗi DB/mount. `pg_isready` chỉ kiểm tra khả năng nhận kết nối, không xác minh mật khẩu hay database nghiệp vụ.

~~~powershell
docker compose stop
docker compose start
docker compose down
~~~

`down` bỏ container/network nhưng giữ hai named volumes. Không dùng `docker compose down -v` nếu cần giữ dữ liệu. Sao lưu/khôi phục phải bao gồm cả PostgreSQL lẫn Odoo filestore trong `odoo_data`: dùng `scripts/backup.sh <db>` và `scripts/restore.sh <thư mục backup> <db đích>` (Windows: bản `.ps1`). Kiểm tra khả năng phục hồi trước khi dùng cho dữ liệu quan trọng.

## Phát triển custom addons

Tạo module trong `custom_addons/<module_name>/` với `__manifest__.py`. Mount read-only cho phép Odoo đọc module; sửa source bằng editor trên host. Sau khi đổi Python code, chạy `docker compose restart odoo`. Khi nhóm đã tự tạo database, cập nhật Apps list rồi cài/upgrade module qua giao diện Odoo. Chỉ commit custom addons đã review, không sửa Odoo core hay code trong `oca/`.

## Troubleshooting

- Không kết nối được Engine/named pipe: mở Docker Desktop, chờ Engine running, thử lại `docker version`. Hướng dẫn này không yêu cầu đổi WSL hay chuyển Docker storage.
- Cổng 8069 bận: kiểm tra tiến trình chiếm cổng trước; có thể đổi `ODOO_HTTP_PORT` trong `.env` sang cổng localhost khác.
- `db` unhealthy: xem `docker compose logs --tail=100 db`, kiểm tra dung lượng, quyền truy cập và volume; không xóa volume khi chưa backup.
- `odoo` không chạy hoặc HTTP không phản hồi: xem logs Odoo, trạng thái DB, file config và quyền đọc bind mounts.
- Module chưa hiện: kiểm tra đường dẫn, manifest, logs và cập nhật Apps list trong database đã tạo. Với module OCA, kiểm tra thư mục `oca/<repo>` không rỗng và `addons_path` trong `config/odoo.conf` khớp file mẫu.
- Đổi mật khẩu sau khi DB đã khởi tạo: xem lưu ý PostgreSQL volume ở trên; không in mật khẩu vào issue/chat.

Xem [README](../README.md), [contributing](contributing.md), [odoo_version](odoo_version.md).

## Kiểm chứng trên máy khởi tạo (2026-10-16)

| Mục | Kết quả |
| --- | --- |
| `docker compose config --quiet`, `pull`, `up -d` | PASS |
| PostgreSQL healthy, Odoo running, HTTP localhost | PASS |
| `odoo --version` | PASS: `Odoo Server 18.0-20260926` |
| Cài `auditlog`, `account_financial_report`, `stock_barcodes`, `pl_base` | PASS |
| Backup và restore bằng `scripts/*.sh` | PASS |
| `scripts/*.ps1` trên Windows | Chưa chạy |

Chi tiết từng bước trong [odoo_version.md](odoo_version.md#kiểm-thử).
