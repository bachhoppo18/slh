# -*- mode: python ; coding: utf-8 -*-
# Build bằng lệnh:  pyinstaller van_ban_tool.spec
#
# Chế độ --onedir (KHÔNG dùng --onefile): mở app nhanh hơn hẳn onefile (onefile phải
# tự giải nén ra thư mục tạm mỗi lần mở) và ít bị phần mềm diệt virus / SmartScreen
# báo nhầm hơn. Kết quả nằm trong thư mục dist/van_ban_tool/ gồm van_ban_tool.exe
# và các file .dll/.pyd đi kèm — Inno Setup (installer.iss) sẽ đóng gói cả thư mục
# này thành 1 file cài đặt duy nhất để đưa cho người dùng.

import sys
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

a = Analysis(
    ['van_ban_tool.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('app.ico', '.'),   # icon nhúng theo exe, app đọc qua _bundled_dir()/app.ico lúc chạy
    ],
    hiddenimports=(
        collect_submodules('PIL')
        + collect_submodules('mammoth')
        + ['xml.etree.ElementTree']
    ),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Không cần các thư viện nặng này trong exe: HanLP/torch chạy ở Python
        # RIÊNG (gói hanlp_runtime tải về sau), không nhúng vào bản thân app.
        'torch', 'hanlp', 'transformers', 'numpy', 'matplotlib', 'scipy',
        'test', 'unittest', 'pydoc_data',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='van_ban_tool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # để False cho an toàn: UPX nén exe hay bị Windows Defender báo nhầm
    console=False,       # ẩn cửa sổ đen (cmd) — đây là app giao diện, không phải công cụ dòng lệnh
    icon='app.ico',
    version='version_info.txt' if sys.platform == 'win32' else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='van_ban_tool',
)
