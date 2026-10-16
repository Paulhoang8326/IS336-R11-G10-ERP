# IS336-R11-G10-ERP

Đồ án **IS336 – Hoạch định nguồn lực doanh nghiệp**, lớp **IS336.R11**, **nhóm 10**, UIT. Môi trường phát triển chạy **Odoo 18 Community official image** và **PostgreSQL 15** bằng Docker Compose. Repository: https://github.com/Paulhoang8326/IS336-R11-G10-ERP.

## Bắt đầu trên Windows

Cài Docker Desktop và bật Linux Docker Engine. Chỉ cần clone repository nhóm; không cần clone source Odoo riêng để chạy Docker.

~~~powershell
git clone --recurse-submodules https://github.com/Paulhoang8326/IS336-R11-G10-ERP.git
cd IS336-R11-G10-ERP
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
if (-not (Test-Path config/odoo.conf)) { Copy-Item config/odoo.example.conf config/odoo.conf }
~~~

Đặt `POSTGRES_PASSWORD` mạnh trong `.env` và thay `REPLACE_WITH_LOCAL_MASTER_PASSWORD` bằng mật khẩu master mạnh trong `config/odoo.conf`. Hai file local bị Git ignore và không tự cập nhật khi pull; nếu đã tạo từ trước, xem [setup.md](docs/setup.md) để sửa hai dòng image và dòng `addons_path`. Không commit hoặc chia sẻ mật khẩu. Trên máy khởi tạo, hai file đã được tạo với mật khẩu ngẫu nhiên riêng.

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
├── .gitmodules                  # khai báo 7 submodule OCA
├── config/
│   ├── odoo.example.conf
│   └── odoo.conf                # local, ignored
├── custom_addons/               # module nhóm, bind mount read-only
│   └── pl_base/                 # module nền Phan Lam Base
├── oca/                         # submodule OCA nhánh 18.0, bind mount read-only
│   ├── account-financial-reporting/
│   ├── reporting-engine/
│   ├── server-tools/
│   ├── server-ux/
│   ├── stock-logistics-barcode/
│   ├── stock-logistics-workflow/
│   └── web/
├── scripts/                     # backup/restore database kèm filestore
│   ├── backup.sh
│   ├── backup.ps1
│   ├── restore.sh
│   └── restore.ps1
├── backups/                     # tạo khi chạy backup, ignored
├── docs/
│   ├── docker_setup.md
│   ├── setup.md
│   ├── contributing.md
│   └── odoo_version.md
└── README.md
~~~

Compose chỉ bind HTTP vào `127.0.0.1:8069` và dùng hai named volumes cho PostgreSQL và dữ liệu Odoo. `docker compose down` giữ volumes; không dùng `down -v` khi cần giữ dữ liệu. **Database tạo bằng Odoo 19 không mở được bằng Odoo 18, vì Odoo không hạ cấp database.** Ai đã tạo database thử bằng 19 thì xóa đi; nếu có dữ liệu cần giữ thì báo nhóm trước. Phát triển module Odoo 18 trong `custom_addons/`, không sửa Odoo core hay code trong `oca/`. Sao lưu database kèm filestore bằng `scripts/backup.sh <db>`, khôi phục bằng `scripts/restore.sh <thư mục backup> <db đích>`; trên Windows dùng bản `.ps1` cùng tham số. Xem [hướng dẫn Docker](docs/docker_setup.md), [quy tắc cộng tác](docs/contributing.md) và [phiên bản image và OCA](docs/odoo_version.md).
