# Phiên bản Odoo upstream

Kiểm tra local ngày **2026-10-13**:

| Thuộc tính | Giá trị |
| --- | --- |
| Edition | Community Edition |
| Version | 18.0 (`odoo/release.py`: `version_info = (18, 0, 0, FINAL, 0, '')`) |
| Remote `origin` | https://github.com/odoo/odoo.git |
| Branch local | `18.0` |
| HEAD SHA | `4ea65e6c252d1f10aa9df314b8225c623099cf92` |
| Commit subject | `[FIX] website: force padding on popup inside containers` |
| Working tree khi khảo sát | Sạch |
| Source local | `D:/UIT/HocTrenTruong/HK5/IS336_Hoach_Dinh_Nguon_Luc_Doanh_Nghiep/odoo-18` |

Đây là phiên bản đã kiểm tra trên máy, không phải tuyên bố về commit mới nhất của upstream. Repository nhóm không theo dõi source Odoo hoặc lịch sử Git upstream.

## Tái lập trên máy mới

Từ thư mục project nhóm, khi `odoo-18` chưa tồn tại:

```powershell
git clone --branch 18.0 --single-branch https://github.com/odoo/odoo.git odoo-18
git -C odoo-18 checkout --detach 4ea65e6c252d1f10aa9df314b8225c623099cf92
git -C odoo-18 rev-parse HEAD
git -C odoo-18 status --short
```

Detached HEAD ở SHA trên là chủ ý để ghim phiên bản. Không dùng `git pull` tự động cho source đã ghim. Khi cần nâng cấp, thống nhất trong nhóm, kiểm tra tương thích rồi cập nhật SHA trong tài liệu qua Pull Request. Nếu source đã tồn tại, chỉ kiểm tra trạng thái và SHA trước; không checkout, di chuyển hoặc ghi đè khi có thay đổi chưa commit.
