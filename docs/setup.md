# Thiết lập môi trường local

Repository nhóm: https://github.com/Paulhoang8326/IS336-R11-G10-ERP. Thành viên chỉ cần clone repository này kèm submodule OCA và dùng Docker Desktop; không cần clone source Odoo. Hướng dẫn đầy đủ, lệnh Compose, volumes và troubleshooting: [docker_setup.md](docker_setup.md).

~~~powershell
git clone --recurse-submodules https://github.com/Paulhoang8326/IS336-R11-G10-ERP.git
cd IS336-R11-G10-ERP
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
if (-not (Test-Path config/odoo.conf)) { Copy-Item config/odoo.example.conf config/odoo.conf }
~~~

Ai đã clone repository trước khi có submodule OCA, hoặc clone mà quên `--recurse-submodules`, thì tải submodule bằng:

~~~powershell
git submodule update --init
~~~

Thiếu bước này thì các thư mục trong `oca/` rỗng và Odoo không thấy module OCA.

Đặt mật khẩu PostgreSQL trong `.env` và master password Odoo trong `config/odoo.conf`; hai file local bị Git ignore. Sau khi Engine chạy:

~~~powershell
docker compose config --quiet
docker compose pull
docker compose up -d
docker compose ps
~~~

Truy cập http://localhost:8069/ khi Odoo sẵn sàng. HTTP chỉ bind localhost; PostgreSQL và dữ liệu Odoo ở named volumes. Không xóa volumes khi cần giữ dữ liệu.

## Cập nhật file local đã tạo từ trước

Git không cập nhật `.env` và `config/odoo.conf`. Ai đã tạo hai file này trước khi repository chuyển sang Odoo 19 và thêm OCA thì sửa lại, giữ nguyên mật khẩu:

- `.env`: chép hai dòng `ODOO_IMAGE` và `POSTGRES_IMAGE` từ `.env.example`.
- `config/odoo.conf`: chép dòng `addons_path` từ `config/odoo.example.conf`.

Sau đó chạy `docker compose pull` và `docker compose up -d`. Odoo 19 không mở được database tạo bằng Odoo 18; nếu máy đã có database Odoo 18 cần giữ, báo nhóm trước, không tự xóa volume.

Compose dùng image chính thức, không build từ source Odoo local. Môi trường đã chạy thử thành công ngày 2026-10-15; chi tiết trong [odoo_version.md](odoo_version.md).
