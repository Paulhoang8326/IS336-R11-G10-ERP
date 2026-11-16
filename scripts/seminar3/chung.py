"""Phần dùng chung của script seminar 3: kết nối Odoo và quản lý database.

Mật khẩu admin Odoo: ODOO_PASSWORD, không có thì hỏi. Mật khẩu master (nhân bản, xóa
database): ODOO_MASTER_PASSWORD, không có thì đọc admin_passwd trong config/odoo.conf.
"""

import configparser
import getpass
import os
import sys
import xmlrpc.client
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from seed_import import Odoo  # noqa: E402,F401

URL = "http://localhost:8069"
DB_CHINH = "pl_moc"
DB_SEMINAR = "phanlam_seminar3"
DB_CHECK = "phanlam_seminar3_check"
DB_CLEAN = "phanlam_seminar3_clean"
MA_SP = "NCC01-SIM12"
TEN_SP = "Dầu ăn Simply 1L (thùng 12 chai)"
MA_O = "A-01-1"


def mat_khau_master():
    mk = os.environ.get("ODOO_MASTER_PASSWORD")
    if mk:
        return mk
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(ROOT / "config" / "odoo.conf", encoding="utf-8")
    mk = cfg.get("options", "admin_passwd", fallback=None)
    if not mk:
        sys.exit("Thiếu mật khẩu master: đặt ODOO_MASTER_PASSWORD hoặc tạo config/odoo.conf")
    return mk


class QuanLyDb:
    def __init__(self, url):
        self.rpc = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/db", allow_none=True)
        self.master = mat_khau_master()

    def co(self, ten):
        return ten in self.rpc.list()

    def xoa(self, ten):
        if self.co(ten):
            self.rpc.drop(self.master, ten)

    def nhan_ban(self, nguon, dich):
        if not self.co(nguon):
            sys.exit(f"Không có database nguồn {nguon}")
        self.rpc.duplicate_database(self.master, nguon, dich)


def ket_noi(url, db, user="admin"):
    password = os.environ.get("ODOO_PASSWORD") or getpass.getpass(f"Mật khẩu Odoo của {user}: ")
    return Odoo(url, db, user, password)


def goi(od, model, method, *args, **kw):
    """Như od(...), nhưng chấp nhận phương thức trả về None hoặc recordset.

    XML-RPC của Odoo chỉ báo "cannot marshal" khi đóng gói kết quả, lúc giao dịch đã commit xong.
    """
    try:
        return od(model, method, *args, **kw)
    except xmlrpc.client.Fault as e:
        if "cannot marshal" in e.faultString:
            return None
        raise
