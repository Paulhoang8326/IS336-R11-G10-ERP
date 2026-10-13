# Chạy Odoo 19 bằng Docker Compose

## Yêu cầu và phạm vi

Cài Docker Desktop với Linux containers và Docker Engine đang chạy. Trong repository nhóm, kiểm tra `docker version` và `docker compose version`. Compose sử dụng official Odoo 19 Community image và PostgreSQL 15 image, hai service `odoo` và `db`. Không build từ source `odoo-19/` local, cũng không cần clone source này để chạy Docker.

Ngày 2026-10-13, Docker CLI và Compose có sẵn trên máy khởi tạo nhưng Engine chưa kết nối được. Pull, chạy service, HTTP, logs và kiểm tra mounts/volumes là **PENDING — Docker Engine unavailable** cho tới khi chạy kiểm thử runtime thực tế.

## Clone và tạo cấu hình local

~~~powershell
git clone https://github.com/Paulhoang8326/IS336-R11-G10-ERP.git
cd IS336-R11-G10-ERP
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
if (-not (Test-Path config/odoo.conf)) { Copy-Item config/odoo.example.conf config/odoo.conf }
~~~

Trong `.env`, đặt `POSTGRES_PASSWORD` mạnh và riêng cho máy. Trong `config/odoo.conf`, thay `REPLACE_WITH_LOCAL_MASTER_PASSWORD` bằng mật khẩu master mạnh. `admin_passwd` bảo vệ quản trị database Odoo, khác mật khẩu PostgreSQL. Không để placeholder khi chạy. Hai file local bị Git ignore; chỉ commit các mẫu không chứa secret. Không ghi đè file local đã tồn tại.

Nếu PostgreSQL volume đã được khởi tạo, đổi `POSTGRES_PASSWORD` trong `.env` không tự đổi mật khẩu role trong database. Giữ credential khớp với volume hiện có hoặc chủ động làm quy trình đổi mật khẩu PostgreSQL; không xóa volume khi chưa sao lưu.

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

Đối chiếu mounts: Odoo dùng `odoo_data` tại `/var/lib/odoo`, `custom_addons/` read-only tại `/mnt/extra-addons`, `config/odoo.conf` read-only tại `/etc/odoo/odoo.conf`. PostgreSQL dùng `db_data` tại `/var/lib/postgresql/data`. Kiểm tra HTTP phản hồi và logs không có lỗi DB/mount. `pg_isready` chỉ kiểm tra khả năng nhận kết nối, không xác minh mật khẩu hay database nghiệp vụ.

~~~powershell
docker compose stop
docker compose start
docker compose down
~~~

`down` bỏ container/network nhưng giữ hai named volumes. Không dùng `docker compose down -v` nếu cần giữ dữ liệu. Sao lưu/khôi phục phải bao gồm cả PostgreSQL lẫn Odoo filestore trong `odoo_data`; kiểm tra khả năng phục hồi trước khi dùng cho dữ liệu quan trọng.

## Phát triển custom addons

Tạo module trong `custom_addons/<module_name>/` với `__manifest__.py`. Mount read-only cho phép Odoo đọc module; sửa source bằng editor trên host. Sau khi đổi Python code, chạy `docker compose restart odoo`. Khi nhóm đã tự tạo database, cập nhật Apps list rồi cài/upgrade module qua giao diện Odoo. Chỉ commit custom addons đã review, không sửa Odoo core.

## Troubleshooting

- Không kết nối được Engine/named pipe: mở Docker Desktop, chờ Engine running, thử lại `docker version`. Hướng dẫn này không yêu cầu đổi WSL hay chuyển Docker storage.
- Cổng 8069 bận: kiểm tra tiến trình chiếm cổng trước; có thể đổi `ODOO_HTTP_PORT` trong `.env` sang cổng localhost khác.
- `db` unhealthy: xem `docker compose logs --tail=100 db`, kiểm tra dung lượng, quyền truy cập và volume; không xóa volume khi chưa backup.
- `odoo` không chạy hoặc HTTP không phản hồi: xem logs Odoo, trạng thái DB, file config và quyền đọc bind mounts.
- Module chưa hiện: kiểm tra đường dẫn, manifest, logs và cập nhật Apps list trong database đã tạo.
- Đổi mật khẩu sau khi DB đã khởi tạo: xem lưu ý PostgreSQL volume ở trên; không in mật khẩu vào issue/chat.

Xem [README](../README.md), [contributing](contributing.md), [odoo_version](odoo_version.md).
