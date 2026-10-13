# Phiên bản Odoo và PostgreSQL

## Runtime Docker Compose

Compose dùng official images, không build từ source local. Image refs trong `.env.example`:

| Thành phần | Tag | OCI index digest |
| --- | --- | --- |
| Odoo 19 Community | `odoo:19.0-20260926` | `sha256:dd9013e669caaa23d26765dc55814655eaeecca7cfc2c265dbabae913bce22fd` |
| PostgreSQL 15 | `postgres:15.19-bookworm` | `sha256:d4a8e1f88f475ee3e0137fa89d21ebc59f6c6ab16bf369ee92907607cc3455ae` |

Tag/digest Odoo 19 được kiểm tra lại qua `docker buildx imagetools inspect` ngày 2026-10-13. Digest là OCI index; Docker chọn manifest theo kiến trúc máy. PostgreSQL 15 đáp ứng yêu cầu PostgreSQL 13+ của Odoo 19. Kết quả pull và chạy thực tế được ghi tại [docker_setup.md](docker_setup.md).

Nguồn: [official Odoo image](https://hub.docker.com/_/odoo), [official PostgreSQL image](https://hub.docker.com/_/postgres), [Odoo Dockerfile 19.0](https://github.com/odoo/docker/tree/master/19.0), [Odoo 19 installation requirements](https://www.odoo.com/documentation/19.0/administration/on_premise/source.html). Giữ nguyên giấy phép và thông báo bản quyền của các image upstream.

## Lịch sử audit source Odoo 18 trước cleanup

Thông tin dưới đây ghi lại checkout đã được audit trước khi dọn source ngày 2026-10-13. Các file source Odoo 18 local đã được xóa; bảng này không mô tả dependency hiện tại và không yêu cầu clone hoặc phục hồi source.

| Thuộc tính | Giá trị |
| --- | --- |
| Edition | Community Edition |
| Version | 18.0 (`odoo/release.py`: `version_info = (18, 0, 0, FINAL, 0, '')`) |
| Remote `origin` | https://github.com/odoo/odoo.git |
| Branch local | `18.0` |
| HEAD SHA | `4ea65e6c252d1f10aa9df314b8225c623099cf92` |
| Source local | `../odoo-18` so với repository nhóm |

SHA này chỉ ghi nhận checkout Odoo 18 upstream tại thời điểm audit, **không phải source/runtime của Odoo 19 Docker image**. Source đó không được Git repository nhóm theo dõi. Không dùng source Odoo 18 làm căn cứ API cho module Odoo 19; không cần clone source để chạy Compose và không sửa Odoo core.
