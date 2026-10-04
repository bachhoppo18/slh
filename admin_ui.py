"""Login and administrator views for the desktop application."""
import json
import os
import queue
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


class AdminLoginDialog(tk.Toplevel):
    def __init__(self, parent, config_path):
        super().__init__(parent)
        self.parent = parent
        self.config_path = config_path
        self.result = None
        self.messages = queue.Queue()
        self.title("Đăng nhập SLH Tool")
        self.geometry("390x245")
        self.resizable(False, False)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        config = {}
        try:
            with open(config_path, "r", encoding="utf-8") as file:
                config = json.load(file)
        except (OSError, ValueError):
            pass
        self.url_var = tk.StringVar(value=os.environ.get("SLH_ADMIN_API_URL", config.get("api_url", "")))
        self.username_var = tk.StringVar()
        self.password_var = tk.StringVar()

        frame = ttk.Frame(self, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="Địa chỉ máy chủ:").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=self.url_var, width=42).grid(row=1, column=0, sticky="ew")
        ttk.Label(frame, text="Tên đăng nhập:").grid(row=2, column=0, sticky="w", pady=(8, 4))
        ttk.Entry(frame, textvariable=self.username_var).grid(row=3, column=0, sticky="ew")
        ttk.Label(frame, text="Mật khẩu:").grid(row=4, column=0, sticky="w", pady=(8, 4))
        ttk.Entry(frame, textvariable=self.password_var, show="*").grid(row=5, column=0, sticky="ew")
        self.status = ttk.Label(frame, text="", wraplength=350)
        self.status.grid(row=6, column=0, sticky="w", pady=(8, 2))
        self.login_button = ttk.Button(frame, text="Đăng nhập", command=self._login)
        self.login_button.grid(row=7, column=0, sticky="e", pady=(6, 0))
        frame.columnconfigure(0, weight=1)
        self.grab_set()
        self.after(100, self._poll_messages)

    def _login(self):
        url = self.url_var.get().strip().rstrip("/")
        username = self.username_var.get().strip()
        password = self.password_var.get()
        parsed_url = urlparse(url)
        local_hosts = {"localhost", "127.0.0.1", "::1"}
        if parsed_url.scheme != "https" and not (parsed_url.scheme == "http" and parsed_url.hostname in local_hosts):
            self.status.config(text="Máy chủ cần dùng HTTPS (HTTP chỉ dùng được trên localhost).")
            return
        if not username or not password:
            self.status.config(text="Nhập tên đăng nhập và mật khẩu.")
            return
        self.login_button.config(state="disabled")
        self.status.config(text="Đang xác thực và đồng bộ dữ liệu...")

        def worker():
            try:
                client = AdminClient(url)
                client.login(username, password)
                datasets = client.get_datasets()
                self.messages.put((client, datasets, None))
            except Exception as exc:
                self.messages.put((None, None, str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_messages(self):
        try:
            client, datasets, error = self.messages.get_nowait()
        except queue.Empty:
            if self.winfo_exists():
                self.after(100, self._poll_messages)
            return
        self.login_button.config(state="normal")
        if error:
            self.status.config(text=error)
            self.after(100, self._poll_messages)
            return
        self.result = (client, datasets)
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as file:
                json.dump({"api_url": self.url_var.get().strip().rstrip("/")}, file, ensure_ascii=False)
        except OSError:
            pass
        self.destroy()

    def _cancel(self):
        self.result = None
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