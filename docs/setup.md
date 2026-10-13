# Thiết lập repository và môi trường local

## Trạng thái đã xác minh

Git `2.47.0.windows.2` có trên máy khởi tạo. Source Odoo local hợp lệ, branch `18.0`, working tree sạch và SHA ghi tại [odoo_version.md](odoo_version.md). Thư mục nhóm được tạo cùng cấp để không thay đổi source upstream.

GitHub CLI (`gh`) không có trong PATH khi khảo sát; trạng thái đăng nhập GitHub chưa xác minh. Chưa tạo repository GitHub, remote hoặc push. Docker, PostgreSQL và việc chạy Odoo chưa được kiểm tra.

## Dùng source hiện có

Đường dẫn project nhóm:
`D:/UIT/HocTrenTruong/HK5/IS336_Hoach_Dinh_Nguon_Luc_Doanh_Nghiep/IS336-R11-G10-ERP`

Source hiện tại: `../odoo-18`. Không cần clone hoặc di chuyển. Từ project:

```powershell
git -C ../odoo-18 remote -v
git -C ../odoo-18 branch --show-current
git -C ../odoo-18 rev-parse HEAD
git -C ../odoo-18 status --short
Copy-Item .env.example .env
```

Chỉ chạy `Copy-Item` nếu `.env` chưa có để không ghi đè cấu hình cá nhân. Máy mới clone Odoo bên trong project theo README và đặt `ODOO_SOURCE_PATH=./odoo-18`. Chưa có chương trình đọc `.env`; chưa có mẫu `odoo.conf` hoặc cấu hình Docker.

## Xuất bản GitHub Private sau khi cài GitHub CLI

Cài GitHub CLI từ https://cli.github.com/ rồi mở terminal mới. Tại thư mục project:

```powershell
gh --version
gh auth login
gh auth status
gh api user --jq .login
```

Đăng nhập qua trình duyệt. Không gửi token vào chat hoặc lưu token trong repository. Thay `YOUR_GITHUB_ACCOUNT` bên dưới bằng login vừa xác minh:

```powershell
gh repo view YOUR_GITHUB_ACCOUNT/IS336-R11-G10-ERP --json nameWithOwner,isPrivate,url
```

Nếu repository tồn tại, dừng để kiểm tra nội dung và quyền sở hữu; không tạo trùng hoặc ghi đè. Nếu lệnh thất bại, phân biệt lỗi xác thực/mạng/quyền với việc repository thật sự không tồn tại, trước khi tạo:

```powershell
git status
git branch --show-current
git remote -v
gh repo create YOUR_GITHUB_ACCOUNT/IS336-R11-G10-ERP --private --source . --remote origin --push
gh repo view YOUR_GITHUB_ACCOUNT/IS336-R11-G10-ERP --json nameWithOwner,isPrivate,url
git ls-remote origin refs/heads/main
git rev-parse HEAD
```

Đối chiếu SHA local với remote `main`, xác nhận `isPrivate=true`. Sau khi thành công, cập nhật README và tài liệu trạng thái bằng commit mới. Owner cần cấp quyền cho thành viên trước khi họ clone repository Private.

## Biến môi trường và dữ liệu

`.env.example` chỉ chứa tên biến và giá trị đường dẫn mẫu, không có credentials. `.env` là cấu hình local bị ignore. Điền secret local sau khi nhóm thống nhất cấu hình thực thi. File config thực tế bị ignore; chỉ commit mẫu `*.example`/`*.example.conf` đã bỏ secret. Không commit database dumps, filestore, logs hoặc venv. `.gitignore` không thay thế việc review diff để phát hiện secret trong file khác.

## Các bước Docker + PostgreSQL tiếp theo

1. Kiểm tra Docker Desktop, WSL2, tài nguyên máy và khả năng chạy container.
2. Đối chiếu tài liệu chính thức Odoo 18 để chọn phiên bản PostgreSQL và phụ thuộc tương thích; chưa chốt version hoặc image tag trong scaffold này.
3. Thống nhất dùng source đã ghim; thiết kế Dockerfile/Compose với đường dẫn source, `custom_addons`, config, network và volume bền vững.
4. Tạo cấu hình mẫu không chứa secret, kiểm tra `docker compose config` và khởi động thử.
5. Kiểm tra kết nối database, tạo database thử, truy cập Odoo, nhận diện addons và dữ liệu còn sau restart; ghi kết quả thật vào tài liệu.

Các bước này chưa được thực hiện trong phạm vi khởi tạo repository.
