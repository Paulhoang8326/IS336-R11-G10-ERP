# Thiết lập môi trường local

Repository nhóm: https://github.com/Paulhoang8326/IS336-R11-G10-ERP. Thành viên chỉ cần clone repository này và dùng Docker Desktop; không cần clone source Odoo. Hướng dẫn đầy đủ, lệnh Compose, volumes và troubleshooting: [docker_setup.md](docker_setup.md).

~~~powershell
git clone https://github.com/Paulhoang8326/IS336-R11-G10-ERP.git
cd IS336-R11-G10-ERP
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
if (-not (Test-Path config/odoo.conf)) { Copy-Item config/odoo.example.conf config/odoo.conf }
~~~

Đặt mật khẩu PostgreSQL trong `.env` và master password Odoo trong `config/odoo.conf`; hai file local bị Git ignore. Sau khi Engine chạy:

~~~powershell
docker compose config --quiet
docker compose pull
docker compose up -d
docker compose ps
~~~

Truy cập http://localhost:8069/ khi Odoo sẵn sàng. HTTP chỉ bind localhost; PostgreSQL và dữ liệu Odoo ở named volumes. Không xóa volumes khi cần giữ dữ liệu. Chưa tạo database nghiệp vụ, tài khoản ứng dụng hoặc module.

Máy khởi tạo vẫn có source upstream `../odoo-19` riêng ngoài repository nhóm; Compose không build từ đó. [odoo_version.md](odoo_version.md) phân biệt source local với image runtime. Engine trên máy khởi tạo chưa khả dụng tại lần kiểm tra 2026-10-13; kiểm thử runtime đang pending.
