# Quy tắc cộng tác nhóm 10

## Branch và Pull Request

- `main`: trạng thái ổn định, ưu tiên cập nhật bằng Pull Request đã review.
- `feature/*`: tính năng; `fix/*`: sửa lỗi; `docs/*`: tài liệu.
- Mỗi thành viên tạo branch riêng, ví dụ `feature/nguyen-sale-report`.
- Module nhóm nằm trong `custom_addons/`; không sửa hoặc commit Odoo core.
- Trước commit, xem `git diff` và `git diff --cached`; stage đường dẫn cụ thể để tránh đưa secret/runtime vào Git.
- PR mô tả thay đổi, cách kiểm tra và giới hạn chưa xác minh. Yêu cầu ít nhất một thành viên review trước merge. Đây là quy ước nhóm, chưa được cưỡng chế bằng branch protection.

## Clone và commit đầu tiên

Sau khi có URL GitHub thật và quyền truy cập:

```powershell
git clone https://github.com/YOUR_GITHUB_ACCOUNT/IS336-R11-G10-ERP.git
cd IS336-R11-G10-ERP
git switch main
git pull --ff-only origin main
git switch -c docs/ten-thanh-vien-setup
# Chỉnh sửa tài liệu thật trước khi commit
git diff
git add docs/setup.md
git diff --cached
git commit -m "docs: clarify local setup"
git push -u origin docs/ten-thanh-vien-setup
```

Tạo Pull Request trên GitHub từ branch vừa push vào `main`. Không push trực tiếp vào `main` cho công việc thường ngày.

## Đồng bộ branch đang làm

Commit hoặc stash công việc local trước khi đồng bộ:

```powershell
git status
git fetch origin
git merge origin/main
# Kiểm tra thay đổi và chạy kiểm tra phù hợp với phần đã sửa
git push
```

Với branch dùng chung, khi cần lấy commit của người khác: `git pull --ff-only`. Nếu không thể fast-forward, xem `git log --oneline --graph --all` rồi thống nhất merge; không force push hoặc reset để loại bỏ công việc của người khác.

Sau khi PR đã merge:

```powershell
git switch main
git pull --ff-only origin main
```

## Conflict cơ bản

1. Chạy `git status` để biết file xung đột.
2. Mở từng file, đọc hai phía quanh `<<<<<<<`, `=======`, `>>>>>>>`. Trao đổi với tác giả nếu logic không rõ.
3. Giữ nội dung đúng đã thống nhất, xóa marker, kiểm tra diff và chạy kiểm tra phù hợp.
4. Stage từng file đã giải quyết, rồi hoàn tất merge:

```powershell
git add docs/setup.md
git diff --cached
git merge --continue
git push
```

Đường dẫn trong ví dụ phải thay bằng file conflict thực tế. Nếu chưa muốn tiếp tục merge, `git merge --abort` quay về trước merge; nên bắt đầu merge từ working tree sạch. Không dùng `reset --hard` hoặc force push để giải quyết conflict.

## Cấu hình và phiên bản

Copy `.env.example` thành `.env` nếu file chưa tồn tại, điền giá trị riêng của máy. Không commit credentials. Clone upstream và ghim SHA theo [odoo_version.md](odoo_version.md); nâng phiên bản phải qua PR có kiểm tra tương thích. Chưa có module hoặc bộ kiểm thử nghiệp vụ trong scaffold này.
