# Chạy Odoo 19 bằng Docker Compose

## Yêu cầu và phạm vi

Cài Docker Desktop với Linux containers và Docker Engine đang chạy. Trong repository nhóm, kiểm tra `docker version` và `docker compose version`. Compose sử dụng official Odoo 19 Community image và PostgreSQL 15 image, hai service `odoo` và `db`. Không build từ source Odoo 18 tại `odoo-18/` local, cũng không cần clone source riêng để chạy Docker.

Ngày 2026-10-13, Docker Engine trên máy khởi tạo đã hoạt động khi chuyển sang Odoo 19. Kết quả kiểm thử runtime cho image mới được ghi ở cuối tài liệu; các máy khác cần tự kiểm tra lại.

## Clone và tạo cấu hình local

~~~powershell
git clone https://github.com/Paulhoang8326/IS336-R11-G10-ERP.git
cd IS336-R11-G10-ERP
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
if (-not (Test-Path config/odoo.conf)) { Copy-Item config/odoo.example.conf config/odoo.conf }
~~~

Trong `.env`, đặt `POSTGRES_PASSWORD` mạnh và riêng cho máy. Nếu file này đã có từ setup Odoo 18, cập nhật riêng `ODOO_IMAGE` theo `.env.example`; file local bị ignore sẽ không tự đổi khi Git pull. Trong `config/odoo.conf`, thay `REPLACE_WITH_LOCAL_MASTER_PASSWORD` bằng mật khẩu master mạnh. `admin_passwd` bảo vệ quản trị database Odoo, khác mật khẩu PostgreSQL. Không để placeholder khi chạy. Hai file local bị Git ignore; chỉ commit các mẫu không chứa secret. Không ghi đè file local đã tồn tại.

Nếu PostgreSQL volume đã được khởi tạo, đổi `POSTGRES_PASSWORD` trong `.env` không tự đổi mật khẩu role trong database. Giữ credential khớp với volume hiện có hoặc chủ động làm quy trình đổi mật khẩu PostgreSQL; không xóa volume khi chưa sao lưu.

**Đổi image Odoo 18 sang 19 không nâng cấp database Odoo 18.** Nếu đã có dữ liệu Odoo 18, sao lưu cả database và filestore, rồi làm quy trình migration tương thích Odoo 19 trước khi cho image mới sử dụng volumes đó. Trên máy khởi tạo, trước khi đổi image không có container hoặc named volume của Compose project này. Xem [hướng dẫn nâng cấp Odoo](https://www.odoo.com/documentation/19.0/administration/upgrade.html).

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

## Kiểm chứng trên máy khởi tạo (2026-10-13)

| Mục | Kết quả |
| --- | --- |
| Docker Engine và `docker compose config --quiet` với Odoo 19 | PASS |
| Official `odoo:19.0-20260926` và OCI index digest trên registry | PASS |
| Pull Odoo 19/PostgreSQL image | PENDING — lần pull đã bắt đầu nhưng chưa tải xong; đã dừng để hoàn tất thay đổi Git |
| PostgreSQL healthy, Odoo running, HTTP localhost, logs và mounts/volumes runtime | PENDING — chưa chạy container |

Sau lần pull chưa hoàn tất, không có image Odoo 19 hoàn chỉnh, container hoặc named volume của Compose project trên máy khởi tạo. Chạy lại `docker compose pull` khi có đủ thời gian/mạng, rồi tiếp tục các lệnh kiểm tra ở trên. Không báo PASS cho runtime khi chưa chạy.
