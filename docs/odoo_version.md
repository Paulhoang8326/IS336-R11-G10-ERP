# Phiên bản Odoo và PostgreSQL

## Runtime Docker Compose

Compose dùng official images, không build từ source local. Image refs trong `.env.example`:

| Thành phần | Tag | OCI index digest |
| --- | --- | --- |
| Odoo 18 Community | `odoo:18.0-20260926` | `sha256:60eb1b5006df85f900e300b6cc120d51ebd979379ee9588340adc2a84ffcd718` |
| PostgreSQL 15 | `postgres:15.19-bookworm` | `sha256:d4a8e1f88f475ee3e0137fa89d21ebc59f6c6ab16bf369ee92907607cc3455ae` |

Tag/digest được kiểm tra qua metadata registry trong Environment Audit. **Pull/runtime trên máy khởi tạo chưa được xác minh vì Docker Engine chưa khả dụng ngày 2026-10-13.** Khi Engine chạy, `docker compose pull` phải xác minh image thực nhận. Digest là OCI index; Docker chọn manifest theo kiến trúc máy. Nếu không có manifest phù hợp, dừng để kiểm tra trước khi thay image.

Nguồn: [official Odoo image](https://hub.docker.com/_/odoo), [official PostgreSQL image](https://hub.docker.com/_/postgres), [Odoo Dockerfile 18.0](https://github.com/odoo/docker/tree/master/18.0). Giữ nguyên giấy phép và thông báo bản quyền của các image upstream.

## Source upstream tham chiếu trên máy khởi tạo

| Thuộc tính | Giá trị |
| --- | --- |
| Edition | Community Edition |
| Version | 18.0 (`odoo/release.py`: `version_info = (18, 0, 0, FINAL, 0, '')`) |
| Remote `origin` | https://github.com/odoo/odoo.git |
| Branch local | `18.0` |
| HEAD SHA | `4ea65e6c252d1f10aa9df314b8225c623099cf92` |
| Source local | `../odoo-18` so với repository nhóm |

SHA này chỉ mô tả checkout upstream riêng trên máy khởi tạo, **không phải commit của Docker image**. Source này không nằm trong Git repository nhóm. `odoo-18/` local trong repository nhóm cũng bị ignore. Không cần clone source để chạy Compose hoặc phát triển custom addons; không sửa Odoo core.
