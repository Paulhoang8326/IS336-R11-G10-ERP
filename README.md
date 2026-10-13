# IS336-R11-G10-ERP

Đồ án môn **IS336 – Hoạch định nguồn lực doanh nghiệp**, lớp **IS336.R11**, **nhóm 10**, UIT.

Mục tiêu: tạo nền tảng cộng tác phát triển ERP trên **Odoo 18.0 Community Edition**. Doanh nghiệp, thành viên, phạm vi nghiệp vụ và module cần triển khai: **TBD**.

## Tech stack và trạng thái

- Odoo 18.0 Community Edition: source upstream đã có trên máy khởi tạo; phiên bản được ghim trong [docs/odoo_version.md](docs/odoo_version.md).
- Git; Windows; VS Code.
- Docker và PostgreSQL: dự kiến, chưa cài đặt hoặc kiểm chứng trong bước này.
- Repository cộng tác: tài liệu, thư mục custom addons/config và mẫu biến môi trường. Chưa có module nghiệp vụ hoặc hệ thống ERP chạy được.
- GitHub: chưa tạo/push tại thời điểm khởi tạo vì GitHub CLI (`gh`) không có trong PATH. URL và tài khoản sở hữu: **TBD**, cập nhật sau khi xác thực và xuất bản thành công.

## Cấu trúc

```text
IS336-R11-G10-ERP/
├── odoo-18/            # vị trí dự kiến cho máy clone mới; local only, Git ignore
├── custom_addons/     # module nhóm phát triển, hiện chỉ có .gitkeep
├── config/            # cấu hình local; chỉ theo dõi .gitkeep và mẫu *.example/*.example.conf
├── docs/
│   ├── setup.md
│   ├── contributing.md
│   └── odoo_version.md
├── .env.example
├── .gitignore
└── README.md
```

**Máy khởi tạo hiện giữ Odoo ở `../odoo-18`, cùng cấp với project.** Không tạo thư mục Odoo thứ hai, không di chuyển source, không sửa Odoo core. Cấu trúc trên cho phép các máy mới clone Odoo vào `odoo-18/` bị bỏ qua bởi Git nhóm.

## Clone repository nhóm và lấy Odoo

Sau khi repository Private được tạo và thành viên được cấp quyền, thay `YOUR_GITHUB_ACCOUNT` bằng owner thật:

```powershell
git clone https://github.com/YOUR_GITHUB_ACCOUNT/IS336-R11-G10-ERP.git
cd IS336-R11-G10-ERP
git clone --branch 18.0 --single-branch https://github.com/odoo/odoo.git odoo-18
git -C odoo-18 checkout --detach 4ea65e6c252d1f10aa9df314b8225c623099cf92
Copy-Item .env.example .env
```

Máy đã có source hợp lệ không clone lại: xem [setup.md](docs/setup.md). Với clone mới, sửa `ODOO_SOURCE_PATH=./odoo-18` trong `.env`. Các biến hiện chỉ là mẫu; chưa có Docker Compose hay launcher tự nạp chúng. Không đưa mật khẩu thật vào file tracked.

## Đồng bộ và làm việc nhóm

```powershell
git switch main
git pull --ff-only origin main
git switch -c feature/ten-thanh-vien-ten-tinh-nang
# Sau khi chỉnh sửa: xem diff rồi stage đúng file cần commit
git status
git diff
git add custom_addons/ten_module/__manifest__.py
git diff --cached
git commit -m "feat: describe the implemented change"
git push -u origin feature/ten-thanh-vien-ten-tinh-nang
```

Lệnh `git add` trên chỉ minh họa sau khi module thật đã tồn tại. `main` dành cho code ổn định; `feature/*`, `fix/*`, `docs/*` dành cho từng thành viên. Mở Pull Request vào `main`, yêu cầu review và kiểm tra trước merge; hạn chế push trực tiếp `main`. Branch protection chưa được cấu hình. Hướng dẫn pull, review và conflict: [contributing.md](docs/contributing.md).

## Bước tiếp theo

1. Cài/xác thực `gh`, kiểm tra trùng tên, tạo repository **Private** và push theo [setup.md](docs/setup.md).
2. Xác định doanh nghiệp, nghiệp vụ, vai trò thành viên và module (**TBD**).
3. Kiểm tra Docker Desktop/WSL2 và tài liệu Odoo 18 để chọn PostgreSQL phù hợp, rồi xây dựng và kiểm chứng cấu hình Docker riêng.
4. Chỉ công bố môi trường chạy được khi đã kiểm tra kết nối database, addons, lưu trữ bền vững và khởi động lại.
