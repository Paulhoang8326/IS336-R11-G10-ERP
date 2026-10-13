# Thiết lập môi trường local

Repository nhóm: https://github.com/Paulhoang8326/IS336-R11-G10-ERP. Thành viên chỉ cần clone repository này và dùng Docker Desktop để chạy Odoo 19; không cần clone source Odoo. Hướng dẫn đầy đủ, lệnh Compose, volumes và troubleshooting: [docker_setup.md](docker_setup.md).

~~~powershell
git clone https://github.com/Paulhoang8326/IS336-R11-G10-ERP.git
cd IS336-R11-G10-ERP
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
if (-not (Test-Path config/odoo.conf)) { Copy-Item config/odoo.example.conf config/odoo.conf }
~~~

Đặt mật khẩu PostgreSQL trong `.env` và master password Odoo trong `config/odoo.conf`; hai file local bị Git ignore. Nếu đã có `.env` từ Odoo 18, cập nhật riêng `ODOO_IMAGE` theo `.env.example` và giữ nguyên secret đang sử dụng. Sau khi Engine chạy:

~~~powershell
docker compose config --quiet
docker compose pull
docker compose up -d
docker compose ps
~~~

Truy cập http://localhost:8069/ khi Odoo sẵn sàng. HTTP chỉ bind localhost; PostgreSQL và dữ liệu Odoo ở named volumes. Không xóa volumes khi cần giữ dữ liệu. Chưa tạo database nghiệp vụ, tài khoản ứng dụng hoặc module.

Các bản source Odoo 18 local trên máy khởi tạo đã được dọn bỏ. Setup hiện tại chỉ dùng official Odoo 19 image; không cần phục hồi hoặc clone source Odoo riêng. [odoo_version.md](odoo_version.md) ghi phiên bản image runtime và giữ thông tin audit source cũ để tham khảo lịch sử.
