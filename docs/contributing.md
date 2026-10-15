# Quy tắc cộng tác nhóm 10

## Source và phát triển module

Môi trường dùng official Odoo 19 Community image và PostgreSQL 15 qua [Docker Compose](docker_setup.md). Thành viên chỉ clone [repository nhóm](https://github.com/Paulhoang8326/IS336-R11-G10-ERP), không cần clone Odoo upstream. Đặt module trong `custom_addons/<module_name>/`; thư mục được bind mount read-only vào container tại `/mnt/extra-addons`, còn `oca/` tại `/mnt/oca`. Phát triển module tương thích Odoo 19, sửa code trên host, kiểm tra manifest, rồi dùng `docker compose restart odoo` sau khi đổi Python code. Cài/upgrade module chỉ sau khi nhóm chủ động tạo database.

Không sửa/commit Odoo core hoặc vendor source. Core được cung cấp bởi official Odoo 19 image; module nhóm phải tương thích với Odoo 19. Không cần clone source Odoo riêng. Nâng image/tag/digest hoặc đổi PostgreSQL cần PR và kiểm tra tương thích. Không commit `.env`, `config/odoo.conf`, secrets, dumps, logs hoặc runtime data.

## Module OCA

`oca/` chứa 4 repository OCA nhánh 19.0 dưới dạng git submodule. Không sửa code trong `oca/`: thay đổi sẽ mất khi cập nhật submodule và không thể commit vào repository nhóm. Cần đổi hành vi một module OCA thì viết module kế thừa trong `custom_addons/`.

Cập nhật một repository OCA lên commit mới nhất của nhánh 19.0, làm trên branch riêng:

~~~powershell
git submodule update --remote oca/<repo>
git diff --submodule
git add oca/<repo>
git commit -m "chore(oca): update <repo>"
~~~

Commit này đi qua PR như mọi thay đổi khác. Trong PR, cập nhật bảng commit ở [odoo_version.md](odoo_version.md) và ghi đã kiểm tra những module nào. Sau khi PR được merge, các thành viên chạy `git submodule update --init` sau `git pull` để lấy đúng commit.

## Git và Pull Request

- `main`: trạng thái ổn định, ưu tiên PR đã review.
- `feature/*`, `fix/*`, `docs/*`: công việc từng thành viên.
- Trước commit: xem `git status`, `git diff` và `git diff --cached`; stage đúng đường dẫn thuộc phạm vi thay đổi.
- PR mô tả hành vi, cách kiểm tra và kiểm thử chưa chạy. Thành viên khác review trước merge. Branch protection chưa được xác minh.

Ví dụ sau khi module thật đã tồn tại:

~~~powershell
git checkout main
git pull --ff-only origin main
git checkout -b feature/ten-thanh-vien-ten-tinh-nang
git status
git diff
git add custom_addons/ten_module/__manifest__.py
git diff --cached
git commit -m "feat: describe the implemented change"
git push -u origin feature/ten-thanh-vien-ten-tinh-nang
~~~

Khi đồng bộ branch đang làm, bảo toàn thay đổi local trước; dùng `git fetch origin` và merge `origin/main` sau khi review. Nếu có conflict, thống nhất nội dung từng file, stage từng file đã xử lý và `git merge --continue`. Không reset cứng hoặc force push để xử lý conflict.

## Cấu hình local

Chỉ commit `.env.example` và `config/odoo.example.conf` không chứa secrets. Bản `.env` và `config/odoo.conf` mỗi máy nằm ngoài Git. Xem [docker_setup.md](docker_setup.md) để cấu hình và quản lý volumes. Hiện mới có module khung `pl_base`; chưa có module nghiệp vụ hoặc bộ kiểm thử nghiệp vụ trong repository.
