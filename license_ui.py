"""License activation dialog shown before opening the desktop application."""
import json
import os
import queue
import tkinter as tk
import threading
from tkinter import ttk

from license_client import LicenseError, activate, get_hwid


class LicenseDialog(tk.Toplevel):
    def __init__(self, parent, config_path):
        super().__init__(parent)
        self.config_path = config_path
        self.result = None
        self._activation_results = queue.Queue()
        self.title("Kích hoạt SLH Tool")
        self.geometry("560x300")
        self.resizable(False, False)
        if parent.state() != "withdrawn":
            self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        try:
            with open(config_path, "r", encoding="utf-8") as file:
                config = json.load(file)
        except (OSError, ValueError):
            config = {}
        if not isinstance(config, dict):
            config = {}
        self.key_var = tk.StringVar(value=config.get("license_key", ""))
        self.hwid = get_hwid()
        self.hwid_var = tk.StringVar(value=self.hwid)

        frame = ttk.Frame(self, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="Mã máy (gửi cho người cấp license):").grid(
            row=0, column=0, sticky="w", pady=(0, 4)
        )
        machine_row = ttk.Frame(frame)
        machine_row.grid(row=1, column=0, sticky="ew")
        self.hwid_entry = ttk.Entry(machine_row, textvariable=self.hwid_var, state="readonly")
        self.hwid_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(machine_row, text="Sao chép", command=self._copy_hwid).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Label(frame, text="Mỗi máy chỉ dùng được key đã cấp riêng cho mã máy này.",
                  style="Muted.TLabel").grid(row=2, column=0, sticky="w", pady=(4, 10))
        ttk.Label(frame, text="Mã kích hoạt:").grid(row=3, column=0, sticky="w", pady=(0, 4))
        self.key_entry = ttk.Entry(frame, textvariable=self.key_var)
        self.key_entry.grid(row=4, column=0, sticky="ew")
        self.key_entry.bind("<Return>", lambda _event: self._activate())
        self.status = ttk.Label(frame, text="", wraplength=380)
        self.status.grid(row=5, column=0, sticky="w", pady=(10, 4))
        self.activate_button = ttk.Button(frame, text="Kích hoạt", command=self._activate)
        self.activate_button.grid(row=6, column=0, sticky="e", pady=(4, 0))
        frame.columnconfigure(0, weight=1)
        self.grab_set()
        if self.key_var.get().strip():
            self.after(0, self._activate)

    def _copy_hwid(self):
        self.clipboard_clear()
        self.clipboard_append(self.hwid)
        self.status.config(text="Đã sao chép mã máy.")

    def _activate(self):
        key = self.key_var.get().strip()
        if len(key) < 16:
            self.status.config(text="Mã kích hoạt không hợp lệ.")
            return
        self.activate_button.config(state="disabled")
        self.status.config(text="Đang xác thực key và thiết bị...")

        def worker():
            try:
                activate(key, self.hwid)
                error = None
            except LicenseError as exc:
                error = str(exc)
            except Exception as exc:
                error = f"Lỗi khi xác thực license: {exc}"
            self._activation_results.put(error)

        threading.Thread(target=worker, daemon=True).start()
        self.after(100, lambda: self._poll_activation_result(key))

    def _poll_activation_result(self, key):
        if not self.winfo_exists():
            return
        try:
            error = self._activation_results.get_nowait()
        except queue.Empty:
            self.after(100, lambda: self._poll_activation_result(key))
            return

        self.activate_button.config(state="normal")
        if error:
            self.status.config(text=error)
            return
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.config_path)), exist_ok=True)
            temporary_path = self.config_path + ".tmp"
            with open(temporary_path, "w", encoding="utf-8") as file:
                json.dump({"license_key": key}, file)
            os.replace(temporary_path, self.config_path)
        except OSError as exc:
            self.status.config(text=f"Đã kích hoạt nhưng không lưu được key: {exc}")
            return
        self.result = True
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()