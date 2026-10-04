"""Login and administrator views for the desktop application."""
import json
import hashlib
import hmac
import os
import queue
import secrets
import threading
import tkinter as tk
from itertools import islice
from tkinter import messagebox, ttk
from urllib.parse import urlparse

from admin_client import AdminApiError, AdminClient


DATASET_LABELS = {
    "hanviet": "HanViet",
    "name": "Name",
    "vp": "VP",
    "blacklist": "Blacklist",
}
LABEL_DATASETS = {label: key for key, label in DATASET_LABELS.items()}
LOCAL_ADMIN_USERNAME = "admin"
LOCAL_ADMIN_DEFAULT_PASSWORD = "123456"
LOCAL_ADMIN_PASSWORD_ITERATIONS = 310_000


def _password_digest(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, LOCAL_ADMIN_PASSWORD_ITERATIONS
    )


def _write_local_admin(config_path, salt, password):
    os.makedirs(os.path.dirname(os.path.abspath(config_path)), exist_ok=True)
    temporary_path = config_path + ".tmp"
    with open(temporary_path, "w", encoding="utf-8") as file:
        json.dump({
            "username": LOCAL_ADMIN_USERNAME,
            "password_salt": salt.hex(),
            "password_hash": _password_digest(password, salt).hex(),
        }, file)
    os.replace(temporary_path, config_path)
    try:
        os.chmod(config_path, 0o600)
    except OSError:
        pass


def initialize_local_admin(config_path):
    try:
        with open(config_path, "r", encoding="utf-8") as file:
            config = json.load(file)
    except FileNotFoundError:
        config = None
    if config is not None and not isinstance(config, dict):
        raise ValueError("Tệp tài khoản cục bộ không hợp lệ.")
    if config is None or not all(key in config for key in ("password_salt", "password_hash")):
        _write_local_admin(config_path, secrets.token_bytes(16), LOCAL_ADMIN_DEFAULT_PASSWORD)
        return
    try:
        salt = bytes.fromhex(config["password_salt"])
        digest = bytes.fromhex(config["password_hash"])
    except (TypeError, ValueError) as exc:
        raise ValueError("Tệp tài khoản cục bộ không hợp lệ.") from exc
    if config.get("username") != LOCAL_ADMIN_USERNAME or len(salt) != 16 or len(digest) != 32:
        raise ValueError("Tệp tài khoản cục bộ không hợp lệ.")


def verify_local_admin(config_path, username, password):
    if username != LOCAL_ADMIN_USERNAME:
        return False
    try:
        with open(config_path, "r", encoding="utf-8") as file:
            config = json.load(file)
        salt = bytes.fromhex(config["password_salt"])
        expected = bytes.fromhex(config["password_hash"])
    except (OSError, ValueError, KeyError, TypeError):
        return False
    return hmac.compare_digest(_password_digest(password, salt), expected)


def change_local_admin_password(config_path, current_password, new_password):
    if len(new_password) < 8:
        raise ValueError("Mật khẩu mới cần có ít nhất 8 ký tự.")
    if not verify_local_admin(config_path, LOCAL_ADMIN_USERNAME, current_password):
        raise ValueError("Mật khẩu hiện tại không đúng.")
    _write_local_admin(config_path, secrets.token_bytes(16), new_password)


class AdminLoginDialog(tk.Toplevel):
    def __init__(self, parent, config_path):
        super().__init__(parent)
        self.parent = parent
        self.config_path = config_path
        self.result = None
        self.auth_error = None
        try:
            initialize_local_admin(config_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self.auth_error = str(exc)
        self.title("Đăng nhập SLH Tool")
        self.geometry("390x220")
        self.resizable(False, False)
        if parent.state() != "withdrawn":
            self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        self.password_var = tk.StringVar()

        frame = ttk.Frame(self, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text=f"Tài khoản: {LOCAL_ADMIN_USERNAME}").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Label(frame, text="Mật khẩu:").grid(row=1, column=0, sticky="w", pady=(8, 4))
        password_entry = ttk.Entry(frame, textvariable=self.password_var, show="*")
        password_entry.grid(row=2, column=0, sticky="ew")
        password_entry.bind("<Return>", lambda _event: self._login())
        ttk.Label(frame, text="Mật khẩu mặc định lần đầu: 123456", style="Muted.TLabel").grid(
            row=3, column=0, sticky="w", pady=(6, 0)
        )
        self.status = ttk.Label(frame, text=self.auth_error or "", wraplength=350)
        self.status.grid(row=4, column=0, sticky="w", pady=(6, 2))
        ttk.Button(frame, text="Đổi mật khẩu", command=self._change_password).grid(
            row=5, column=0, sticky="w", pady=(6, 0)
        )
        self.login_button = ttk.Button(frame, text="Đăng nhập", command=self._login)
        self.login_button.grid(row=5, column=0, sticky="e", pady=(6, 0))
        frame.columnconfigure(0, weight=1)
        self.grab_set()

    def _login(self):
        if self.auth_error:
            self.status.config(text=self.auth_error)
            return
        if not verify_local_admin(self.config_path, LOCAL_ADMIN_USERNAME, self.password_var.get()):
            self.status.config(text="Mật khẩu không đúng.")
            return
        self.result = True
        self.destroy()

    def _change_password(self):
        if self.auth_error:
            self.status.config(text=self.auth_error)
            return
        ChangePasswordDialog(self, self.config_path)

    def _cancel(self):
        self.result = None
        self.destroy()


class ChangePasswordDialog(tk.Toplevel):
    def __init__(self, parent, config_path):
        super().__init__(parent)
        self.config_path = config_path
        self.title("Đổi mật khẩu admin")
        self.geometry("390x250")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        self.current_password = tk.StringVar()
        self.new_password = tk.StringVar()
        self.confirm_password = tk.StringVar()
        fields = (
            ("Mật khẩu hiện tại:", self.current_password),
            ("Mật khẩu mới (ít nhất 8 ký tự):", self.new_password),
            ("Nhập lại mật khẩu mới:", self.confirm_password),
        )
        for row, (label, variable) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=row * 2, column=0, sticky="w", pady=(4, 2))
            entry = ttk.Entry(frame, textvariable=variable, show="*")
            entry.grid(row=row * 2 + 1, column=0, sticky="ew")
        self.status = ttk.Label(frame, text="", wraplength=350)
        self.status.grid(row=6, column=0, sticky="w", pady=(6, 2))
        ttk.Button(frame, text="Lưu mật khẩu", command=self._save).grid(row=7, column=0, sticky="e", pady=(6, 0))
        frame.columnconfigure(0, weight=1)

    def _save(self):
        if self.new_password.get() != self.confirm_password.get():
            self.status.config(text="Hai mật khẩu mới không khớp.")
            return
        try:
            change_local_admin_password(
                self.config_path, self.current_password.get(), self.new_password.get()
            )
        except (OSError, ValueError) as exc:
            self.status.config(text=str(exc))
            return
        self.destroy()


class AdminPanel(ttk.Frame):
    PAGE_SIZE = 100
    SEARCH_RESULT_LIMIT = 10_000

    def __init__(self, parent, app):
        super().__init__(parent, padding=10)
        self.app = app
        self.dataset_var = tk.StringVar(value="HanViet")
        self.search_var = tk.StringVar()
        self.offset = 0
        self.search_results = None
        self.messages = queue.Queue()
        self._build()
        self._refresh_page()
        self._refresh_users()
        self.after(100, self._poll_messages)

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        top = ttk.Frame(self)
        top.grid(row=0, column=0, sticky="ew")
        ttk.Label(top, text="Danh sách:").pack(side=tk.LEFT)
        self.dataset_combo = ttk.Combobox(top, textvariable=self.dataset_var, state="readonly", width=18,
                                          values=list(DATASET_LABELS.values()))
        self.dataset_combo.pack(side=tk.LEFT, padx=6)
        self.dataset_combo.bind("<<ComboboxSelected>>", lambda _event: self._reset_view())
        self.search_entry = ttk.Entry(top, textvariable=self.search_var, width=30)
        self.search_entry.pack(side=tk.LEFT, padx=(8, 4))
        self.search_entry.bind("<Return>", lambda _event: self._search())
        ttk.Button(top, text="Tìm", command=self._search).pack(side=tk.LEFT)
        ttk.Button(top, text="Tất cả", command=self._clear_search).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Đồng bộ", command=self._sync).pack(side=tk.RIGHT)

        self.list_tree = ttk.Treeview(self, columns=("key", "value"), show="headings", height=10)
        self.list_tree.heading("key", text="Từ khóa")
        self.list_tree.heading("value", text="Nghĩa / nội dung")
        self.list_tree.column("key", width=230, stretch=True)
        self.list_tree.column("value", width=500, stretch=True)
        self.list_tree.grid(row=2, column=0, sticky="nsew", pady=6)
        scroll = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.list_tree.yview)
        scroll.grid(row=2, column=1, sticky="ns", pady=6)
        self.list_tree.configure(yscrollcommand=scroll.set)
        pager = ttk.Frame(self)
        pager.grid(row=3, column=0, sticky="ew")
        self.page_label = ttk.Label(pager, text="")
        self.page_label.pack(side=tk.LEFT)
        ttk.Button(pager, text="Sau", command=lambda: self._move_page(1)).pack(side=tk.RIGHT)
        ttk.Button(pager, text="Trước", command=lambda: self._move_page(-1)).pack(side=tk.RIGHT, padx=4)

        ttk.Separator(self, orient=tk.HORIZONTAL).grid(row=4, column=0, sticky="ew", pady=10)
        ttk.Label(self, text="Thêm mục lên GitHub", font=("Segoe UI", 10, "bold")).grid(row=5, column=0, sticky="w")
        add = ttk.Frame(self)
        add.grid(row=6, column=0, sticky="ew", pady=5)
        add.columnconfigure(1, weight=1)
        self.key_var = tk.StringVar()
        self.value_var = tk.StringVar()
        ttk.Label(add, text="Từ khóa:").grid(row=0, column=0, sticky="w")
        self.key_entry = ttk.Entry(add, textvariable=self.key_var)
        self.key_entry.grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Label(add, text="Giá trị:").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(add, textvariable=self.value_var).grid(row=1, column=1, sticky="ew", padx=5, pady=4)
        self.add_button = ttk.Button(add, text="Thêm", command=self._add_entry)
        self.add_button.grid(row=0, column=2, rowspan=2, padx=5)

        ttk.Separator(self, orient=tk.HORIZONTAL).grid(row=7, column=0, sticky="ew", pady=8)
        user_row = ttk.Frame(self)
        user_row.grid(row=8, column=0, sticky="ew")
        ttk.Label(user_row, text="Tài khoản user", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        ttk.Button(user_row, text="Cập nhật", command=self._refresh_users).pack(side=tk.RIGHT)
        user_form = ttk.Frame(self)
        user_form.grid(row=9, column=0, sticky="ew", pady=5)
        self.new_username = tk.StringVar()
        self.new_password = tk.StringVar()
        ttk.Label(user_form, text="Tên:").pack(side=tk.LEFT)
        ttk.Entry(user_form, textvariable=self.new_username, width=22).pack(side=tk.LEFT, padx=4)
        ttk.Label(user_form, text="Mật khẩu (tối thiểu 12 ký tự):").pack(side=tk.LEFT, padx=(6, 0))
        ttk.Entry(user_form, textvariable=self.new_password, show="*", width=24).pack(side=tk.LEFT, padx=4)
        ttk.Button(user_form, text="Cấp tài khoản", command=self._create_user).pack(side=tk.LEFT, padx=4)
        self.users_tree = ttk.Treeview(self, columns=("username", "role"), show="headings", height=4)
        self.users_tree.heading("username", text="Tên đăng nhập")
        self.users_tree.heading("role", text="Quyền")
        self.users_tree.column("username", width=240)
        self.users_tree.column("role", width=120)
        self.users_tree.grid(row=10, column=0, sticky="ew")
        self.status = ttk.Label(self, text="")
        self.status.grid(row=11, column=0, sticky="w", pady=(5, 0))

    def _source_items(self):
        key = LABEL_DATASETS[self.dataset_var.get()]
        if key == "hanviet":
            return self.app.translate_tab.engine.hv_dict
        if key == "name":
            return self.app.translate_tab.engine.name_raw
        if key == "vp":
            return self.app.translate_tab.engine.vp_raw
        return NAME_BLACKLIST

    def _reset_view(self):
        self.offset = 0
        self.search_results = None
        self._refresh_page()

    def _search(self):
        query = self.search_var.get().strip().casefold()
        if not query:
            self._clear_search()
            return
        self.status.config(text="Đang tìm trong danh sách...")
        source = self._source_items()

        def worker():
            matches = []
            entries = source.items() if hasattr(source, "items") else ((word, "") for word in source)
            for key, value in entries:
                shown = value.get("val", "") if isinstance(value, dict) else str(value)
                if query in str(key).casefold() or query in shown.casefold():
                    matches.append((key, shown))
                    if len(matches) >= self.SEARCH_RESULT_LIMIT:
                        break
            self.messages.put(("search", matches, None))

        threading.Thread(target=worker, daemon=True).start()

    def _clear_search(self):
        self.search_var.set("")
        self.search_results = None
        self.offset = 0
        self._refresh_page()

    def _refresh_page(self):
        self.list_tree.delete(*self.list_tree.get_children())
        if self.search_results is None:
            source = self._source_items()
            entries = source.items() if hasattr(source, "items") else ((word, "") for word in source)
            rows = list(islice(entries, self.offset, self.offset + self.PAGE_SIZE))
            more = len(source) > self.offset + len(rows)
            count = f"Đang xem {self.offset + 1 if rows else 0}-{self.offset + len(rows)} / {len(source):,}"
        else:
            rows = self.search_results[self.offset:self.offset + self.PAGE_SIZE]
            more = self.offset + len(rows) < len(self.search_results)
            count = f"{len(self.search_results):,} kết quả khớp"
        for key, value in rows:
            shown = value.get("val", "") if isinstance(value, dict) else value
            self.list_tree.insert("", tk.END, values=(key, shown))
        self.page_label.config(text=f"{count}  |  Trang {self.offset // self.PAGE_SIZE + 1}")
        self._next_enabled = more
        self.key_entry.configure(state="disabled" if LABEL_DATASETS[self.dataset_var.get()] == "blacklist" else "normal")

    def _move_page(self, amount):
        next_offset = max(0, self.offset + amount * self.PAGE_SIZE)
        if amount > 0 and self.search_results is None and next_offset >= len(self._source_items()):
            return
        if amount > 0 and self.search_results is not None and next_offset >= len(self.search_results):
            return
        self.offset = next_offset
        self._refresh_page()

    def _add_entry(self):
        dataset = LABEL_DATASETS[self.dataset_var.get()]
        key, value = self.key_var.get().strip(), self.value_var.get().strip()
        if not value or (dataset != "blacklist" and not key):
            messagebox.showwarning("Thiếu dữ liệu", "Nhập từ khóa và giá trị cần thêm.", parent=self)
            return
        self.add_button.config(state="disabled")
        self.status.config(text="Đang cập nhật GitHub...")

        def worker():
            try:
                self.app.admin_client.add_entry(dataset, key, value)
                data = self.app.admin_client.get_datasets()
                self.messages.put(("entry", data, None))
            except Exception as exc:
                self.messages.put(("entry", None, str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _create_user(self):
        username, password = self.new_username.get().strip(), self.new_password.get()
        if not username or not password:
            messagebox.showwarning("Thiếu thông tin", "Nhập tên đăng nhập và mật khẩu.", parent=self)
            return

        def worker():
            try:
                self.app.admin_client.create_user(username, password)
                users = self.app.admin_client.list_users()
                self.messages.put(("users", users, None))
            except Exception as exc:
                self.messages.put(("users", None, str(exc)))

        threading.Thread(target=worker, daemon=True).start()
        self.status.config(text="Đang tạo tài khoản...")

    def _refresh_users(self):
        def worker():
            try:
                self.messages.put(("users", self.app.admin_client.list_users(), None))
            except Exception as exc:
                self.messages.put(("users", None, str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _sync(self):
        self.status.config(text="Đang đồng bộ GitHub...")

        def worker():
            try:
                self.messages.put(("entry", self.app.admin_client.get_datasets(), None))
            except Exception as exc:
                self.messages.put(("entry", None, str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_messages(self):
        if not self.winfo_exists():
            return
        try:
            kind, result, error = self.messages.get_nowait()
        except queue.Empty:
            self.after(100, self._poll_messages)
            return
        if kind == "entry":
            self.add_button.config(state="normal")
            if error:
                self.status.config(text=error)
            else:
                self.app._apply_admin_datasets(result)
                self.key_var.set("")
                self.value_var.set("")
                self.status.config(text="Đã cập nhật dữ liệu từ GitHub.")
                self._reset_view()
                if hasattr(self.app, "translate_tab"):
                    self.app.translate_tab._load_dicts_async()
        elif kind == "search":
            self.search_results = result
            self.offset = 0
            self._refresh_page()
            self.status.config(text=f"Tìm thấy {len(result):,} mục (hiển thị tối đa {self.SEARCH_RESULT_LIMIT:,}).")
        else:
            if error:
                self.status.config(text=error)
            else:
                self.users_tree.delete(*self.users_tree.get_children())
                for user in result:
                    self.users_tree.insert("", tk.END, values=(user["username"], user["role"]))
                self.status.config(text=f"Đang có {len(result)} tài khoản.")
        self.after(100, self._poll_messages)