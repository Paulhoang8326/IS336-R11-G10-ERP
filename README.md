# IS336-R11-G10-ERP

Đồ án **IS336 – Hoạch định nguồn lực doanh nghiệp**, lớp **IS336.R11**, **nhóm 10**, UIT. Môi trường phát triển chạy **Odoo 18 Community official image** và **PostgreSQL 15** bằng Docker Compose. Repository: https://github.com/Paulhoang8326/IS336-R11-G10-ERP.

## Bắt đầu trên Windows

Cài Docker Desktop và bật Linux Docker Engine. Chỉ cần clone repository nhóm; không cần clone source Odoo riêng để chạy Docker.

~~~powershell
git clone https://github.com/Paulhoang8326/IS336-R11-G10-ERP.git
cd IS336-R11-G10-ERP
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
if (-not (Test-Path config/odoo.conf)) { Copy-Item config/odoo.example.conf config/odoo.conf }
~~~

Đặt `POSTGRES_PASSWORD` mạnh trong `.env` và thay `REPLACE_WITH_LOCAL_MASTER_PASSWORD` bằng mật khẩu master mạnh trong `config/odoo.conf`. Hai file local bị Git ignore. Không commit hoặc chia sẻ mật khẩu. Trên máy khởi tạo, hai file đã được tạo với mật khẩu ngẫu nhiên riêng.

~~~powershell
docker compose config --quiet
docker compose pull
docker compose up -d
docker compose ps
~~~

Khi `db` healthy và `odoo` running, truy cập http://localhost:8069/. Để xem lỗi: `docker compose logs --tail=100 db odoo`. Việc tạo database Odoo, tài khoản ứng dụng và cài module chỉ thực hiện sau này khi nhóm cần.

## Cấu trúc

~~~text
IS336-R11-G10-ERP/
├── docker-compose.yml
├── .env.example
├── .env                         # local, ignored
├── config/
│   ├── odoo.example.conf
│   └── odoo.conf                # local, ignored
├── custom_addons/               # module nhóm, bind mount read-only
├── docs/
│   ├── docker_setup.md
│   ├── setup.md
│   ├── contributing.md
│   └── odoo_version.md
└── odoo-18/                     # source local nếu có, ignored; không dùng để build
~~~

Compose chỉ bind HTTP vào `127.0.0.1:8069` và dùng hai named volumes cho PostgreSQL và dữ liệu Odoo. `docker compose down` giữ volumes; không dùng `down -v` khi cần giữ dữ liệu. Phát triển module trong `custom_addons/`, không sửa Odoo core. Xem [hướng dẫn Docker](docs/docker_setup.md), [quy tắc cộng tác](docs/contributing.md) và [phiên bản image/source](docs/odoo_version.md).
