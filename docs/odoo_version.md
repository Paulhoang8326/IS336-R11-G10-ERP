# Phiên bản Odoo, PostgreSQL và OCA

## Image Docker

Compose dùng official images, không build từ source local. Image refs trong `.env.example`:

| Thành phần | Tag | OCI index digest |
| --- | --- | --- |
| Odoo 19 Community | `odoo:19.0-20260926` | `sha256:dd9013e669caaa23d26765dc55814655eaeecca7cfc2c265dbabae913bce22fd` |
| PostgreSQL 15 | `postgres:15.19-bookworm` | `sha256:d4a8e1f88f475ee3e0137fa89d21ebc59f6c6ab16bf369ee92907607cc3455ae` |

Docker kéo image theo digest và bỏ qua tag; tag chỉ để người đọc biết phiên bản. Khi đổi image phải đổi cả tag lẫn digest, lấy digest bằng `docker buildx imagetools inspect <image>:<tag>`. Digest là OCI index; Docker chọn manifest theo kiến trúc máy. Nếu không có manifest phù hợp, dừng để kiểm tra trước khi thay image. PostgreSQL 15 đáp ứng yêu cầu PostgreSQL 13+ của Odoo 19.

Nguồn: [official Odoo image](https://hub.docker.com/_/odoo), [official PostgreSQL image](https://hub.docker.com/_/postgres), [Odoo Dockerfile 19.0](https://github.com/odoo/docker/tree/master/19.0), [Odoo 19 installation requirements](https://www.odoo.com/documentation/19.0/administration/on_premise/source.html). Giữ nguyên giấy phép và thông báo bản quyền của các image upstream.

## Module OCA

Các repository OCA là git submodule trong `oca/`, theo nhánh `19.0`. Commit lấy từ `git submodule status`:

| Repository | Nhánh | Commit |
| --- | --- | --- |
| [OCA/server-tools](https://github.com/OCA/server-tools) | `19.0` | `ff085d56f10e5d1dc68ef85482eb3fc34a5b62d2` |
| [OCA/account-financial-reporting](https://github.com/OCA/account-financial-reporting) | `19.0` | `0078bc03f234d1caa8b9f40324678ce9dbed2a72` |
| [OCA/server-ux](https://github.com/OCA/server-ux) | `19.0` | `2e040168c4ed27ac6e732c68516ca47781eb1a0f` |
| [OCA/reporting-engine](https://github.com/OCA/reporting-engine) | `19.0` | `b9e8c6cdd2d106614eddaf81bd78f487ae35db45` |

Khi cập nhật submodule, sửa bảng này trong cùng PR.

## Kiểm thử

Ngày 2026-10-15, môi trường đã chạy thử thành công với đúng các image và commit OCA ở trên, trên macOS (Apple Silicon, Docker Desktop, Docker Engine 29.8.2):

- `docker compose config --quiet`, `pull`, `up -d`: `db` healthy, `odoo` chạy.
- `docker compose exec odoo odoo --version`: `Odoo Server 19.0-20260926`.
- Cài `auditlog`, `account_financial_report`, `pl_base` vào database thử `erp_smoke`: cả ba cùng các phụ thuộc `account`, `date_range`, `report_xlsx` ở trạng thái `installed`.
- `scripts/backup.sh` rồi `scripts/restore.sh` sang `erp_smoke_restored`: Odoo mở được database mới; số bảng, module, attachment và file filestore khớp bản gốc. Restore đè lên database đã có thì script hỏi xác nhận, trả lời không thì dừng.
- http://localhost:8069 hiện trang tạo database sau khi xóa hai database thử.

Bản PowerShell `scripts/backup.ps1` và `scripts/restore.ps1` chưa được chạy thử trên Windows.
