# Phiên bản Odoo, PostgreSQL và OCA

## Image Docker

Compose dùng official images, không build từ source local. Image refs trong `.env.example`:

| Thành phần | Tag | OCI index digest |
| --- | --- | --- |
| Odoo 18 Community | `odoo:18.0-20260926` | `sha256:60eb1b5006df85f900e300b6cc120d51ebd979379ee9588340adc2a84ffcd718` |
| PostgreSQL 15 | `postgres:15.19-bookworm` | `sha256:d4a8e1f88f475ee3e0137fa89d21ebc59f6c6ab16bf369ee92907607cc3455ae` |

Docker kéo image theo digest và bỏ qua tag; tag chỉ để người đọc biết phiên bản. Khi đổi image phải đổi cả tag lẫn digest, lấy digest bằng `docker buildx imagetools inspect <image>:<tag>`. Digest là OCI index; Docker chọn manifest theo kiến trúc máy. Image Odoo ở trên có manifest cho cả `linux/amd64` (máy Windows x86) và `linux/arm64` (Mac Apple Silicon). Nếu không có manifest phù hợp, dừng để kiểm tra trước khi thay image. PostgreSQL 15 đáp ứng yêu cầu PostgreSQL 12+ của Odoo 18.

Nguồn: [official Odoo image](https://hub.docker.com/_/odoo), [official PostgreSQL image](https://hub.docker.com/_/postgres), [Odoo Dockerfile 18.0](https://github.com/odoo/docker/tree/master/18.0), [Odoo 18 installation requirements](https://www.odoo.com/documentation/18.0/administration/on_premise/source.html). Giữ nguyên giấy phép và thông báo bản quyền của các image upstream.

## Vì sao dùng Odoo 18

Repository từng chạy Odoo 19. Nhóm chuyển về Odoo 18 vì module quét mã vạch `stock_barcodes` (OCA/stock-logistics-barcode) mới chỉ có nhánh 18.0, chưa có 19.0.

Tiêu chí chốt phiên bản: cả 3 module `stock_barcodes`, `account_financial_report` và `auditlog` phải có nhánh cho bản đó. Odoo 18 đáp ứng, Odoo 19 thì thiếu `stock_barcodes`.

Database tạo bằng Odoo 19 không mở được bằng Odoo 18, vì Odoo không hạ cấp database. Ai đã tạo database thử bằng 19 thì xóa đi; nếu có dữ liệu cần giữ thì báo nhóm trước.

## Module OCA

Các repository OCA là git submodule trong `oca/`, theo nhánh `18.0`. Commit lấy từ `git submodule status`:

| Repository | Nhánh | Commit |
| --- | --- | --- |
| [OCA/server-tools](https://github.com/OCA/server-tools) | `18.0` | `126afd2a62ec528386285aa753b24c15277d1f15` |
| [OCA/account-financial-reporting](https://github.com/OCA/account-financial-reporting) | `18.0` | `512c06f145f1e536a82ae28a944b0a3633ec8c31` |
| [OCA/server-ux](https://github.com/OCA/server-ux) | `18.0` | `8ae4369943650d72619f6b390e361847865fde30` |
| [OCA/reporting-engine](https://github.com/OCA/reporting-engine) | `18.0` | `e35a0fe4d52f9ffcc9335d66aded84586e3e8f78` |
| [OCA/stock-logistics-barcode](https://github.com/OCA/stock-logistics-barcode) | `18.0` | `4ad589d55e23702d552d22700292242340a61a74` |
| [OCA/stock-logistics-workflow](https://github.com/OCA/stock-logistics-workflow) | `18.0` | `1698ec3a319d37e170de522cb556dd72146214d1` |
| [OCA/web](https://github.com/OCA/web) | `18.0` | `c3120b0cf89a7b90ada70fd944c22b9b74fbd8a4` |

`stock_barcodes` nằm trong stock-logistics-barcode và cần thêm hai module ở repo khác: `stock_move_line_qty_picked` (stock-logistics-workflow) và `web_widget_numeric_step` (web). Ba repo này đi cùng nhau.

Khi cập nhật submodule, sửa bảng này trong cùng PR.

## Kiểm thử

Ngày 2026-10-16, môi trường đã chạy thử thành công với đúng các image và commit OCA ở trên, trên macOS (Apple Silicon, Docker Desktop, Docker Engine 29.8.2):

- Trước khi đổi image, PostgreSQL chỉ có `postgres`, `template0`, `template1`; không có database Odoo 19 nào phải xử lý.
- `docker compose config --quiet`, `pull`, `up -d`: `db` healthy, `odoo` chạy.
- `docker compose exec odoo odoo --version`: `Odoo Server 18.0-20260926`.
- `docker compose run --rm odoo odoo -d erp_smoke -i auditlog,account_financial_report,stock_barcodes,pl_base --stop-after-init --without-demo=all`: 59 module được cài, log không có traceback hay dòng ERROR/WARNING của Odoo. Các module OCA ở trạng thái `installed`: `auditlog`, `account_financial_report`, `date_range`, `date_range_account`, `report_xlsx`, `stock_barcodes`, `stock_move_line_qty_picked`, `web_widget_numeric_step`.
- `scripts/backup.sh erp_smoke` rồi `scripts/restore.sh` sang `erp_smoke_restored`: Odoo mở được database mới, đăng nhập `admin` được, 4 module trên vẫn `installed` và có menu Barcodes. Sau đó đã xóa `erp_smoke_restored` cùng thư mục backup.
- Database `erp_smoke` được giữ lại để xem giao diện Barcodes (đăng nhập `admin`/`admin`).

Phải dùng `docker compose run` cho lệnh cài module: lệnh đi qua entrypoint của image, entrypoint thêm tham số kết nối DB từ biến môi trường. `docker compose exec` không có các tham số này.

Bản PowerShell `scripts/backup.ps1` và `scripts/restore.ps1` chưa được chạy thử trên Windows.
