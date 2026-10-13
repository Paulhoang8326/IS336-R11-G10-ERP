# Phiên bản Odoo và PostgreSQL

## Runtime Docker Compose

Compose dùng official images, không build từ source local. Image refs trong `.env.example`:

| Thành phần | Tag | OCI index digest |
| --- | --- | --- |
| Odoo 19 Community | `odoo:19.0-20260926` | `sha256:dd9013e669caaa23d26765dc55814655eaeecca7cfc2c265dbabae913bce22fd` |
| PostgreSQL 15 | `postgres:15.19-bookworm` | `sha256:d4a8e1f88f475ee3e0137fa89d21ebc59f6c6ab16bf369ee92907607cc3455ae` |

Tag/digest được kiểm tra qua metadata registry trong Environment Audit. **Pull/runtime trên máy khởi tạo chưa được xác minh vì Docker Engine chưa khả dụng ngày 2026-10-13.** Khi Engine chạy, `docker compose pull` phải xác minh image thực nhận. Digest là OCI index; Docker chọn manifest theo kiến trúc máy. Nếu không có manifest phù hợp, dừng để kiểm tra trước khi thay image.

Nguồn: [official Odoo image](https://hub.docker.com/_/odoo), [official PostgreSQL image](https://hub.docker.com/_/postgres), [Odoo Dockerfile 19.0](https://github.com/odoo/docker/tree/master/19.0). Giữ nguyên giấy phép và thông báo bản quyền của các image upstream.
