#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""

============================================================

  VĂN BẢN TOOL - Tích hợp 3 chức năng

  1. Lọc tên nhân vật

  2. Tạo EPUB

  3. Dịch QT

============================================================

Build EXE:

    pip install pyinstaller

    pyinstaller --onefile --windowed --icon=app.ico slhtool.py

============================================================

"""

import os

import re

import csv

import sys

import shutil

import tempfile

import subprocess

import tkinter as tk

from tkinter import filedialog, messagebox, ttk

from collections import Counter

from threading import Thread
import threading
import webbrowser

# ── Giao diện: bảng màu xanh lá + hồng pastel (sửa ở đây, toàn app đổi theo) ──
THEME = {
    "bg":     "#f3f8f4",   # nền cửa sổ (xanh lá rất nhạt)
    "panel":  "#ffffff",   # nền ô nhập / bảng
    "ink":    "#24352b",   # chữ chính
    "muted":  "#6b7f72",   # chữ phụ
    "border": "#c3d8ca",   # viền
    "dis_bg": "#eef2ef",   # nền khi bị vô hiệu
    "g700":   "#2f6f4e",   # xanh lá đậm  (nút chính, tiêu đề)
    "g500":   "#5aa77a",   # xanh lá      (hover, focus)
    "g200":   "#cfe8d8",
    "g100":   "#e6f4ea",   # xanh lá nhạt (nút thường, tiêu đề bảng)
    "p300":   "#f6b8cf",   # hồng pastel  (dòng đang chọn, hover)
    "p200":   "#f9d3e2",
    "p100":   "#fdebf2",   # hồng nhạt    (nút xóa, tab hover)
    "p700":   "#a13d68",   # chữ nhấn hồng
}
FONT_UI = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_TEXT = ("Segoe UI", 11)      # vùng đọc/nhập văn bản
FONT_MONO = ("Consolas", 10)      # chỉ dùng cho nhật ký (log)

# ══════════════════════════════════════════════════════════════════════════
#  PHIÊN BẢN & CẬP NHẬT — ĐIỀN LẠI 2 DÒNG NÀY SAU KHI TẠO REPO GITHUB CỦA BẠN
# ══════════════════════════════════════════════════════════════════════════
APP_VERSION = "1.0.0"
GITHUB_REPO = "bachhoppo18/slh"          # repo chứa mã nguồn + bản .exe (GitHub Releases)
DATA_REPO   = "bachhoppo18/slh"          # repo riêng, CHỈ chứa danh sách loại trừ — bạn sửa hoài ở đây
DATA_BRANCH = "main"

HANLP_PACK_URL = f"https://github.com/{GITHUB_REPO}/releases/download/hanlp-pack-v1/hanlp_pack.zip"
UPDATE_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
DATA_RAW_BASE = f"https://raw.githubusercontent.com/{DATA_REPO}/{DATA_BRANCH}/"


def _bundled_dir():
    """Thư mục CHỨA EXE (hoặc file .py khi chạy bằng Python) — CHỈ ĐỌC.

    Dùng để tìm tài nguyên đóng gói sẵn (icon...). KHÔNG ghi dữ liệu vào đây vì
    khi cài vào Program Files, Windows không cho ghi ở đó nếu không chạy Admin.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _app_data_dir():
    """Thư mục GHI DỮ LIỆU của app: cấu hình, từ điển, danh sách loại trừ, gói HanLP.

    Windows  : %APPDATA%\SLHTool   (vd. C:\\Users\\Ten\\AppData\\Roaming\\SLHTool)
    Khác     : ~/.slhtool           (dùng khi chạy thử bằng Python trên Linux/Mac)
    Luôn ghi được dù EXE được cài vào Program Files.
    """
    appdata = os.environ.get("APPDATA")
    d = os.path.join(appdata, "SLHTool") if appdata else os.path.join(os.path.expanduser("~"), ".slhtool")
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        pass
    return d


APP_DATA_DIR = _app_data_dir()
HANLP_RUNTIME_DIR = os.path.join(APP_DATA_DIR, "hanlp_runtime")


# ── Đồng bộ danh sách loại trừ / họ / ký tự cắt từ DATA_REPO (nền, tự động) ──
def sync_admin_lists(log=None):
    """Tải bản mới của các file trong CUSTOM_LIST_DEFS từ DATA_REPO nếu có version mới.

    Chỉ ghi đè phần "admin" (đồng bộ từ GitHub) — không đụng tới phần người dùng tự
    thêm trong app (được lưu chung 1 file, xem `load_custom_list`/`save_custom_list`:
    khi đồng bộ, hai tập được GỘP rồi ghi lại, nên chữ người dùng tự thêm không mất).
    Trả về True nếu có cập nhật được áp dụng.
    """
    log = log or (lambda _m: None)
    ver_path = os.path.join(APP_DATA_DIR, "data_version.json")
    tmp_path = ver_path + ".tmp"
    local_ver = 0
    try:
        local_ver = json.load(open(ver_path, encoding="utf-8")).get("version", 0)
    except Exception:
        pass
    try:
        _trans_download(DATA_RAW_BASE + "version.json", tmp_path, timeout=20)
        manifest = json.load(open(tmp_path, encoding="utf-8"))
    except Exception as e:
        log(f"Không kiểm tra được cập nhật danh sách: {e}")
        return False
    remote_ver = manifest.get("version", 0)
    if remote_ver <= local_ver:
        os.replace(tmp_path, ver_path)          # vẫn lưu lại để lần sau khỏi tải lại bản y hệt
        return False

    changed = False
    for key, info in CUSTOM_LIST_DEFS.items():
        fname = manifest.get("files", {}).get(key)
        if not fname:
            continue
        try:
            tmp = _custom_list_path(key) + ".remote"
            _trans_download(DATA_RAW_BASE + fname, tmp, timeout=30)
            remote_words = _custom_list_expand(key, open(tmp, encoding="utf-8").read().split("\n"))
            os.remove(tmp)
        except Exception as e:
            log(f"Không tải được {fname}: {e}")
            continue
        # Gộp: giữ nguyên chữ người dùng đã tự thêm, cộng thêm danh sách admin mới nhất
        before = CUSTOM_LIST_WORDS[key]
        merged = before | remote_words
        if merged != before:
            save_custom_list(key, sorted(merged))
            changed = True
            log(f"Đã cập nhật {info['label']}: +{len(merged) - len(before)} mục")
    os.replace(tmp_path, ver_path)
    if changed:
        log(f"Đã đồng bộ danh sách loại trừ lên phiên bản dữ liệu #{remote_ver}.")
    return changed


def sync_admin_lists_async(on_done=None):
    def worker():
        try:
            changed = sync_admin_lists()
        except Exception:
            changed = False
        if on_done:
            try:
                on_done(changed)
            except Exception:
                pass
    threading.Thread(target=worker, daemon=True).start()


# ── Kiểm tra bản EXE mới trên GitHub Releases ────────────────────────────────
def _version_tuple(v):
    v = (v or "").strip().lstrip("vV")
    parts = re.findall(r"\d+", v)
    return tuple(int(p) for p in parts) or (0,)


def check_for_update():
    """Trả về (có_bản_mới, phiên_bản_mới, url_trang_release) hoặc (False, None, None)."""
    req = urllib.request.Request(UPDATE_API_URL, headers={"User-Agent": "SLHTool", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.load(r)
    tag = data.get("tag_name") or ""
    url = data.get("html_url") or f"https://github.com/{GITHUB_REPO}/releases/latest"
    if _version_tuple(tag) > _version_tuple(APP_VERSION):
        return True, tag, url
    return False, tag, url


def check_for_update_async(on_result):
    def worker():
        try:
            result = check_for_update()
        except Exception as e:
            result = (False, None, str(e))
        try:
            on_result(*result)
        except Exception:
            pass
    threading.Thread(target=worker, daemon=True).start()


# ── Tải & giải nén gói HanLP (Python + torch + hanlp + model, đóng gói sẵn) ──
def download_hanlp_pack(progress=None):
    """Tải HANLP_PACK_URL, giải nén đè vào HANLP_RUNTIME_DIR. Gọi ở LUỒNG NỀN.

    progress(nhận_được, tổng, giai_đoạn) được gọi định kỳ; tổng có thể là 0 nếu
    server không trả Content-Length. Ném lỗi lên trên nếu thất bại.
    """
    progress = progress or (lambda a, b, s: None)
    os.makedirs(APP_DATA_DIR, exist_ok=True)
    zip_path = os.path.join(APP_DATA_DIR, "hanlp_pack_download.zip")
    req = urllib.request.Request(HANLP_PACK_URL, headers={"User-Agent": "SLHTool"})
    with urllib.request.urlopen(req, timeout=60) as r, open(zip_path, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        got = 0
        while True:
            chunk = r.read(1024 * 256)
            if not chunk:
                break
            f.write(chunk)
            got += len(chunk)
            progress(got, total, "download")
    progress(0, 0, "extract")
    tmp_extract = HANLP_RUNTIME_DIR + ".new"
    if os.path.exists(tmp_extract):
        shutil.rmtree(tmp_extract, ignore_errors=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(tmp_extract)
    os.remove(zip_path)
    # Gói có thể có 1 thư mục gốc bên trong (vd. hanlp_runtime/python.exe) — dò cho đúng
    root = tmp_extract
    entries = os.listdir(root)
    if len(entries) == 1 and os.path.isdir(os.path.join(root, entries[0])):
        root = os.path.join(root, entries[0])
    if os.path.exists(HANLP_RUNTIME_DIR):
        shutil.rmtree(HANLP_RUNTIME_DIR, ignore_errors=True)
    shutil.move(root, HANLP_RUNTIME_DIR)
    shutil.rmtree(tmp_extract, ignore_errors=True)
    progress(0, 0, "done")


def packaged_hanlp_python():
    """Đường dẫn python.exe trong gói HanLP đã tải, hoặc None nếu chưa có."""
    for name in ("python.exe", os.path.join("bin", "python3")):
        p = os.path.join(HANLP_RUNTIME_DIR, name)
        if os.path.exists(p):
            return p
    return None

# ═══════════════════════════════════════════════════════════

#  PHẦN 1 — DỮ LIỆU DÙNG CHUNG

# ═══════════════════════════════════════════════════════════

# ── Lọc ký tự (Chinese Line Checker) ──────────────────────

CATEGORY_DEFS = [

    ("han",          r'\u4E00-\u9FFF\u3400-\u4DBF\uF900-\uFAFF',

     "Chữ Hán (CJK + mở rộng)", True),

    ("cjk_punct",    r'\u3000-\u303F\uFF00-\uFFEF',

     "Dấu câu Trung / full-width （。！？…）", True),

    ("curly_quotes", r'\u2010-\u2027',

     "Ngoặc kép/nháy cong \u201c\u201d \u2018\u2019 và dấu … –", True),

    ("latin_letters",r'A-Za-z',

     "Chữ cái Latin (a-z, A-Z)", False),

    ("digits",       r'0-9',

     "Chữ số (0-9)", False),

    ("latin_punct",  r'!-/:-@\[-`{-~',

     "Dấu câu Latin (, ! ? ; : \" ( ) - * & % … trừ dấu chấm '.')", False),

    ("vietnamese",   r'\u00C0-\u024F\u1E00-\u1EFF',

     "Chữ có dấu tiếng Việt", False),

]

CATEGORY_PATTERNS = {

    key: re.compile(f'[{cc}]')

    for key, cc, label, default in CATEGORY_DEFS

}

ENDING_VALID_CHARS = set('\u3002\uff01\uff1f\u2026\u300d\u300f"\'\uff09\u2019\u201d')

# ── Lọc tên nhân vật ──────────────────────────────────────
HAN  = r'[\u4e00-\u9fff\u3400-\u4dbf]'
NAME = fr'({HAN}{{2,4}})'

NAME_PATTERNS = [
    NAME + r'(?:說道|笑道|問道|答道|冷道|輕聲道|嘆道|喝道|怒道|低聲道)',
    NAME + r'(?:說|道|問|答|笑|哭|喊|叫|嘆|怒|冷笑|苦笑|輕笑)',
    NAME + r'(?:點頭|搖頭|皺眉|蹙眉|抬頭|低頭|轉身|起身|站起|坐下)',
    NAME + r'(?:走過來|走過去|走進|走出|跑過來|跑過去|飛身)',
    NAME + r'(?:的眼|的臉|的手|的聲音|的身影|的身子|的嘴角)',
    r'[「『]' + NAME + r'[！？，」』]',
    r'叫(?:做|作)?' + NAME,
    r'名(?:叫|為|字)' + NAME,
    r'喚作' + NAME,
    r'稱(?:為|作)?' + NAME,
    r'(小' + HAN + r'{1,3})(?=[，。！？\s「」])',
    r'(大' + HAN + r'{1,3})(?=[，。！？\s「」])',
    r'(老' + HAN + r'{1,2})(?=[，。！？\s「」])',
    NAME + r'(?:姑娘|小姐|公子|大俠|先生|夫人|娘子)',
    NAME + r'(?:來了|走了|死了|回來|出現|消失)',
    NAME + r'看(?:了看|向|著)',
    NAME + r'想(?:了想|著|到)',
    NAME + r'(?:緩緩|慢慢|輕輕|靜靜|默默|悄悄)(?:說|道|走|看|想)',
    # ── Bản giản thể (truyện Trung Quốc đại lục) ──
    NAME + r'(?:说道|笑道|问道|答道|冷道|轻声道|叹道|喝道|怒道|低声道)',
    NAME + r'(?:说|问|答|哭|喊|叫|叹|怒|冷笑|苦笑|轻笑)',
    NAME + r'(?:点头|摇头|皱眉|蹙眉|抬头|低头|转身|起身|站起|坐下)',
    NAME + r'(?:走过来|走过去|走进|走出|跑过来|跑过去|飞身)',
    NAME + r'(?:的眼|的脸|的手|的声音|的身影|的身子|的嘴角)',
    r'["“『「]' + NAME + r'[！!？?，,。」』”"]',
    r'名(?:叫|为|字)' + NAME,
    r'唤作' + NAME,
    r'称(?:为|作)?' + NAME,
    NAME + r'(?:大侠|先生|夫人|娘子|姑娘|小姐|公子)',
    NAME + r'(?:来了|走了|死了|回来|出现|消失)',
    NAME + r'看(?:了看|向|着)',
    NAME + r'想(?:了想|着|到)',
    NAME + r'(?:缓缓|慢慢|轻轻|静静|默默|悄悄)(?:说|道|走|看|想)',
    # ── Thoại dẫn mở rộng (phồn) ──
    NAME + r'(?:罵道|斥道|吼道|喃喃道|朗聲道|厲聲道|沉聲道|柔聲道|顫聲道|啞聲道|尖聲道|驚呼道|冷冷道|淡淡道|幽幽道)',
    NAME + r'(?:笑著說|哭著說|大聲道|大喊道|大叫道|冷聲道|柔聲說|輕聲說)',
    NAME + r'心(?:想|道|念|中暗道|中暗想)',
    NAME + r'暗(?:道|想|忖|自)',

    # ── Hành động mở rộng ──
    NAME + r'(?:眨了眨眼|咬了咬牙|咬唇|握緊拳頭|擺了擺手|揮了揮手|伸出手|舉起手)',
    NAME + r'(?:點了點頭|搖了搖頭|嘆了口氣|深吸一口氣|愣住|愣了|呆住了|一怔|一愣|一笑)',
    NAME + r'(?:冷笑一聲|微微一笑|微微一怔|苦笑一聲|輕嘆一聲)',
    NAME + r'(?:站在|坐在|躺在|跪在|蹲在|倚在|靠在)',

    # ── Sở hữu cách mở rộng ──
    NAME + r'(?:的目光|的神色|的表情|的動作|的呼吸|的心|的頭|的腳|的背影|的語氣|的笑容)',

    # ── Được người khác nhìn/gọi ──
    r'只見' + NAME,
    r'卻見' + NAME,
    r'眼見' + NAME,
    r'望向' + NAME,
    r'望著' + NAME,
    r'盯著' + NAME,
    r'瞪著' + NAME,
    r'轉頭看向' + NAME,
    r'轉頭對' + NAME,

    # ── Giới thiệu thân phận ──
    NAME + r'(?:乃是|便是|正是|原是|即是)',
    r'(?:乃是|便是|正是|原是|即是)' + NAME,

    # ── Giản thể tương ứng ──
    NAME + r'(?:骂道|斥道|吼道|喃喃道|朗声道|厉声道|沉声道|柔声道|颤声道|哑声道|尖声道|惊呼道|冷冷道|淡淡道|幽幽道)',
    NAME + r'(?:笑着说|哭着说|大声道|大喊道|大叫道|冷声道)',
    NAME + r'心(?:想|道|念|中暗道|中暗想)',
    NAME + r'暗(?:道|想|忖|自)',
    NAME + r'(?:点了点头|摇了摇头|叹了口气|深吸一口气|愣住|呆住了|一怔|一愣|一笑)',
    NAME + r'(?:冷笑一声|微微一笑|微微一怔|苦笑一声|轻叹一声)',
    NAME + r'(?:站在|坐在|躺在|跪在|蹲在|倚在|靠在)',
    NAME + r'(?:的目光|的神色|的表情|的动作|的呼吸|的心|的头|的脚|的背影|的语气|的笑容)',
    r'只见' + NAME,
    r'却见' + NAME,
    r'望向' + NAME,
    r'望着' + NAME,
    r'盯着' + NAME,
    r'瞪着' + NAME,
    r'转头看向' + NAME,
    NAME + r'(?:乃是|便是|正是|原是|即是)',
]

NAME_BLACKLIST = {
    '本宮','公主','公子','太子','皇上','陛下','殿下','皇帝',
    '駙馬','娘娘','貴妃','皇后','皇兄','皇妹','皇弟','皇父',
    '王爺','郡主','世子','太后','皇太','皇族','太妃','王妃',
    '大王','國王','君王','天子','聖上','萬歲','皇子','皇孫',
    '掌櫃','將軍','大人','侍衛','奴才','婢女','丫鬟','丫环',
    '保鑣','刺客','惡霸','官員','侍從','宮女','太監','管家',
    '先生','夫子','師父','師兄','師姐','師弟','師妹','師尊',
    '長老','堂主','閣主','莊主','幫主','教主','盟主','族長',
    '父皇','母后','父親','母親','爹娘','夫人','老爺','少爺',
    '大人','小人','本人','他人','眾人','旁人','外人','故人',
    '親人','家人','主人','夫君','妻子','兒子','女兒','兄長',
    '金龍','天堂','大牢','寢宮','書房','長安','洛陽','京城',
    '皇宮','宮殿','府邸','山莊','江湖','天下','中原','武林',
    '忽然','突然','竟然','果然','居然','依然','仍然','雖然',
    '自然','當然','不然','既然','顯然','悄然','淡然','坦然',
    '今日','明日','昨日','此刻','當下','片刻','剎那','瞬間',
    '什麼','這樣','那樣','怎麼','為何','因為','所以','但是',
    '不過','然後','接著','隨後','於是','只是','只要','只有',
    '沒有','已經','還是','或者','如果','雖然','即使','哪怕',
    '原來','本來','畢竟','終於','總算','反正','其實','確實',
    '天地','萬物','蒼生','世間','人間','凡間','塵世','紅塵',
    '命運','緣分','因果','報應','天意','天命','天道','道理',
    # thời gian
    '早晨','傍晚','黃昏','深夜','半夜','清晨','凌晨','午後','黎明',
    '早晚','早已','早就','早知','早点','晚点','晚上','晚了',
    # vị trí/không gian dễ bị "屋/院/門/窗..." bắt vào mẫu 的X
    '屋內','屋外','門口','窗外','院子','街上','路上','山上','山下',
    '林中','林外','城中','城外','宮中','殿內','殿外','房中','房內',
    '床上','桌上','地上','眼前','身前','身後','身邊','手中','懷中',
    # đại từ/khiêm xưng cổ trang
    '彼此','大伙','咱','俺','汝','爾','吾','余','朕','寡人','哀家',
    '老衲','老朽','老身','老夫','老臣','微臣','臣妾','奴婢','小生',
    '晚輩','前輩','閣下','足下','在下','貧僧','貧道','老衲家',
    # cụm "小/大/老 + X" thông dụng dễ lọt lưới nhất
    '小心','小聲','小子','小鬼','小輩','小人','小僧','小道','小弟',
    '小妹','小心翼翼','小小','小事','小巷','小院','小屋','小路',
    '大概','大約','大聲','大力','大批','大量','大群','大片','大概是',
    '大意','大局','大事','大小','大約莫','大半',
    '老實','老是','老天','老天爺','老規矩','老樣子','老地方','老早',
    # phồn thể bổ sung song song giản thể đã có
    '沒事','算了','等等','走吧','來吧','明白','單身','備胎','直接',
    '轉頭','隨即','還有','等會','回頭','面前','眼前',
    '老婆','老公','老师','老板','导演','主持人','记者','经纪人','助理','秘书',
    '医生','护士','警察','司机','明星','粉丝','观众','网友','大神','大家',
    '什么','怎么','这样','那样','为何','因为','所以','但是','不过','然后',
    '接着','随后','于是','只是','只要','只有','没有','已经','还是','或者',
    '如果','虽然','即使','哪怕','原来','本来','毕竟','终于','总算','反正',
    '其实','确实','不知','知道','真的','可以','时候','现在','今天','明天',
    '昨天','我们','你们','他们','她们','咱们','自己','一个','这个','那个',
    '一下','一起','出来','起来','回去','过来','东西','地方','事情','样子',
    '感觉','心里','突然','忽然','竟然','果然','居然','依然','仍然','当然',
    '不然','既然','显然','悄然','淡然','坦然','小心','低声','轻声','微微',
    '缓缓','慢慢','轻轻','静静','默默','悄悄','立刻','马上','顿时','瞬间',
    '好的','好了','对了','没事','是啊','是呢','算了','等等','走吧','来吧',
    '明白','单身','备胎','直接','转头','随即','还有','等会','回头','面前',
}


# Họ phổ biến (giản + phồn) — tên bắt đầu bằng họ được ưu tiên giữ lại
CN_SURNAMES = set(
    '王李张張刘劉陈陳杨楊黄黃赵趙吴吳周徐孙孫马馬朱胡郭何林罗羅高郑鄭梁'
    '谢謝宋唐许許韩韓冯馮邓鄧曹彭曾肖萧蕭田董袁潘蒋蔣蔡余杜叶葉程苏蘇魏'
    '吕呂丁任沈姚卢盧姜崔钟鍾谭譚陆陸汪范金石廖贾賈夏韦韋方白邹鄒孟熊秦'
    '邱江尹薛段雷侯龙龍史陶黎贺賀顾顧毛郝龚龔邵万萬钱錢严嚴武戴莫孔汤湯'
    '温溫慕容欧歐阳陽司马上官南宫東东独獨孤宇文轩軒辕皇甫尉迟诸諸葛司徒'
)

# Ký tự "rác" hay dính vào đầu/cuối tên khi regex bắt nhầm
NAME_TRIM_LEAD = set('的了是不一住到那这這但却卻而已就被把跟和与與向对對')
NAME_TRIM_TRAIL = set(
    '的了地得着著是在就都也很再又被把给給让讓们們'
    '说說问問答喊叫哭叹嘆怒笑走转轉身来來看想听聽对對向'
)

TRAIL_FUNCTION_WORDS = [
    '微微','剛才','方才','這才','那才','才是','才好','才行','才對',
    '一般','這般','那般','幾般','半晌','片刻','一陣','一聲','一笑',
    '一驚','一怔','一愣','了了','的的','著著','起來','過來','下去',
    '不已','不止','不停','而已','罷了','便是','正是','原是',
]
_TRAIL_FUNCTION_WORDS_SORTED = sorted(TRAIL_FUNCTION_WORDS, key=len, reverse=True)

def _trim_trailing_phrase(word):
    """Cắt cụm hư từ ≥2 ký tự dính ở cuối, chỉ khi phần còn lại vẫn ≥2 ký tự."""
    for w in _TRAIL_FUNCTION_WORDS_SORTED:
        if word.endswith(w) and len(word) - len(w) >= 2:
            return word[:-len(w)]
    return word

# ── Danh sách tuỳ chỉnh: Blacklist / Họ / Ký tự cắt đầu-cuối ──────────
# Cho phép người dùng thêm trực tiếp từ EXE, không cần sửa code Python.

def _custom_list_app_dir():
    return APP_DATA_DIR

CUSTOM_LIST_DEFS = {
    "blacklist": {
        "file": "blacklist_tuychinh.txt",
        "target": NAME_BLACKLIST,
        "label": "🚫 Loại trừ (NAME_BLACKLIST)",
        "mode": "word",   # giữ nguyên cả cụm 2-4 chữ
    },
    "surname": {
        "file": "surnames_tuychinh.txt",
        "target": CN_SURNAMES,
        "label": "👤 Danh sách Họ (CN_SURNAMES)",
        "mode": "char",   # tách thành từng ký tự
    },
    "trim_lead": {
        "file": "trim_lead_tuychinh.txt",
        "target": NAME_TRIM_LEAD,
        "label": "✂ Ký tự cắt ĐẦU (NAME_TRIM_LEAD)",
        "mode": "char",
    },
    "trim_trail": {
        "file": "trim_trail_tuychinh.txt",
        "target": NAME_TRIM_TRAIL,
        "label": "✂ Ký tự cắt CUỐI (NAME_TRIM_TRAIL)",
        "mode": "char",
    },
}

CUSTOM_LIST_WORDS = {key: set() for key in CUSTOM_LIST_DEFS}

def _custom_list_path(key):
    return os.path.join(_custom_list_app_dir(), CUSTOM_LIST_DEFS[key]["file"])

def _custom_list_expand(key, raw_lines):
    """mode='word' → giữ nguyên cụm. mode='char' → tách thành từng ký tự."""
    mode = CUSTOM_LIST_DEFS[key]["mode"]
    out = set()
    for w in raw_lines:
        w = w.strip()
        if not w or w.startswith("#"):
            continue
        if mode == "char":
            out.update(list(w))
        else:
            out.add(w)
    return out

def load_custom_list(key):
    path = _custom_list_path(key)
    raw = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = f.readlines()
        except Exception:
            pass
    words = _custom_list_expand(key, raw)
    CUSTOM_LIST_WORDS[key] = words
    CUSTOM_LIST_DEFS[key]["target"].update(words)
    return words

def save_custom_list(key, raw_lines):
    words = _custom_list_expand(key, raw_lines)
    path = _custom_list_path(key)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(words)))
    target = CUSTOM_LIST_DEFS[key]["target"]
    target.difference_update(CUSTOM_LIST_WORDS[key])  # bỏ bản cũ
    target.update(words)                               # thêm bản mới
    CUSTOM_LIST_WORDS[key] = words

def load_all_custom_lists():
    for key in CUSTOM_LIST_DEFS:
        load_custom_list(key)

load_all_custom_lists()


def clean_name_candidate(word):
    while word and word[0] in NAME_TRIM_LEAD:
        word = word[1:]
    while word and word[-1] in NAME_TRIM_TRAIL:
        word = word[:-1]
    return word


# ═══════════════════════════════════════════════════════════
#  PHẦN 2 — LOGIC XỬ LÝ
# ═══════════════════════════════════════════════════════════

def check_strange_chars(line, enabled_keys):
    patterns = [CATEGORY_PATTERNS[k] for k in enabled_keys]
    found, seen = [], set()
    for ch in line:
        if ch == '.' or ch.isspace():
            continue
        if not any(p.match(ch) for p in patterns):
            if ch not in seen:
                seen.add(ch)
                found.append(ch)
    return found

def check_single_dot(line):
    for m in re.finditer(r'\.+', line):
        if len(m.group(0)) == 1:
            return True
    return False

def check_missing_end_punct(line):
    stripped = line.rstrip()
    if not stripped:
        return False
    if re.search(r'\.{2,}$', stripped):
        return False
    return stripped[-1] not in ENDING_VALID_CHARS

def check_double_space(line):
    return re.search(r'  +', line) is not None

def is_valid_name(word):
    if not (2 <= len(word) <= 4):
        return False
    if not re.match(fr'^{HAN}+$', word):
        return False
    if word in NAME_BLACKLIST:
        return False
    return True

def capitalize_first(text):
    return re.sub(
        r'(^|\n)([\-\[\("\'\s]*)([a-zà-ỹ])',
        lambda m: m.group(1) + m.group(2) + m.group(3).upper(),
        text
    )


# ── Chế độ HanLP (chính xác cao, cần Python + hanlp cài trên máy) ──
HANLP_WORKER_SRC = r'''
# Worker HanLP - chay boi SLHTool qua subprocess
import sys, re, json
from collections import Counter

def split_sentences(text):
    sentences = re.split(r'(?<=[。！？…\n])', text)
    out = []
    for s in sentences:
        s = s.strip()
        if len(s) < 3:
            continue
        if len(s) > 120:
            out.extend(x.strip() for x in re.split(r'(?<=[，；：])', s) if len(x.strip()) >= 3)
        else:
            out.append(s)
    return out

def ok(w):
    if not (2 <= len(w) <= 4):
        return False
    if re.search(r'[a-zA-Z0-9。，！？、…「」『』【】\s]', w):
        return False
    return True

def main():
    inp, outp = sys.argv[1], sys.argv[2]
    print("LOADING", flush=True)
    import hanlp
    tagger = hanlp.load(hanlp.pretrained.mtl.CLOSE_TOK_POS_NER_SRL_DEP_SDP_CON_ELECTRA_SMALL_ZH)
    print("LOADED", flush=True)
    with open(inp, encoding="utf-8") as f:
        text = f.read()
    sents = split_sentences(text)
    total = len(sents)
    print("TOTAL %d" % total, flush=True)
    counter = Counter()
    for i, sent in enumerate(sents, 1):
        if i % 500 == 0:
            print("PROGRESS %d %d" % (i, total), flush=True)
        try:
            result = tagger(sent)
        except Exception:
            continue
        if "tok/fine" in result and "pos/ctb" in result:
            for w, t in zip(result["tok/fine"], result["pos/ctb"]):
                if t == "NR" and ok(w):
                    counter[w] += 1
        if "ner/msra" in result:
            for ent in result["ner/msra"]:
                if str(ent[1]).upper() in ("NR", "PERSON", "PER") and ok(ent[0]):
                    counter[ent[0]] += 1
    with open(outp, "w", encoding="utf-8") as f:
        json.dump(dict(counter), f, ensure_ascii=False)
    print("DONE", flush=True)

main()
'''


class HanlpMissingDialog(tk.Toplevel):
    """Hiện khi máy chưa có Python + HanLP: cho tải gói cài sẵn (không cần cài Python),
    hoặc hướng dẫn tự cài Python + `pip install hanlp` nếu người dùng muốn tự làm."""

    def __init__(self, parent, on_ready=None):
        super().__init__(parent)
        self.on_ready = on_ready
        self.title("Thiếu HanLP")
        self.geometry("520x300")
        self.resizable(False, False)
        self.transient(parent)
        frm = ttk.Frame(self, padding=16)
        frm.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frm, text="Máy này chưa có Python + thư viện HanLP.", font=FONT_BOLD).pack(anchor="w")
        ttk.Label(frm, text="Cách nhanh nhất: tải gói HanLP đóng gói sẵn (~vài trăm MB, tải 1 lần).",
                  wraplength=470, justify="left").pack(anchor="w", pady=(8, 4))
        self.pb = ttk.Progressbar(frm, mode="determinate", maximum=100)
        self.pb.pack(fill=tk.X, pady=(4, 4))
        self.var_status = tk.StringVar(value="")
        ttk.Label(frm, textvariable=self.var_status, style="Muted.TLabel").pack(anchor="w")
        self.btn_dl = ttk.Button(frm, text="⬇ Tải gói HanLP", style="Accent.TButton", command=self._start_download)
        self.btn_dl.pack(anchor="w", pady=(10, 14))
        ttk.Separator(frm).pack(fill=tk.X, pady=(0, 10))
        ttk.Label(frm, text="Hoặc tự cài: cài Python từ python.org rồi mở CMD chạy  pip install hanlp",
                  wraplength=470, justify="left", style="Muted.TLabel").pack(anchor="w")
        ttk.Button(frm, text="Đóng", command=self.destroy).pack(anchor="e", pady=(14, 0))

    def _start_download(self):
        self.btn_dl.config(state="disabled")
        self.var_status.set("Đang chuẩn bị tải...")

        def progress(got, total, stage):
            def apply():
                if stage == "download" and total:
                    self.pb.config(mode="determinate", maximum=total)
                    self.pb["value"] = got
                    self.var_status.set(f"Đang tải: {got / 1_048_576:.0f} / {total / 1_048_576:.0f} MB")
                elif stage == "download":
                    self.pb.config(mode="indeterminate")
                    self.var_status.set(f"Đang tải: {got / 1_048_576:.0f} MB")
                elif stage == "extract":
                    self.pb.config(mode="indeterminate")
                    self.pb.start(15)
                    self.var_status.set("Đang giải nén...")
                elif stage == "done":
                    self.pb.stop()
                    self.pb.config(mode="determinate")
                    self.pb["value"] = self.pb["maximum"]
                    self.var_status.set("✔ Xong! Bấm lại 'Lọc bằng HanLP' để dùng.")
            try:
                self.after(0, apply)
            except (tk.TclError, RuntimeError):
                pass

        def worker():
            try:
                download_hanlp_pack(progress=progress)
                ok, err = True, None
            except Exception as e:                       # noqa: BLE001
                ok, err = False, str(e)

            def finish():
                if ok:
                    if self.on_ready:
                        self.on_ready()
                else:
                    self.var_status.set(f"Lỗi: {err}")
                    self.btn_dl.config(state="normal")
            try:
                self.after(0, finish)
            except (tk.TclError, RuntimeError):
                pass
        threading.Thread(target=worker, daemon=True).start()


def find_python_with_hanlp():
    """Ưu tiên gói HanLP đã tải sẵn (APP_DATA_DIR/hanlp_runtime); nếu chưa có thì
    tìm Python cài sẵn trên máy có thư viện hanlp."""
    packaged = packaged_hanlp_python()
    if packaged:
        return packaged
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    for cand in ("python", "python3", "py"):
        exe = shutil.which(cand)
        if not exe:
            continue
        try:
            r = subprocess.run(
                [exe, "-c", "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('hanlp') else 1)"],
                capture_output=True, timeout=30, creationflags=flags,
            )
            if r.returncode == 0:
                return exe
        except Exception:
            pass
    return None

# ═══════════════════════════════════════════════════════════

#  PHẦN 3 — DIALOG TÌM / THAY THẾ

# ═══════════════════════════════════════════════════════════

class FindReplaceDialog(tk.Toplevel):

    def __init__(self, master, text_widget):

        super().__init__(master)

        self.text_widget = text_widget

        self.title("Tìm / Thay thế  (Ctrl+F)")

        self.geometry("440x145")

        self.resizable(False, False)

        frm = ttk.Frame(self, padding=10)

        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="Tìm:").grid(row=0, column=0, sticky=tk.W, pady=3)

        self.find_var = tk.StringVar()

        fe = ttk.Entry(frm, textvariable=self.find_var, width=36)

        fe.grid(row=0, column=1, columnspan=3, sticky=tk.W, pady=3)

        fe.focus_set()

        ttk.Label(frm, text="Thay bằng:").grid(row=1, column=0, sticky=tk.W, pady=3)

        self.replace_var = tk.StringVar()

        ttk.Entry(frm, textvariable=self.replace_var, width=36).grid(

            row=1, column=1, columnspan=3, sticky=tk.W, pady=3)

        ttk.Button(frm, text="Tìm tiếp",    command=self.find_next).grid(row=2, column=0, pady=8)

        ttk.Button(frm, text="Thay",         command=self.replace_one).grid(row=2, column=1, pady=8)

        ttk.Button(frm, text="Thay tất cả", command=self.replace_all).grid(row=2, column=2, pady=8)

        ttk.Button(frm, text="Đóng",         command=self.destroy).grid(row=2, column=3, pady=8)

        self.text_widget.tag_configure("find_match", background="#ffe066")

        self.bind("<Return>", lambda e: self.find_next())

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):

        self.text_widget.tag_remove("find_match", "1.0", tk.END)

        self.destroy()

    def find_next(self):

        q = self.find_var.get()

        if not q: return

        self.text_widget.tag_remove("find_match", "1.0", tk.END)

        start = self.text_widget.index(tk.INSERT)

        pos = self.text_widget.search(q, start, stopindex=tk.END)

        if not pos:

            pos = self.text_widget.search(q, "1.0", stopindex=tk.END)

            if not pos:

                messagebox.showinfo("Không tìm thấy", f"Không tìm thấy: {q}", parent=self)

                return

        end = f"{pos}+{len(q)}c"

        self.text_widget.tag_add("find_match", pos, end)

        self.text_widget.mark_set(tk.INSERT, end)

        self.text_widget.see(pos)

    def replace_one(self):

        sel = self.text_widget.tag_ranges("find_match")

        if sel:

            self.text_widget.delete(sel[0], sel[1])

            self.text_widget.insert(sel[0], self.replace_var.get())

        self.find_next()

    def replace_all(self):

        q = self.find_var.get()

        r = self.replace_var.get()

        if not q: return

        content = self.text_widget.get("1.0", "end-1c")

        count = content.count(q)

        if count == 0:

            messagebox.showinfo("Không tìm thấy", f"Không tìm thấy: {q}", parent=self)

            return

        self.text_widget.delete("1.0", tk.END)

        self.text_widget.insert("1.0", content.replace(q, r))

        messagebox.showinfo("Đã thay thế", f"Đã thay {count} chỗ.", parent=self)


# ═══════════════════════════════════════════════════════════

#  PHẦN 5 — TAB 2: LỌC TÊN NHÂN VẬT

# ═══════════════════════════════════════════════════════════

class TabNames(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.translate_tab = None      # được App gắn vào: tab Dịch Trung → Việt (engine + bộ tên)
        self._build()

    

    def paste_text(self):
        """Dán nội dung từ clipboard vào input_text."""
        try:
            clip = self.clipboard_get()
        except tk.TclError:
            messagebox.showinfo("Clipboard trống", "Không có nội dung text.")
            return

        self.input_text.delete("1.0", tk.END)
        self.input_text.insert("1.0", clip)
        self.status_var.set("Đã dán văn bản → nhấn 'Lọc bằng HanLP'.")

    def open_file(self):

        """Mở file .txt chứa văn bản tiếng Trung."""

        path = filedialog.askopenfilename(

            filetypes=[("Text files","*.txt"),("Tất cả","*.*")]

        )

        if not path: 

            return

        for enc in ["utf-8","utf-8-sig","gb18030","gbk"]:

            try:

                with open(path, "r", encoding=enc, errors="strict") as f:

                    content = f.read()

                break

            except Exception:

                content = None

        if not content:

            with open(path, "r", encoding="utf-8", errors="replace") as f:

                content = f.read()

        self.input_text.delete("1.0", tk.END)

        self.input_text.insert("1.0", content)

        self.status_var.set(f"Đã mở: {os.path.basename(path)} → nhấn 'Lọc bằng HanLP'.")


    def _build(self):

        # Toolbar

        tb = ttk.Frame(self)

        tb.pack(side=tk.TOP, fill=tk.X, padx=6, pady=4)

        ttk.Button(tb, text="📋 Dán văn bản", command=self.paste_text).pack(side=tk.LEFT)

        ttk.Button(tb, text="📂 Mở file .txt", command=self.open_file).pack(side=tk.LEFT, padx=(4,0))

        

        # ── Ngưỡng tần suất: giờ người dùng tự chọn, không cố định 2 nữa ──

        freq_fr = ttk.Frame(tb)

        freq_fr.pack(side=tk.LEFT, padx=(12, 0))

        ttk.Label(freq_fr, text="Tần suất tối thiểu:").pack(side=tk.LEFT)

        self.min_freq_var = tk.IntVar(value=5)

        ttk.Spinbox(freq_fr, from_=1, to=999, width=5,

                    textvariable=self.min_freq_var).pack(side=tk.LEFT, padx=(4, 0))

        

        self.hanlp_btn = ttk.Button(tb, text="🎯 Lọc bằng HanLP", style="Accent.TButton", command=self.run_hanlp)
        self.hanlp_btn.pack(side=tk.LEFT, padx=(12,0))
        self.translate_btn = ttk.Button(tb, text="🌐 Dịch name", style="Accent.TButton",
                                        command=self.open_name_translate, state="disabled")
        self.translate_btn.pack(side=tk.LEFT, padx=(4,0))

        ttk.Button(tb, text="💾 Sao chép kết quả", command=self.copy_result).pack(side=tk.LEFT, padx=(4,0))

        ttk.Button(tb, text="💾 Lưu kết quả", command=self.save_result).pack(side=tk.LEFT, padx=(4,0))

        ttk.Button(tb, text="🗂 Quản lý danh sách", command=self.open_blacklist_manager).pack(side=tk.LEFT, padx=(4,0))

        self.status_var = tk.StringVar(value="Dán văn bản tiếng Trung → 'Lọc bằng HanLP' → 'Dịch name' → thêm vào bộ tên")
        ttk.Label(self, textvariable=self.status_var, style="Muted.TLabel").pack(side=tk.TOP, fill=tk.X, padx=10)

        self._hanlp_running = False

        

        # PanedWindow ngang

        pw = ttk.PanedWindow(self, orient=tk.HORIZONTAL)

        pw.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0,6))

        # Input

        left = ttk.LabelFrame(pw, text="Văn bản đầu vào (tiếng Trung)")

        pw.add(left, weight=3)

        self.input_text = tk.Text(left, wrap=tk.WORD, font=FONT_TEXT, undo=True)

        self.input_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        isb = ttk.Scrollbar(left, orient=tk.VERTICAL, command=self.input_text.yview)

        self.input_text.configure(yscrollcommand=isb.set)

        # Output: bảng tên

        right = ttk.Frame(pw)

        pw.add(right, weight=2)

        rf = ttk.LabelFrame(right, text="Tên tìm được (sắp xếp theo tần suất)")

        rf.pack(fill=tk.BOTH, expand=True)

        cols = ("name","freq","group")

        self.name_tree = ttk.Treeview(rf, columns=cols, show="headings", height=30)

        self.name_tree.heading("name",  text="Tên")

        self.name_tree.heading("freq",  text="Số lần")

        self.name_tree.heading("group", text="Phân loại")

        self.name_tree.column("name",  width=120, anchor=tk.CENTER)

        self.name_tree.column("freq",  width=80,  anchor=tk.CENTER)

        self.name_tree.column("group", width=160)

        self.name_tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        # Màu nhóm

        self.name_tree.tag_configure("main",  background="#d4edda")  # xanh lá nhạt

        self.name_tree.tag_configure("side",  background="#fff3cd")  # vàng nhạt

        self.name_tree.tag_configure("minor", background="#f8f9fa")  # trắng xám

        nsb = ttk.Scrollbar(rf, orient=tk.VERTICAL, command=self.name_tree.yview)

        nsb.pack(side=tk.LEFT, fill=tk.Y)

        self.name_tree.configure(yscrollcommand=nsb.set)

        self.name_tree.bind("<Button-3>", self._show_name_context_menu)

    def _populate_results(self, results, source_note=""):

        for item in self.name_tree.get_children():

            self.name_tree.delete(item)

        min_freq = self.min_freq_var.get()

        for name, freq in results:

            if freq >= max(20, min_freq):

                threshold = max(20, min_freq)

                group, tag = f"Nhân vật chính (≥{threshold})", "main"

            elif freq >= min_freq:

                group, tag = f"Nhân vật phụ ({min_freq}-19)", "side"

            else:

                group, tag = f"Xuất hiện ít (<{min_freq})", "minor"

            self.name_tree.insert("", tk.END, values=(name, f"{freq} lần", group), tags=(tag,))

        self.status_var.set(f"Tìm được {len(results)} tên  |  {source_note}")
        self.translate_btn.config(state="normal" if results else "disabled")

    def open_name_translate(self):
        """Nút 'Dịch name': mở cửa sổ tự dịch các tên đã lọc rồi thêm vào bộ tên (Quản lý Name).
        Có dòng đang chọn thì chỉ dịch các dòng đó; không chọn thì dịch toàn bộ kết quả."""
        tr = self.translate_tab
        if tr is None:
            messagebox.showerror("Lỗi", "Chưa kết nối với tab Dịch Trung → Việt.", parent=self)
            return
        chosen = self.name_tree.selection()
        items = chosen if chosen else self.name_tree.get_children()
        if not items:
            messagebox.showinfo("Chưa có tên", "Hãy dán văn bản rồi bấm 'Lọc bằng HanLP' trước.", parent=self)
            return
        rows = []
        for it in items:
            name, freq, group = (str(v) for v in self.name_tree.item(it, "values"))
            rows.append((name, freq, group))
        note = (f"{len(rows)} tên đang chọn trong kết quả lọc" if chosen
                else f"toàn bộ {len(rows)} tên trong kết quả lọc")
        NameTranslateDialog(self, tr, rows, note)

    def _show_name_context_menu(self, event):
        """Chuột phải lên 1 dòng kết quả → chọn thêm vào 1 trong 4 danh sách."""
        item = self.name_tree.identify_row(event.y)
        if not item:
            return
        self.name_tree.selection_set(item)
        name = self.name_tree.item(item, "values")[0]
        first_ch = name[0] if name else ""
        last_ch = name[-1] if name else ""

        menu = tk.Menu(self.name_tree, tearoff=0)
        menu.add_command(
            label=f"🚫 Thêm cả '{name}' vào Danh sách loại trừ",
            command=lambda: self._quick_add_to_list("blacklist", name, item),
        )
        if first_ch:
            menu.add_command(
                label=f"👤 Thêm '{first_ch}' vào Danh sách Họ (CN_SURNAMES)",
                command=lambda: self._quick_add_to_list("surname", first_ch),
            )
            menu.add_command(
                label=f"✂ Thêm '{first_ch}' vào Ký tự cắt ĐẦU (NAME_TRIM_LEAD)",
                command=lambda: self._quick_add_to_list("trim_lead", first_ch),
            )
        if last_ch:
            menu.add_command(
                label=f"✂ Thêm '{last_ch}' vào Ký tự cắt CUỐI (NAME_TRIM_TRAIL)",
                command=lambda: self._quick_add_to_list("trim_trail", last_ch),
            )
        menu.tk_popup(event.x_root, event.y_root)

    def _quick_add_to_list(self, key, value, item=None):
        current = set(CUSTOM_LIST_WORDS[key])
        current.update(_custom_list_expand(key, [value]))
        try:
            save_custom_list(key, current)
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không lưu được: {e}", parent=self)
            return
        label = CUSTOM_LIST_DEFS[key]["label"]
        self.status_var.set(f"Đã thêm '{value}' vào {label}.")
        if key == "blacklist" and item is not None:
            self.name_tree.delete(item)
        else:
            self._remove_blacklisted_from_results()

    def _remove_blacklisted_from_results(self):
        removed = 0
        for item in list(self.name_tree.get_children()):
            name = self.name_tree.item(item, "values")[0]
            if name in NAME_BLACKLIST:
                self.name_tree.delete(item)
                removed += 1
        if removed:
            self.status_var.set(f"Đã loại bỏ {removed} tên khỏi kết quả theo danh sách loại trừ mới.")

    def open_blacklist_manager(self):
        """Cửa sổ quản lý 4 danh sách tuỳ chỉnh — đọc/ghi ra file .txt cạnh EXE."""
        win = tk.Toplevel(self)
        win.title("Quản lý danh sách tuỳ chỉnh")
        win.geometry("580x580")

        ttk.Label(
            win,
            text=("Quản lý 4 danh sách dùng để lọc tên nhân vật.\n"
                  "Sửa xong bấm 'Lưu' ở từng tab để áp dụng ngay — không cần build lại EXE."),
            foreground="#555", wraplength=540, justify="left",
        ).pack(padx=10, pady=(10, 4), anchor="w")

        sync_row = ttk.Frame(win)
        sync_row.pack(fill=tk.X, padx=10)
        sync_status = tk.StringVar(value=f"Nguồn cập nhật: github.com/{DATA_REPO}")
        ttk.Label(sync_row, textvariable=sync_status, style="Muted.TLabel").pack(side=tk.LEFT)

        nb = ttk.Notebook(win)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=(6, 10))

        all_reload_fns = []
        for key, info in CUSTOM_LIST_DEFS.items():
            tab = ttk.Frame(nb, padding=8)
            nb.add(tab, text=info["label"])

            note = "Mỗi dòng 1 ký tự." if info["mode"] == "char" else "Mỗi dòng 1 cụm từ (2-4 chữ)."
            ttk.Label(tab, text=note, foreground="#888").pack(anchor="w")

            txt_fr = ttk.Frame(tab)
            txt_fr.pack(fill=tk.BOTH, expand=True, pady=(4, 4))
            txt = tk.Text(txt_fr, wrap=tk.NONE, font=FONT_TEXT)
            txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            sb = ttk.Scrollbar(txt_fr, orient=tk.VERTICAL, command=txt.yview)
            sb.pack(side=tk.LEFT, fill=tk.Y)
            txt.configure(yscrollcommand=sb.set)
            txt.insert("1.0", "\n".join(sorted(CUSTOM_LIST_WORDS[key])))

            add_fr = ttk.Frame(tab)
            add_fr.pack(fill=tk.X, pady=(0, 4))
            ttk.Label(add_fr, text="Thêm nhanh:").pack(side=tk.LEFT)
            add_var = tk.StringVar()
            add_entry = ttk.Entry(add_fr, textvariable=add_var)
            add_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 4))

            def make_do_add(t=txt, v=add_var):
                def do_add():
                    w = v.get().strip()
                    if not w:
                        return
                    current = t.get("1.0", "end-1c").strip()
                    t.insert(tk.END, ("\n" if current else "") + w)
                    v.set("")
                return do_add

            do_add = make_do_add()
            ttk.Button(add_fr, text="➕", width=3, command=do_add).pack(side=tk.LEFT)
            add_entry.bind("<Return>", lambda e, f=do_add: f())

            ttk.Label(tab, text=f"File: {_custom_list_path(key)}",
                      foreground="#888", wraplength=540).pack(anchor="w")

            btn_fr = ttk.Frame(tab)
            btn_fr.pack(fill=tk.X, pady=(6, 0))

            def make_do_save(k=key, t=txt):
                def do_save():
                    lines = t.get("1.0", "end-1c").split("\n")
                    try:
                        save_custom_list(k, lines)
                    except Exception as e:
                        messagebox.showerror("Lỗi", f"Không lưu được file:\n{e}", parent=win)
                        return
                    messagebox.showinfo(
                        "Đã lưu",
                        f"Đã lưu {len(CUSTOM_LIST_WORDS[k])} mục vào:\n{_custom_list_path(k)}",
                        parent=win,
                    )
                    self._remove_blacklisted_from_results()
                return do_save

            def make_do_reload(k=key, t=txt):
                def do_reload():
                    load_custom_list(k)
                    t.delete("1.0", tk.END)
                    t.insert("1.0", "\n".join(sorted(CUSTOM_LIST_WORDS[k])))
                return do_reload

            ttk.Button(btn_fr, text="💾 Lưu", command=make_do_save()).pack(side=tk.LEFT)
            ttk.Button(btn_fr, text="🔄 Nạp lại từ file", command=make_do_reload()).pack(side=tk.LEFT, padx=6)
            all_reload_fns.append(make_do_reload())

        def do_sync():
            sync_btn.config(state="disabled")
            sync_status.set("Đang kiểm tra bản cập nhật...")

            def on_done(changed):
                def apply():
                    sync_btn.config(state="normal")
                    for fn in all_reload_fns:
                        fn()
                    sync_status.set("Đã có bản mới nhất." if changed else "Danh sách đã là bản mới nhất.")
                    if changed:
                        self._remove_blacklisted_from_results()
                win.after(0, apply)
            sync_admin_lists_async(on_done)

        sync_btn = ttk.Button(sync_row, text="🔄 Đồng bộ từ máy chủ", style="Accent.TButton", command=do_sync)
        sync_btn.pack(side=tk.RIGHT)

        ttk.Button(win, text="Đóng", command=win.destroy).pack(pady=(0, 10))

    # ── Chế độ HanLP (gọi Python cài trên máy) ────────────
    def run_hanlp(self):
        text = self.input_text.get("1.0", "end-1c").strip()
        if not text:
            messagebox.showinfo("Trống", "Vui lòng dán văn bản vào ô bên trái trước.")
            return
        if self._hanlp_running:
            return
        self._hanlp_running = True
        self.hanlp_btn.config(state="disabled")
        min_freq = self.min_freq_var.get()
        Thread(target=self._hanlp_worker, args=(text, min_freq), daemon=True).start()

    def _hanlp_status(self, msg):
        self.after(0, lambda: self.status_var.set(msg))

    def _hanlp_finish(self):
        self._hanlp_running = False
        self.after(0, lambda: self.hanlp_btn.config(state="normal"))

    def _hanlp_worker(self, text, min_freq):
        try:
            self._hanlp_status("Đang tìm Python + HanLP trên máy...")
            py = find_python_with_hanlp()
            if not py:
                self._hanlp_status("Chưa có HanLP — có thể tải gói cài sẵn.")
                self.after(0, lambda: HanlpMissingDialog(
                    self, on_ready=lambda: self._hanlp_status("Đã sẵn sàng — bấm 'Lọc bằng HanLP' để tiếp tục.")))
                return

            tmpdir = tempfile.mkdtemp(prefix="vbt_hanlp_")
            inp = os.path.join(tmpdir, "input.txt")
            outp = os.path.join(tmpdir, "out.json")
            wk = os.path.join(tmpdir, "worker.py")
            with open(inp, "w", encoding="utf-8") as f:
                f.write(text)
            with open(wk, "w", encoding="utf-8") as f:
                f.write(HANLP_WORKER_SRC)

            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            env = dict(os.environ, PYTHONIOENCODING="utf-8")
            if py == packaged_hanlp_python():
                # Dùng model đã đóng gói sẵn trong gói HanLP — khỏi tải lại, chạy offline được
                env["HANLP_HOME"] = os.path.join(HANLP_RUNTIME_DIR, "hanlp_home")
            proc = subprocess.Popen(
                [py, wk, inp, outp],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                creationflags=flags, env=env,
            )
            total = 0
            for line in proc.stdout:
                line = line.strip()
                if line == "LOADING":
                    self._hanlp_status("Đang nạp model HanLP (lần đầu sẽ tải model, có thể mất vài phút)...")
                elif line == "LOADED":
                    self._hanlp_status("Model đã nạp, bắt đầu phân tích...")
                elif line.startswith("TOTAL "):
                    total = int(line.split()[1])
                    self._hanlp_status(f"HanLP: 0/{total} câu...")
                elif line.startswith("PROGRESS "):
                    _, i, t = line.split()
                    self._hanlp_status(f"HanLP: {i}/{t} câu...")
            proc.wait()

            if proc.returncode != 0 or not os.path.exists(outp):
                self._hanlp_status("HanLP chạy lỗi — xem lại cài đặt (pip install hanlp).")
                return

            import json as _json
            with open(outp, encoding="utf-8") as f:
                raw = _json.load(f)

            # Lọc lại phía app: blacklist, cắt ký tự thừa, ngưỡng tần suất
            counter = Counter()
            for w, fr in raw.items():
                w2 = clean_name_candidate(w)
                if is_valid_name(w2):
                    counter[w2] += fr
            results = sorted(
                [(n, fr) for n, fr in counter.items() if fr >= min_freq],
                key=lambda x: (-x[1], x[0]),
            )
            self.after(0, lambda: self._populate_results(results, f"HanLP  |  ngưỡng: ≥{min_freq} lần"))
            try:
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass
        except Exception as e:
            self._hanlp_status(f"Lỗi HanLP: {e}")
        finally:
            self._hanlp_finish()

    def copy_result(self):
        items = self.name_tree.get_children()
        if not items:
            messagebox.showinfo("Trống", "Chưa có kết quả. Nhấn 'Lọc bằng HanLP' trước.")
            return
        names = [self.name_tree.item(item, "values")[0] for item in items]
        self.clipboard_clear()
        self.clipboard_append("\n".join(names))
        messagebox.showinfo("Đã sao chép", f"Đã sao chép {len(names)} tên (chỉ tên) vào clipboard.")

    def save_result(self):
        items = self.name_tree.get_children()
        if not items:
            messagebox.showinfo("Trống", "Chưa có kết quả.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files","*.txt"),("CSV","*.csv")],
            initialfile="ten_nhan_vat.txt"
        )
        if not path: return
        lines = []
        for item in items:
            name, freq, group = self.name_tree.item(item, "values")
            lines.append(f"{name}    [{freq}]  # {group}")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        messagebox.showinfo("Đã lưu", f"Đã lưu tại:\n{path}")

# ═══════════════════════════════════════════════════════════

#  PHẦN 7 — TAB 4: TẠO & GỘP EPUB

# ═══════════════════════════════════════════════════════════

import zipfile

import uuid

import xml.etree.ElementTree as ET

from datetime import date

from threading import Thread

def _esc_xml(s):

    return (str(s)

        .replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

        .replace('"',"&quot;").replace("'","&apos;"))

def _uid():

    return uuid.uuid4().hex

def _decode_entities(s):

    s = str(s)

    s = re.sub(r'&amp;',  '&', s)

    s = re.sub(r'&lt;',   '<', s)

    s = re.sub(r'&gt;',   '>', s)

    s = re.sub(r'&quot;', '"', s)

    s = re.sub(r'&apos;', "'", s)

    s = re.sub(r'&#x([0-9a-fA-F]+);', lambda m: chr(int(m.group(1),16)), s)

    s = re.sub(r'&#(\d+);',           lambda m: chr(int(m.group(1))),    s)

    return s

# ── Đọc nội dung .docx bằng mammoth ──────────────────────

def _read_docx_html(docx_path):

    """Dùng mammoth để chuyển .docx → HTML, giữ đúng heading/bold/italic."""

    import mammoth

    with open(docx_path, 'rb') as f:

        result = mammoth.convert_to_html(f)

    return result.value

def _split_chapters(html):

    matches = list(re.finditer(r'<h1[^>]*>([\s\S]*?)</h1>', html, re.IGNORECASE))

    if not matches:

        return [{'title': 'Nội dung', 'data': html}]

    chapters = []

    for i, m in enumerate(matches):

        title = _decode_entities(re.sub(r'<[^>]+>','', m.group(1)).strip())

        start = m.start()

        end   = matches[i+1].start() if i+1 < len(matches) else len(html)

        chapters.append({'title': title, 'data': html[start:end]})

    return chapters

def _image_bytes_to_webp(data, quality=80):

    """Nén ảnh (bytes) sang WebP. Trả về bytes WebP, hoặc None nếu không chuyển được."""

    try:

        from PIL import Image

        import io

        img = Image.open(io.BytesIO(data))

        if img.mode not in ("RGB", "RGBA"):

            img = img.convert("RGB")

        buf = io.BytesIO()

        img.save(buf, "WEBP", quality=quality, method=6)

        return buf.getvalue()

    except Exception:

        return None

def _fmt_kb(n_bytes):

    if n_bytes >= 1024 * 1024:

        return f"{n_bytes / 1024 / 1024:.2f}MB"

    return f"{n_bytes / 1024:.1f}KB"

# ── Build EPUB buffer ──────────────────────────────────────

def _build_epub(title, author, description, cover_path, chapters, out_path, log=None):

    book_id = _uid()

    now     = date.today().isoformat()

    ext_map = {'.jpg':'image/jpeg','.jpeg':'image/jpeg',

               '.png':'image/png','.webp':'image/webp','.gif':'image/gif'}

    cover_ext  = None

    cover_mime = None

    cover_data = None

    if cover_path and os.path.exists(cover_path):

        cover_ext  = os.path.splitext(cover_path)[1].lower()

        cover_mime = ext_map.get(cover_ext, 'image/jpeg')

        with open(cover_path,'rb') as f:

            cover_data = f.read()

        # Tự nén ảnh bìa sang WebP để EPUB nhẹ hơn

        if cover_ext != '.webp':

            webp_data = _image_bytes_to_webp(cover_data)

            if webp_data:

                if log:

                    log(f"🖼 Ảnh bìa: {_fmt_kb(len(cover_data))} ({cover_ext}) → WebP {_fmt_kb(len(webp_data))}")

                cover_data = webp_data

                cover_ext  = '.webp'

                cover_mime = 'image/webp'

            elif log:

                log("⚠ Không nén được ảnh bìa sang WebP (cần: pip install pillow) — giữ định dạng gốc.")

    with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as z:

        # mimetype — phải STORE, phải đầu tiên

        z.writestr(zipfile.ZipInfo('mimetype'), 'application/epub+zip',

                   compress_type=zipfile.ZIP_STORED)

        z.writestr('META-INF/container.xml',

            '<?xml version="1.0" encoding="UTF-8"?>\n'

            '<container version="1.0" xmlns="urn:oasis:schemas:container">\n'

            '  <rootfiles>\n'

            '    <rootfile full-path="OEBPS/content.opf"'

            ' media-type="application/oebps-package+xml"/>\n'

            '  </rootfiles>\n'

            '</container>')

        # Chapters

        ch_files = []

        for i, ch in enumerate(chapters):

            fname = f'chapter{i+1:03d}.xhtml'

            xhtml = (

                '<?xml version="1.0" encoding="UTF-8"?>\n'

                '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"'

                ' "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">\n'

                '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="vi">\n'

                f'<head><meta charset="UTF-8"/><title>{_esc_xml(ch["title"])}</title>\n'

                '<style>body{font-family:serif;font-size:1em;line-height:1.6;margin:1em 1.5em;}'

                'p{margin:0.5em 0;}h1,h2{font-weight:bold;}</style>\n'

                f'</head>\n<body>{ch["data"]}</body>\n</html>'

            )

            z.writestr(f'OEBPS/{fname}', xhtml)

            ch_files.append({'id': f'ch{i+1}', 'href': fname, 'title': ch['title']})

        z.writestr('OEBPS/style.css', 'body{font-family:serif;line-height:1.6;}')

        # Cover

        cover_manifest = ''

        cover_spine    = ''

        cover_meta     = ''

        if cover_data:

            z.writestr(f'OEBPS/images/cover{cover_ext}', cover_data)

            z.writestr('OEBPS/cover.xhtml',

                '<?xml version="1.0" encoding="UTF-8"?>\n'

                '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"'

                ' "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">\n'

                '<html xmlns="http://www.w3.org/1999/xhtml">\n'

                '<head><title>Cover</title>'

                '<style>body{margin:0;padding:0;text-align:center;}'

                'img{max-width:100%;max-height:100%;}</style></head>\n'

                f'<body><img src="images/cover{cover_ext}" alt="Cover"/></body>\n</html>')

            cover_manifest = (

                f'    <item id="cover-image" href="images/cover{cover_ext}"'

                f' media-type="{cover_mime}" properties="cover-image"/>\n'

                '    <item id="cover-page" href="cover.xhtml"'

                ' media-type="application/xhtml+xml"/>')

            cover_spine = '    <itemref idref="cover-page" linear="no"/>'

            cover_meta  = '    <meta name="cover" content="cover-image"/>'

        manifest_items = '\n'.join(

            f'    <item id="{c["id"]}" href="{c["href"]}"'

            f' media-type="application/xhtml+xml"/>' for c in ch_files)

        spine_items = '\n'.join(

            f'    <itemref idref="{c["id"]}"/>' for c in ch_files)

        desc_meta = (f'    <dc:description>{_esc_xml(description)}</dc:description>'

                     if description and description.strip() else '')

        z.writestr('OEBPS/content.opf',

            '<?xml version="1.0" encoding="UTF-8"?>\n'

            '<package xmlns="http://www.idpf.org/2007/opf"'

            ' unique-identifier="bookid" version="2.0">\n'

            '  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"'

            ' xmlns:opf="http://www.idpf.org/2007/opf">\n'

            f'    <dc:identifier id="bookid">urn:uuid:{book_id}</dc:identifier>\n'

            f'    <dc:title>{_esc_xml(title)}</dc:title>\n'

            f'    <dc:creator>{_esc_xml(author)}</dc:creator>\n'

            '    <dc:language>vi</dc:language>\n'

            f'    <dc:date>{now}</dc:date>\n'

            + (desc_meta + '\n' if desc_meta else '')

            + (cover_meta + '\n' if cover_meta else '') +

            '  </metadata>\n'

            '  <manifest>\n'

            '    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>\n'

            '    <item id="css" href="style.css" media-type="text/css"/>\n'

            + (cover_manifest + '\n' if cover_manifest else '')

            + manifest_items + '\n'

            '  </manifest>\n'

            '  <spine toc="ncx">\n'

            + (cover_spine + '\n' if cover_spine else '')

            + spine_items + '\n'

            '  </spine>\n'

            '</package>')

        nav_points = '\n'.join(

            f'  <navPoint id="nav{i+1}" playOrder="{i+1}">\n'

            f'    <navLabel><text>{_esc_xml(c["title"])}</text></navLabel>\n'

            f'    <content src="{c["href"]}"/>\n'

            f'  </navPoint>' for i, c in enumerate(ch_files))

        z.writestr('OEBPS/toc.ncx',

            '<?xml version="1.0" encoding="UTF-8"?>\n'

            '<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN"'

            ' "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">\n'

            '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">\n'

            f'  <head><meta name="dtb:uid" content="urn:uuid:{book_id}"/></head>\n'

            f'  <docTitle><text>{_esc_xml(title)}</text></docTitle>\n'

            '  <navMap>\n' + nav_points + '\n  </navMap>\n</ncx>')

# ── Đọc EPUB để lấy chapters + metadata ───────────────────

def _read_epub(epub_path):

    with zipfile.ZipFile(epub_path, 'r') as z:

        names = z.namelist()

        container_xml = z.read('META-INF/container.xml').decode('utf-8')

        opf_path = re.search(r'full-path="([^"]+\.opf)"', container_xml)

        if not opf_path:

            raise ValueError('Không tìm thấy OPF path')

        opf_path = opf_path.group(1)

        opf_dir  = '/'.join(opf_path.split('/')[:-1])

        opf_pfx  = (opf_dir + '/') if opf_dir else ''

        opf_xml  = z.read(opf_path).decode('utf-8')

        # Metadata

        book_title  = _decode_entities(re.search(r'<dc:title[^>]*>(.*?)</dc:title>', opf_xml, re.S) and

                      re.search(r'<dc:title[^>]*>(.*?)</dc:title>', opf_xml, re.S).group(1) or

                      os.path.basename(epub_path))

        book_author = _decode_entities((re.search(r'<dc:creator[^>]*>(.*?)</dc:creator>', opf_xml, re.S) or

                      type('', (), {'group': lambda s,i: 'Unknown'})()).group(1))

        book_desc_m = re.search(r'<dc:description[^>]*>(.*?)</dc:description>', opf_xml, re.S)

        book_desc   = _decode_entities(book_desc_m.group(1)) if book_desc_m else ''

        # Manifest

        manifest = {}

        for m in re.finditer(r'<item\s(.*?)/>', opf_xml, re.S):

            attrs = m.group(1)

            item_id   = (re.search(r'\bid="([^"]+)"', attrs) or type('',(),{'group':lambda s,i:''})()).group(1)

            item_href  = (re.search(r'\bhref="([^"]+)"', attrs) or type('',(),{'group':lambda s,i:''})()).group(1)

            item_mime  = (re.search(r'media-type="([^"]+)"', attrs) or type('',(),{'group':lambda s,i:''})()).group(1)

            item_props = (re.search(r'properties="([^"]+)"', attrs) or type('',(),{'group':lambda s,i:''})()).group(1)

            if item_id:

                manifest[item_id] = {'href': item_href, 'mime': item_mime, 'props': item_props}

        # Cover

        cover_data = None

        cover_ext  = None

        for item_id, info in manifest.items():

            if info['mime'].startswith('image/') and (

                'cover-image' in info['props'] or item_id == 'cover-image' or

                'cover' in info['href'].lower()

            ):

                img_path = opf_pfx + info['href']

                if img_path in names:

                    cover_data = z.read(img_path)

                    cover_ext  = os.path.splitext(info['href'])[1].lower() or '.jpg'

                    break

        # Spine → chapters

        spine_idrefs = re.findall(r'<itemref\s[^>]*idref="([^"]+)"', opf_xml)

        chapters = []

        for idref in spine_idrefs:

            info = manifest.get(idref)

            if not info: continue

            if 'cover' in info['props'] or idref == 'cover-page': continue

            fp = opf_pfx + info['href']

            if fp not in names: continue

            html = z.read(fp).decode('utf-8', errors='replace')

            h1   = re.search(r'<h[12][^>]*>([\s\S]*?)</h[12]>', html, re.I)

            ch_title = _decode_entities(re.sub(r'<[^>]+>','', h1.group(1)).strip()) if h1 else ''

            if not ch_title:

                t = re.search(r'<title[^>]*>(.*?)</title>', html, re.I)

                ch_title = _decode_entities(t.group(1).strip()) if t else f'Chương {len(chapters)+1}'

            body = re.search(r'<body[^>]*>([\s\S]*?)</body>', html, re.I)

            chapters.append({'title': ch_title, 'data': body.group(1) if body else html})

        if not chapters:

            raise ValueError(f'Không đọc được chương từ {os.path.basename(epub_path)}')

    return {

        'title': book_title, 'author': book_author,

        'description': book_desc,

        'cover_data': cover_data, 'cover_ext': cover_ext,

        'chapters': chapters

    }

# ═══════════════════════════════════════════════════════════════════════════
#  TXT → EPUB có XEM TRƯỚC & SỬA CHƯƠNG (dùng trong tab Tạo & Gộp EPUB)
#  Không cần file Word trung gian. Tiêu đề chương chốt ở cửa sổ xem trước sẽ
#  được dùng cho CẢ mục lục lẫn heading <h1> trong nội dung -> không bị lệch.
# ═══════════════════════════════════════════════════════════════════════════
import io
import codecs
import queue
from dataclasses import dataclass, field, replace
from typing import Callable, Iterable, List, Optional

# ════════════════════════════════════════════════════════════════════════════
#  PHẦN 1 — MÔ HÌNH DỮ LIỆU
# ════════════════════════════════════════════════════════════════════════════


@dataclass
class Chapter:
    title: str
    content: str = ""
    kind: str = "chương"      # chương | chương (ghép) | đặc biệt | tùy chỉnh | dòng ngắn | mở đầu | thủ công
    heading_line: str = ""    # dòng gốc trong file, dùng để khôi phục khi người dùng xóa tiêu đề

    def to_pair(self) -> list:
        """Dạng [Tiêu đề, Nội dung] như bạn yêu cầu."""
        return [self.title, self.content]


@dataclass
class ScanOptions:
    strict: bool = True                    # Chương/Hồi/Chapter/第X章 ...
    special: bool = True                   # Phiên ngoại, Ngoại truyện, Lời mở đầu, Epilogue ...
    loose: bool = False                    # dòng ngắn không có dấu câu cuối
    custom_patterns: List[str] = field(default_factory=list)   # regex do người dùng nhập
    merge_next_title_line: bool = True     # "Chương 12" + dòng kế tiếp là tên chương -> ghép lại
    max_heading_len: int = 100             # tiêu đề dài hơn -> coi là câu văn
    loose_max_chars: int = 60
    loose_min_words: int = 2
    loose_max_words: int = 14
    intro_title: str = "Mở đầu"
    keep_intro: bool = True                # giữ phần chữ nằm trước tiêu đề đầu tiên


# ════════════════════════════════════════════════════════════════════════════
#  PHẦN 2 — REGEX NHẬN DIỆN TIÊU ĐỀ CHƯƠNG
# ════════════════════════════════════════════════════════════════════════════

# Từ chỉ số bằng tiếng Việt: "Chương hai mươi ba", "Chương thứ nhất", "Chương cuối"
_VI_NUM_WORD = (r"(?:không|linh|lẻ|một|mốt|hai|ba|bốn|tư|năm|lăm|sáu|bảy|bẩy|"
                r"tám|chín|mười|mươi|trăm|nghìn|ngàn|nhất|cuối)")
_NUM = (r"(?:\d{1,6}"                                   # 12
        r"|(?-i:[IVXLCDM]{1,10})"                       # XII (chỉ chữ HOA, tránh nhầm "di", "mix")
        rf"|{_VI_NUM_WORD}(?:\s+{_VI_NUM_WORD}){{0,6}})")  # hai mươi ba
_KW = (r"(?:chương|chuong|hồi|quyển|tập|phần|chapter|chap|ch\.|episode|ep\.)")

_STRICT_RE = re.compile(
    rf"^(?P<kw>{_KW})\s*(?:thứ\s+)?(?P<num>{_NUM})(?!\w)\s*"
    r"(?P<sep>[:：.\-–—、)）]*)\s*(?P<rest>.*)$",
    re.IGNORECASE,
)
# Tiêu đề kiểu Trung chưa dịch: 第12章 ...
_CN_RE = re.compile(
    r"^第\s*[0-9零〇一二两三四五六七八九十百千万]+\s*[章回节節卷集部篇话話]"
    r"\s*[:：.\-–—、]*\s*(?P<rest>.*)$"
)
# Tên chương đặc thù
_SPECIAL_RE = re.compile(
    r"^(?:phiên\s+ngoại|ngoại\s+truyện|lời\s+mở\s+đầu|lời\s+nói\s+đầu|lời\s+tựa|"
    r"mở\s+đầu|giới\s+thiệu|đại\s+kết\s+cục|kết\s+thúc|hậu\s+ký|hậu\s+kỳ|tổng\s+kết|"
    r"lời\s+cuối|phần\s+kết|prologue|epilogue|foreword|afterword|extra|side\s+story|"
    r"番外|楔子|序章|尾声)"
    rf"(?:\s*(?:\d{{1,4}}|{_VI_NUM_WORD}(?:\s+{_VI_NUM_WORD}){{0,3}}))?"
    r"\s*(?:[:：.\-–—]\s*.*)?$",
    re.IGNORECASE,
)

_DECOR_LEAD = re.compile(r"^[\s#*_~=>【\[《〈「『]+")     # "## Chương 1", "【Chương 1】"
_DECOR_TAIL = re.compile(r"[\s*_~=】\]》〉」』]+$")
_SENT_END = ".!?…。！？"                                   # dấu kết câu
_LOOSE_BAD_END = ".,;:!?…。！？，；：”\"'’)）»"
_LOOSE_BAD_START = "-–—\"“‘'«(（"
_XML_BAD = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")   # ký tự làm hỏng XHTML


def normalize_text(text: str) -> str:
    """Chuẩn hóa xuống dòng, khoảng trắng lạ, ký tự cấm của XML."""
    t = text.replace("\ufeff", "").replace("\r\n", "\n").replace("\r", "\n")
    t = t.replace("\u2028", "\n").replace("\u2029", "\n").replace("\x85", "\n")
    t = t.replace("\u00a0", " ").replace("\u3000", " ")
    return _XML_BAD.sub("", t)


def _compile_custom(patterns: Iterable[str]) -> List[re.Pattern]:
    out = []
    for p in patterns:
        p = p.strip()
        if not p:
            continue
        try:
            out.append(re.compile(p))
        except re.error as e:
            raise ValueError(f"Regex tùy chỉnh không hợp lệ: {p!r}\n{e}") from e
    return out


def _is_word_number(m: re.Match) -> bool:
    num = m.groupdict().get("num")
    return bool(num) and not re.fullmatch(r"\d+|[IVXLCDM]+", num)


def _looks_like_title(s: str, o: ScanOptions) -> bool:
    """Heuristic 'dòng ngắn không có dấu câu cuối'."""
    if len(s) > o.loose_max_chars or s[-1] in _LOOSE_BAD_END or s[0] in _LOOSE_BAD_START:
        return False
    if not (o.loose_min_words <= len(s.split()) <= o.loose_max_words):
        return False
    return s[0].isupper() or s[0].isdigit()


def _classify(line: str, o: ScanOptions, customs: List[re.Pattern]):
    """Trả về (kind, title_đã_làm_sạch) nếu dòng là tiêu đề chương, ngược lại None."""
    raw = line.strip()
    if not raw:
        return None
    s = _DECOR_TAIL.sub("", _DECOR_LEAD.sub("", raw)).strip()
    if not s or len(s) > o.max_heading_len:
        return None

    for rx in customs:                                   # 1) regex người dùng nhập
        if rx.search(s):
            return "tùy chỉnh", s

    if o.strict:                                         # 2) Chương / Hồi / Chapter / 第X章
        m = _STRICT_RE.match(s)
        if m:
            # "Hồi hai giờ chiều, ..." là câu văn, không phải tiêu đề
            if not (_is_word_number(m) and ("," in s or s.endswith(tuple(_SENT_END)))):
                return "chương", s
        elif _CN_RE.match(s):
            return "chương", s

    if o.special and len(s) <= 60 and not s.endswith(tuple(_SENT_END)) and _SPECIAL_RE.match(s):
        return "đặc biệt", s                             # 3) Phiên ngoại, Ngoại truyện...

    if o.loose and _looks_like_title(s, o):              # 4) dòng ngắn không dấu câu
        return "dòng ngắn", s
    return None


def _is_bare_heading(title: str) -> bool:
    """'Chương 12' / 'Chương 12:' trơ trọi, chưa có tên."""
    m = _STRICT_RE.match(title) or _CN_RE.match(title)
    return bool(m and not m.group("rest").strip())


def split_chapters(text: str, opts: Optional[ScanOptions] = None) -> List[Chapter]:
    """
    Quét toàn bộ văn bản trên RAM, tách thành danh sách Chapter(title, content).
    Phần chữ trước tiêu đề đầu tiên -> chương 'Mở đầu' (nếu opts.keep_intro).
    Không có tiêu đề nào -> trả về 1 chương duy nhất chứa toàn bộ văn bản.
    """
    o = opts or ScanOptions()
    customs = _compile_custom(o.custom_patterns)
    lines = normalize_text(text).split("\n")
    n = len(lines)

    chapters: List[Chapter] = []
    cur: Optional[Chapter] = None
    buf: List[str] = []

    def tidy(ls: List[str]) -> str:
        return "\n".join(x.strip() for x in ls).strip("\n")

    def flush():
        nonlocal buf
        body = tidy(buf)
        if cur is not None:
            cur.content = body
        elif body and o.keep_intro:
            chapters.insert(0, Chapter(o.intro_title, body, "mở đầu", ""))
        buf = []

    i = 0
    while i < n:
        hit = _classify(lines[i], o, customs)
        if hit is None:
            buf.append(lines[i])
            i += 1
            continue

        kind, title = hit
        heading_raw = lines[i].strip()

        # Bỏ tiêu đề lặp liền kề (cùng tên, chương trước chưa có nội dung)
        if cur is not None and not tidy(buf) and title == cur.title:
            i += 1
            continue

        # "Chương 12" + dòng kế tiếp là tên chương -> ghép
        if o.merge_next_title_line and kind == "chương" and _is_bare_heading(title):
            j = i + 1
            if j < n and not lines[j].strip():
                j += 1                                   # cho phép 1 dòng trống ở giữa
            if j < n and lines[j].strip():
                cand = lines[j].strip()
                if (len(cand) <= 80 and len(cand.split()) <= 15
                        and cand[-1] not in _LOOSE_BAD_END
                        and _classify(cand, replace(o, loose=False), customs) is None):
                    title = title.rstrip(" :：.-–—、") + ": " + cand
                    heading_raw = "\n".join(x.strip() for x in lines[i:j + 1] if x.strip())
                    kind = "chương (ghép)"
                    i = j

        flush()
        cur = Chapter(title, "", kind, heading_raw)
        chapters.append(cur)
        i += 1

    flush()
    return chapters




# ════════════════════════════════════════════════════════════════════════════
#  TXT → CHƯƠNG → EPUB (dùng chung bộ đóng gói _build_epub của app)
# ════════════════════════════════════════════════════════════════════════════

def auto_scan_chapters(text, opts=None):
    """Quét chương tự động (dùng khi KHÔNG mở cửa sổ xem trước, và cho lần quét đầu tiên).

    Nếu quét chặt tìm được < 3 tiêu đề 'Chương X...' thì tự bật quét lỏng (dòng ngắn không dấu câu).
    Trả về (danh sách Chapter, đã_bật_quét_lỏng).
    """
    o = opts or ScanOptions()
    chs = split_chapters(text, o)
    strict_hits = sum(1 for c in chs if c.kind not in ("mở đầu", "dòng ngắn"))
    if strict_hits < 3 and not o.loose:
        return split_chapters(text, replace(o, loose=True)), True
    return chs, False


def read_text_file(path):
    """Đọc TXT: UTF-8 (có/không BOM), UTF-16 có BOM; lỗi thì thử bảng mã tiếng Việt cp1258."""
    with open(path, "rb") as f:
        raw = f.read()
    if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return raw.decode("utf-16")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1258", errors="replace")


def txt_chapters_to_epub(chapters):
    """List[Chapter] → định dạng của _build_epub: [{'title', 'data'}].

    Mỗi chương mở đầu bằng <h1> đúng bằng tiêu đề đã chốt trong cửa sổ xem trước, nên tên chương
    trong mục lục và heading trong nội dung luôn khớp nhau (giống kết quả của _split_chapters).
    """
    out = []
    for i, ch in enumerate(chapters, 1):
        title = _XML_BAD.sub("", str(ch.title or "")).strip() or f"Chương {i}"
        body = []
        for line in str(ch.content or "").split("\n"):
            line = _XML_BAD.sub("", line).strip()
            if line:
                body.append(f"<p>{_esc_xml(line)}</p>")
        out.append({"title": title, "data": f"<h1>{_esc_xml(title)}</h1>\n" + "\n".join(body)})
    return out


class ChapterPreviewDialog(tk.Toplevel):
    """Cửa sổ xem trước & sửa nhanh danh sách chương (modal).

    Gọi on_done(danh_sách_Chapter) khi bấm “Xác nhận và Tạo EPUB”, hoặc on_done(None) khi hủy.
      • Chọn 1 dòng bên trái -> xem nội dung, sửa tên ở ô “Tiêu đề”.
      • “Xóa tiêu đề (gộp lên)”: tiêu đề bị nhận nhầm trở về thành văn bản, dồn vào chương trên.
      • “Tách chương tại dòng con trỏ”: bấm vào 1 dòng trong khung nội dung, dòng đó thành
        tiêu đề của chương mới (dùng khi regex bỏ sót chương).
      • “Thêm chương trống” / “Xóa cả chương”.
    """

    PREVIEW_MAX_CHARS = 300_000     # chỉ hiển thị tối đa chừng này ký tự cho mỗi chương

    def __init__(self, parent, raw_text, source_name="", on_done=None):
        super().__init__(parent)
        self.title(f"Xem trước & sửa chương — {source_name}" if source_name else "Xem trước & sửa chương")
        self.geometry("1120x700")
        self.minsize(900, 560)
        self.transient(parent)

        self.raw_text = normalize_text(raw_text)
        self.on_done = on_done
        self.chapters = []
        self._loading = False
        self._dirty = False
        self._done = False

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self._auto_scan()
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass
        self.focus_set()

    # ── dựng giao diện ──────────────────────────────────────────────────────
    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        top = ttk.LabelFrame(self, text="Quét chương")
        top.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        top.columnconfigure(3, weight=1)
        self.var_loose = tk.BooleanVar(value=False)
        self.var_merge = tk.BooleanVar(value=True)
        self.var_custom = tk.StringVar()
        ttk.Checkbutton(top, text="Quét lỏng (thêm dòng ngắn không dấu câu cuối)",
                        variable=self.var_loose).grid(row=0, column=0, padx=6, pady=4, sticky="w")
        ttk.Checkbutton(top, text="Ghép dòng kế tiếp vào “Chương X” trơ trọi",
                        variable=self.var_merge).grid(row=0, column=1, padx=6, sticky="w")
        ttk.Label(top, text="Regex tên đặc thù:").grid(row=0, column=2, padx=(12, 4), sticky="e")
        ttk.Entry(top, textvariable=self.var_custom).grid(row=0, column=3, sticky="ew", padx=4)
        ttk.Button(top, text="Quét lại", command=self._rescan).grid(row=0, column=4, padx=6)

        pan = ttk.PanedWindow(self, orient="horizontal")
        pan.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        self._pan = pan

        left = ttk.Frame(pan)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(left, columns=("idx", "title", "kind", "chars"),
                                 show="headings", selectmode="browse")
        for c, txt, w, anc in (("idx", "#", 40, "e"), ("title", "Tiêu đề chương", 290, "w"),
                               ("kind", "Loại", 105, "w"), ("chars", "Ký tự", 70, "e")):
            self.tree.heading(c, text=txt)
            self.tree.column(c, width=w, anchor=anc, stretch=(c == "title"))
        sb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.tag_configure("empty", foreground="#c0392b")
        self.tree.tag_configure("loose", background="#fff4d6")
        self.tree.tag_configure("manual", background=THEME["g100"])
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        pan.add(left, weight=2)

        right = ttk.Frame(pan)
        right.columnconfigure(1, weight=1)
        right.rowconfigure(1, weight=1)
        ttk.Label(right, text="Tiêu đề:").grid(row=0, column=0, sticky="w", padx=(6, 4), pady=4)
        self.var_title = tk.StringVar()
        self.ent_title = ttk.Entry(right, textvariable=self.var_title)
        self.ent_title.grid(row=0, column=1, sticky="ew", padx=(0, 6))
        self.var_title.trace_add("write", self._on_title_edit)

        self.txt = tk.Text(right, wrap="word", undo=False, font=FONT_TEXT, padx=8, pady=6)
        tsb = ttk.Scrollbar(right, orient="vertical", command=self.txt.yview)
        self.txt.configure(yscrollcommand=tsb.set)
        self.txt.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=(6, 0))
        tsb.grid(row=1, column=2, sticky="ns")
        self.txt.tag_configure("cur", background=THEME["g200"])
        self.txt.bind("<Key>", self._block_edit)
        self.txt.bind("<<Paste>>", lambda e: "break")
        self.txt.bind("<<Cut>>", lambda e: "break")
        self.txt.bind("<ButtonRelease-1>", self._hl_cursor_line)
        self.txt.bind("<KeyRelease>", self._hl_cursor_line)

        self.lbl_info = ttk.Label(right, text="", style="Muted.TLabel")
        self.lbl_info.grid(row=2, column=0, columnspan=2, sticky="w", padx=6)

        btns = ttk.Frame(right)
        btns.grid(row=3, column=0, columnspan=3, sticky="ew", padx=6, pady=6)
        btns.columnconfigure((0, 1), weight=1, uniform="b")
        ttk.Button(btns, text="✂ Tách chương tại dòng con trỏ",
                   command=self._split_at_cursor).grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=2)
        ttk.Button(btns, text="＋ Thêm chương trống",
                   command=self._add_empty).grid(row=0, column=1, sticky="ew", padx=(4, 0), pady=2)
        ttk.Button(btns, text="⤴ Xóa tiêu đề (gộp lên)",
                   command=self._remove_heading).grid(row=1, column=0, sticky="ew", padx=(0, 4), pady=2)
        ttk.Button(btns, text="🗑 Xóa cả chương", style="Pink.TButton",
                   command=self._delete_chapter).grid(row=1, column=1, sticky="ew", padx=(4, 0), pady=2)
        pan.add(right, weight=3)
        self.after(150, self._set_sash)

        bot = ttk.Frame(self)
        bot.grid(row=2, column=0, sticky="ew", padx=8, pady=(4, 8))
        bot.columnconfigure(0, weight=1)
        self.var_status = tk.StringVar()
        ttk.Label(bot, textvariable=self.var_status, style="Ok.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(bot, text="Hủy (bỏ qua file này)", command=self._cancel).grid(row=0, column=1, padx=4)
        ttk.Button(bot, text="✔ Xác nhận và Tạo EPUB", style="Accent.TButton",
                   command=self._confirm).grid(row=0, column=2, padx=4)

    def _set_sash(self):
        try:
            self._pan.sashpos(0, 535)          # chừa đủ chỗ cho 4 cột bên trái
        except tk.TclError:
            pass

    # ── quét ───────────────────────────────────────────────────────────────
    def _scan_options(self):
        p = self.var_custom.get().strip()
        return ScanOptions(loose=self.var_loose.get(), merge_next_title_line=self.var_merge.get(),
                           custom_patterns=[p] if p else [])

    def _scan(self, auto=False):
        note = ""
        try:
            if auto:
                self.chapters, used_loose = auto_scan_chapters(self.raw_text, self._scan_options())
                if used_loose:
                    self.var_loose.set(True)
                    note = "ít tiêu đề “Chương X” → đã tự bật quét lỏng, hãy xem các dòng tô vàng"
            else:
                self.chapters = split_chapters(self.raw_text, self._scan_options())
        except ValueError as e:
            messagebox.showerror("Regex lỗi", str(e), parent=self)
            return False
        self._dirty = False
        self._refresh_tree(select=0)
        if note:
            self.var_status.set(f"{self.var_status.get()}  •  {note}")
        return True

    def _auto_scan(self):
        self._scan(auto=True)

    def _rescan(self):
        if self._dirty and not messagebox.askyesno(
                "Quét lại?", "Quét lại sẽ bỏ các chỉnh sửa thủ công. Tiếp tục?", parent=self):
            return
        self._scan()

    def _update_status(self):
        empty = sum(1 for c in self.chapters if not c.content.strip())
        msg = f"{len(self.chapters)} chương"
        if empty:
            msg += f"  •  {empty} chương trống (chữ đỏ) – kiểm tra xem có nhận nhầm tiêu đề không"
        self.var_status.set(msg)

    # ── danh sách ──────────────────────────────────────────────────────────
    @staticmethod
    def _row_tags(ch):
        tags = []
        if not ch.content.strip():
            tags.append("empty")
        if ch.kind == "dòng ngắn":
            tags.append("loose")
        elif ch.kind == "thủ công":
            tags.append("manual")
        return tuple(tags)

    def _refresh_tree(self, select=None):
        self.tree.delete(*self.tree.get_children())
        for i, ch in enumerate(self.chapters):
            self.tree.insert("", "end", iid=str(i),
                             values=(i + 1, ch.title, ch.kind, f"{len(ch.content):,}"),
                             tags=self._row_tags(ch))
        if self.chapters:
            idx = min(max(select or 0, 0), len(self.chapters) - 1)
            self.tree.selection_set(str(idx))
            self.tree.focus(str(idx))
            self.tree.see(str(idx))
        else:
            self._show_chapter(None)
        self._update_status()

    def _cur_index(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _on_select(self, _e=None):
        self._show_chapter(self._cur_index())

    def _show_chapter(self, idx):
        self._loading = True
        try:
            self.txt.delete("1.0", "end")
            if idx is None or idx >= len(self.chapters):
                self.var_title.set("")
                self.lbl_info.config(text="")
                return
            ch = self.chapters[idx]
            self.var_title.set(ch.title)
            shown, note = ch.content, ""
            if len(shown) > self.PREVIEW_MAX_CHARS:
                cut = shown.rfind("\n", 0, self.PREVIEW_MAX_CHARS)
                shown = shown[: cut if cut > 0 else self.PREVIEW_MAX_CHARS]
                note = "  — chỉ hiển thị phần đầu"
            self.txt.insert("1.0", shown)
            self.txt.mark_set("insert", "1.0")
            self.lbl_info.config(text=f"{len(ch.content):,} ký tự{note}")
        finally:
            self._loading = False

    def _on_title_edit(self, *_):
        if self._loading:
            return
        i = self._cur_index()
        if i is None:
            return
        self.chapters[i].title = self.var_title.get()
        self._dirty = True
        self.tree.set(str(i), "title", self.var_title.get())

    # ── khung nội dung chỉ đọc ─────────────────────────────────────────────
    @staticmethod
    def _block_edit(e):
        nav = {"Left", "Right", "Up", "Down", "Home", "End", "Prior", "Next"}
        if e.keysym in nav or (e.state & 0x4 and e.keysym.lower() in ("c", "a")):
            return None
        return "break"

    def _hl_cursor_line(self, _e=None):
        self.txt.tag_remove("cur", "1.0", "end")
        self.txt.tag_add("cur", "insert linestart", "insert lineend+1c")

    # ── các thao tác sửa ───────────────────────────────────────────────────
    def _split_at_cursor(self):
        i = self._cur_index()
        if i is None:
            return
        ch = self.chapters[i]
        line_no = int(self.txt.index("insert").split(".")[0]) - 1
        lines = ch.content.split("\n")
        if not (0 <= line_no < len(lines)) or not lines[line_no].strip():
            messagebox.showinfo("Chưa chọn dòng",
                                "Hãy bấm vào dòng chữ muốn làm tiêu đề chương mới (trong khung nội dung), rồi thử lại.",
                                parent=self)
            return
        new = Chapter(lines[line_no].strip(), "\n".join(lines[line_no + 1:]).strip("\n"),
                      "thủ công", lines[line_no].strip())
        ch.content = "\n".join(lines[:line_no]).strip("\n")
        self.chapters.insert(i + 1, new)
        self._dirty = True
        self._refresh_tree(select=i + 1)

    def _add_empty(self):
        i = self._cur_index()
        pos = (i + 1) if i is not None else len(self.chapters)
        self.chapters.insert(pos, Chapter("Chương mới", "", "thủ công", ""))
        self._dirty = True
        self._refresh_tree(select=pos)
        self.ent_title.focus_set()
        self.ent_title.select_range(0, "end")

    def _remove_heading(self):
        """Tiêu đề nhận nhầm -> trả về thành dòng văn bản, gộp nội dung vào chương trên."""
        i = self._cur_index()
        if i is None:
            return
        ch = self.chapters[i]
        block = "\n".join(x for x in (ch.heading_line, ch.content) if x)
        if i > 0:
            prev = self.chapters[i - 1]
            prev.content = "\n".join(x for x in (prev.content, block) if x)
            del self.chapters[i]
            sel = i - 1
        else:
            # Chương đầu tiên: không có chương nào ở trên để gộp vào -> chuyển thành phần "Mở đầu"
            # (KHÔNG dồn xuống chương sau, vì sẽ làm đảo thứ tự văn bản).
            if ch.kind == "mở đầu":
                messagebox.showinfo(
                    "Không thể gộp lên",
                    "Đây là phần chữ nằm trước tiêu đề đầu tiên nên không có chương nào ở trên.\n"
                    "Dùng “Xóa cả chương” nếu muốn bỏ phần này.", parent=self)
                return
            ch.title, ch.kind, ch.content, ch.heading_line = "Mở đầu", "mở đầu", block, ""
            sel = 0
        self._dirty = True
        self._refresh_tree(select=sel)

    def _delete_chapter(self):
        i = self._cur_index()
        if i is None:
            return
        ch = self.chapters[i]
        if not messagebox.askyesno(
                "Xóa cả chương?",
                f"Xóa “{ch.title}” và toàn bộ {len(ch.content):,} ký tự nội dung?\n"
                "(Muốn giữ chữ, hãy dùng “Xóa tiêu đề (gộp lên)”.)", parent=self):
            return
        del self.chapters[i]
        self._dirty = True
        self._refresh_tree(select=max(i - 1, 0))

    # ── kết thúc: xác nhận / hủy ───────────────────────────────────────────
    def _finish(self, result):
        if self._done:
            return
        self._done = True
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()
        if self.on_done:
            self.on_done(result)

    def _confirm(self):
        if not self.chapters:
            messagebox.showwarning("Trống", "Chưa có chương nào để tạo EPUB.", parent=self)
            return
        empty = sum(1 for c in self.chapters if not c.content.strip())
        if empty and not messagebox.askyesno(
                "Có chương trống",
                f"Có {empty} chương chưa có nội dung (chữ đỏ). Vẫn tạo EPUB?", parent=self):
            return
        result = [Chapter((c.title or "").strip() or f"Chương {i}", c.content, c.kind, c.heading_line)
                  for i, c in enumerate(self.chapters, 1)]
        self._finish(result)

    def _cancel(self):
        if self._dirty and not messagebox.askyesno(
                "Bỏ qua file này?", "Các chỉnh sửa chưa được dùng để tạo EPUB sẽ mất. Đóng thật không?",
                parent=self):
            return
        self._finish(None)


class TabEpub(ttk.Frame):

    def __init__(self, parent):

        super().__init__(parent)

        self._build()

    def _build(self):

        # Sub-tabs: Tạo / Gộp

        self._mode = tk.StringVar(value='create')

        top = ttk.Frame(self)

        top.pack(side=tk.TOP, fill=tk.X, padx=6, pady=(6,0))

        self._btn_create = ttk.Button(top, text="📄 Tạo EPUB (.docx / .txt)",

                                      command=lambda: self._switch('create'))

        self._btn_create.pack(side=tk.LEFT)

        self._btn_merge = ttk.Button(top, text="🔗 Gộp EPUB",

                                     command=lambda: self._switch('merge'))

        self._btn_merge.pack(side=tk.LEFT, padx=(6,0))

        # Container chứa 2 panel

        self._container = ttk.Frame(self)

        self._container.pack(fill=tk.BOTH, expand=True)

        self._panel_create = self._build_create(self._container)

        self._panel_merge  = self._build_merge(self._container)

        self._switch('create')

    def _switch(self, mode):

        self._mode.set(mode)

        if mode == 'create':

            self._panel_merge.pack_forget()

            self._panel_create.pack(fill=tk.BOTH, expand=True)

        else:

            self._panel_create.pack_forget()

            self._panel_merge.pack(fill=tk.BOTH, expand=True)

    # ── PANEL TẠO EPUB ────────────────────────────────────

    def _build_create(self, parent):

        frame = ttk.Frame(parent)

        pw = ttk.PanedWindow(frame, orient=tk.HORIZONTAL)

        pw.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # Trái: form

        left = ttk.Frame(pw)

        pw.add(left, weight=2)

        # Thông tin sách

        info = ttk.LabelFrame(left, text="Thông tin sách")

        info.pack(fill=tk.BOTH, expand=True, pady=(0,6))

        ttk.Label(info, text="Tên truyện *").grid(row=0, column=0, sticky=tk.W, padx=8, pady=4)

        self._c_title = ttk.Entry(info, width=30)

        self._c_title.grid(row=0, column=1, sticky=tk.EW, padx=(0,8), pady=4)

        ttk.Label(info, text="Tác giả").grid(row=1, column=0, sticky=tk.W, padx=8, pady=4)

        self._c_author = ttk.Entry(info, width=30)

        self._c_author.grid(row=1, column=1, sticky=tk.EW, padx=(0,8), pady=4)

        ttk.Label(info, text="Văn án").grid(row=2, column=0, sticky=tk.W, padx=8, pady=(4,0))

        self._c_desc = tk.Text(info, height=10, font=("Segoe UI", 9), wrap=tk.WORD)

        self._c_desc.grid(row=3, column=0, columnspan=3, sticky=tk.NSEW, padx=8, pady=(0,6))

        _c_desc_sb = ttk.Scrollbar(info, orient=tk.VERTICAL, command=self._c_desc.yview)

        _c_desc_sb.grid(row=3, column=3, sticky=tk.NS, pady=(0,6))

        self._c_desc.configure(yscrollcommand=_c_desc_sb.set)

        info.columnconfigure(1, weight=1)

        info.rowconfigure(3, weight=1)   # văn án giãn theo cửa sổ

        # Ảnh bìa

        cover_f = ttk.LabelFrame(left, text="Ảnh bìa (tuỳ chọn)")

        cover_f.pack(fill=tk.X, pady=(0,6))

        self._c_cover_var = tk.StringVar(value="Chưa chọn ảnh bìa")

        ttk.Label(cover_f, textvariable=self._c_cover_var,

                  foreground="#888").pack(side=tk.LEFT, padx=8, pady=6, fill=tk.X, expand=True)

        ttk.Button(cover_f, text="🖼 Chọn ảnh",

                   command=self._c_pick_cover).pack(side=tk.RIGHT, padx=(0,8), pady=6)

        ttk.Button(cover_f, text="✕", width=3,

                   command=self._c_clear_cover).pack(side=tk.RIGHT, pady=6)

        self._c_cover_path = ''

        # File .docx

        docx_f = ttk.LabelFrame(left, text="File nguồn (.docx / .txt)")

        docx_f.pack(fill=tk.X, pady=(0,6))

        btn_row = ttk.Frame(docx_f)

        btn_row.pack(fill=tk.X, padx=6, pady=(6,4))

        ttk.Button(btn_row, text="＋ Thêm file .docx / .txt",

                   command=self._c_add_docx).pack(side=tk.LEFT)

        ttk.Button(btn_row, text="📁 Chọn thư mục",

                   command=self._c_add_folder).pack(side=tk.LEFT, padx=(6,0))

        ttk.Button(btn_row, style="Pink.TButton", text="🗑 Xoá tất cả",

                   command=self._c_clear_docx).pack(side=tk.RIGHT)

        ttk.Button(btn_row, style="Pink.TButton", text="✕ Xoá mục chọn",

                   command=self._c_remove_selected).pack(side=tk.RIGHT, padx=(0,6))

        self._c_docx_lb = tk.Listbox(docx_f, height=4, selectmode=tk.EXTENDED,

                                     font=("Consolas",9))

        self._c_docx_lb.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0,6))

        self._c_docx_lb.bind("<Delete>", lambda e: self._c_remove_selected())

        self._c_docx_files = []
        self._c_preview_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(docx_f, text="Với file .txt: xem trước & sửa chương trước khi tạo EPUB",
                        variable=self._c_preview_var).pack(anchor="w", padx=8, pady=(0, 6))

        # Thư mục lưu

        out_f = ttk.LabelFrame(left, text="Thư mục lưu EPUB")

        out_f.pack(fill=tk.X, pady=(0,6))

        self._c_outdir_var = tk.StringVar(value="Chưa chọn thư mục")

        ttk.Label(out_f, textvariable=self._c_outdir_var,

                  foreground="#888").pack(side=tk.LEFT, padx=8, pady=6, fill=tk.X, expand=True)

        ttk.Button(out_f, text="📁 Chọn",

                   command=self._c_pick_outdir).pack(side=tk.RIGHT, padx=(0,8), pady=6)

        self._c_outdir = ''

        ttk.Button(left, text="▶ Xuất EPUB", style="Accent.TButton",

                   command=self._c_run).pack(pady=4)

        # Phải: log

        right = ttk.LabelFrame(pw, text="Nhật ký")

        pw.add(right, weight=1)

        self._c_log = tk.Text(right, state=tk.DISABLED, wrap=tk.WORD,

                              font=("Consolas",9), background="#1a1a1a",

                              foreground="#cccccc")

        self._c_log.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        sb = ttk.Scrollbar(right, command=self._c_log.yview)

        self._c_log.configure(yscrollcommand=sb.set)

        return frame

    # ── PANEL GỘP EPUB ────────────────────────────────────

    def _build_merge(self, parent):

        frame = ttk.Frame(parent)

        pw = ttk.PanedWindow(frame, orient=tk.HORIZONTAL)

        pw.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        left = ttk.Frame(pw)

        pw.add(left, weight=2)

        info = ttk.LabelFrame(left, text="Thông tin bộ sách gộp (bỏ trống = tự lấy từ file đầu)")

        info.pack(fill=tk.X, pady=(0,6))

        ttk.Label(info, text="Tên truyện").grid(row=0, column=0, sticky=tk.W, padx=8, pady=4)

        self._m_title = ttk.Entry(info, width=30)

        self._m_title.grid(row=0, column=1, sticky=tk.EW, padx=(0,8), pady=4)

        ttk.Label(info, text="Tác giả").grid(row=1, column=0, sticky=tk.W, padx=8, pady=4)

        self._m_author = ttk.Entry(info, width=30)

        self._m_author.grid(row=1, column=1, sticky=tk.EW, padx=(0,8), pady=4)

        info.columnconfigure(1, weight=1)

        epub_f = ttk.LabelFrame(left, text="File EPUB cần gộp (theo thứ tự)")

        epub_f.pack(fill=tk.BOTH, expand=True, pady=(0,6))

        btn_row = ttk.Frame(epub_f)

        btn_row.pack(fill=tk.X, padx=6, pady=(6,4))

        ttk.Button(btn_row, text="＋ Thêm file EPUB",

                   command=self._m_add_epub).pack(side=tk.LEFT)

        ttk.Button(btn_row, text="⬆ Lên",

                   command=self._m_move_up).pack(side=tk.LEFT, padx=(6,0))

        ttk.Button(btn_row, text="⬇ Xuống",

                   command=self._m_move_down).pack(side=tk.LEFT, padx=(4,0))

        ttk.Button(btn_row, style="Pink.TButton", text="🗑 Xoá",

                   command=self._m_remove).pack(side=tk.RIGHT)

        self._m_epub_lb = tk.Listbox(epub_f, height=8, selectmode=tk.SINGLE,

                                     font=("Consolas",9))

        self._m_epub_lb.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0,6))

        self._m_epub_files = []

        out_f = ttk.LabelFrame(left, text="Thư mục lưu kết quả")

        out_f.pack(fill=tk.X, pady=(0,6))

        self._m_outdir_var = tk.StringVar(value="Chưa chọn thư mục")

        ttk.Label(out_f, textvariable=self._m_outdir_var,

                  foreground="#888").pack(side=tk.LEFT, padx=8, pady=6, fill=tk.X, expand=True)

        ttk.Button(out_f, text="📁 Chọn",

                   command=self._m_pick_outdir).pack(side=tk.RIGHT, padx=(0,8), pady=6)

        self._m_outdir = ''

        ttk.Button(left, text="🔗 Gộp EPUB", style="Accent.TButton", command=self._m_run).pack(pady=4)

        right = ttk.LabelFrame(pw, text="Nhật ký")

        pw.add(right, weight=1)

        self._m_log = tk.Text(right, state=tk.DISABLED, wrap=tk.WORD,

                              font=("Consolas",9), background="#1a1a1a",

                              foreground="#cccccc")

        self._m_log.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        sb2 = ttk.Scrollbar(right, command=self._m_log.yview)

        self._m_log.configure(yscrollcommand=sb2.set)

        return frame

    # ── Helpers log ───────────────────────────────────────

    def _log(self, widget, msg):

        widget.configure(state=tk.NORMAL)

        widget.insert(tk.END, msg + '\n')

        widget.see(tk.END)

        widget.configure(state=tk.DISABLED)

    # ── Create actions ────────────────────────────────────

    def _c_pick_cover(self):

        p = filedialog.askopenfilename(

            title="Chọn ảnh bìa",

            filetypes=[("Ảnh","*.jpg *.jpeg *.png *.webp *.gif"),("Tất cả","*.*")]

        )

        if not p: return

        self._c_cover_path = p

        label = os.path.basename(p)

        try:

            size = os.path.getsize(p)

            if not p.lower().endswith(".webp"):

                with open(p, "rb") as f:

                    webp = _image_bytes_to_webp(f.read())

                if webp:

                    label = f"{os.path.basename(p)}  ({_fmt_kb(size)} → WebP {_fmt_kb(len(webp))} khi xuất)"

                else:

                    label = f"{os.path.basename(p)}  ({_fmt_kb(size)})"

            else:

                label = f"{os.path.basename(p)}  ({_fmt_kb(size)})"

        except Exception:

            pass

        self._c_cover_var.set(label)

    def _c_clear_cover(self):

        self._c_cover_path = ''

        self._c_cover_var.set("Chưa chọn ảnh bìa")

    def _c_add_docx(self):
        paths = filedialog.askopenfilenames(
            title="Chọn file .docx hoặc .txt",
            filetypes=[("Word / Văn bản", "*.docx *.txt"), ("Word", "*.docx"),
                       ("Văn bản (.txt)", "*.txt"), ("Tất cả", "*.*")]
        )

        for p in paths:

            if p not in self._c_docx_files:

                self._c_docx_files.append(p)

                self._c_docx_lb.insert(tk.END, os.path.basename(p))

    def _c_add_folder(self):

        folder = filedialog.askdirectory(title="Chọn thư mục chứa .docx / .txt")

        if not folder: return

        files = sorted([

            os.path.join(folder, f)

            for f in os.listdir(folder)
            if f.lower().endswith(('.docx', '.txt')) and not f.startswith('~$')

        ])

        for p in files:

            if p not in self._c_docx_files:

                self._c_docx_files.append(p)

                self._c_docx_lb.insert(tk.END, os.path.basename(p))

    def _c_remove_selected(self):

        sel = list(self._c_docx_lb.curselection())

        if not sel:

            messagebox.showinfo("Thông báo", "Chọn 1 hoặc nhiều file trong danh sách trước (giữ Ctrl để chọn nhiều).")

            return

        for i in reversed(sel):

            self._c_docx_lb.delete(i)

            del self._c_docx_files[i]

    def _c_clear_docx(self):

        self._c_docx_files.clear()

        self._c_docx_lb.delete(0, tk.END)

    def _c_pick_outdir(self):

        d = filedialog.askdirectory(title="Chọn thư mục lưu EPUB")

        if not d: return

        self._c_outdir = d

        self._c_outdir_var.set(d)

    def _c_run(self):
        title  = self._c_title.get().strip()
        author = self._c_author.get().strip() or 'Unknown'
        desc   = self._c_desc.get("1.0", "end-1c").strip()
        if not title:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng nhập Tên truyện.")
            return
        if not self._c_docx_files:
            messagebox.showwarning("Thiếu file", "Vui lòng thêm ít nhất 1 file .docx hoặc .txt.")
            return
        if not self._c_outdir:
            messagebox.showwarning("Thiếu thư mục", "Vui lòng chọn thư mục lưu.")
            return
        preview = bool(self._c_preview_var.get())
        log = lambda m: self._log(self._c_log, m)

        def run():
            files = list(self._c_docx_files)
            used_names = set()
            for fp in files:
                fname = os.path.basename(fp)
                use_title = title if len(files) == 1 else os.path.splitext(fname)[0]
                log(f"[►] Đang xử lý: {fname}")
                try:
                    if fp.lower().endswith('.txt'):
                        chapters = self._c_chapters_from_txt(fp, preview, log)
                        if chapters is None:
                            log("    ⏭ Đã hủy ở cửa sổ xem trước — bỏ qua file này")
                            continue
                    else:
                        html     = _read_docx_html(fp)
                        chapters = _split_chapters(html)
                    log(f"    {len(chapters)} chương tìm thấy")
                    base = re.sub(r'[\\/:*?"<>|]', '_', use_title)
                    name, n = base, 2
                    while name.lower() in used_names:          # vd. a.docx và a.txt cùng tên
                        name, n = f"{base} ({n})", n + 1
                    used_names.add(name.lower())
                    out = os.path.join(self._c_outdir, name + '.epub')
                    buf = io.BytesIO()                          # đóng gói trên RAM, ghi đĩa đúng 1 lần
                    _build_epub(use_title, author, desc, self._c_cover_path, chapters, buf, log=log)
                    with open(out, 'wb') as f:
                        f.write(buf.getvalue())
                    log(f"    ✅ Xong → {os.path.basename(out)}")
                except Exception as e:
                    log(f"    ❌ Lỗi: {e}")
            log("═" * 40)
            log("✅ Hoàn tất tất cả file!")
        Thread(target=run, daemon=True).start()

    def _c_chapters_from_txt(self, fp, preview, log):
        """Đọc TXT -> danh sách chương (định dạng của _build_epub).
        Trả về None nếu người dùng hủy ở cửa sổ xem trước.
        Hàm này chạy ở luồng nền: cửa sổ xem trước được mở trên luồng giao diện, luồng nền đứng đợi."""
        text = read_text_file(fp)
        if not preview:
            chs, used_loose = auto_scan_chapters(text)
            if used_loose:
                log("    ⚠ Ít tiêu đề “Chương X” → đã dùng quét lỏng (nên bật xem trước để kiểm tra)")
            return txt_chapters_to_epub(chs)
        log("    ⏳ Đang chờ bạn kiểm tra chương trong cửa sổ xem trước…")
        q = queue.Queue()

        def open_dialog():
            try:
                ChapterPreviewDialog(self.winfo_toplevel(), text, os.path.basename(fp), on_done=q.put)
            except Exception as e:                              # đừng để luồng nền treo mãi
                q.put(e)
        self.after(0, open_dialog)
        result = q.get()
        if isinstance(result, Exception):
            raise result
        return None if result is None else txt_chapters_to_epub(result)


    # ── Merge actions ─────────────────────────────────────

    def _m_add_epub(self):
        paths = filedialog.askopenfilenames(
            title="Chọn file EPUB",
            filetypes=[("EPUB", "*.epub"), ("Tất cả", "*.*")]
        )

        for p in paths:
            if p not in self._m_epub_files:
                self._m_epub_files.append(p)
                self._m_epub_lb.insert(
                    tk.END,
                    os.path.basename(p)
                )

    def _m_move_up(self):
        sel = self._m_epub_lb.curselection()

        if not sel or sel[0] == 0:
            return

        i = sel[0]

        self._m_epub_files[i - 1], self._m_epub_files[i] = (
            self._m_epub_files[i],
            self._m_epub_files[i - 1]
        )

        names = [
            os.path.basename(p)
            for p in self._m_epub_files
        ]

        self._m_epub_lb.delete(0, tk.END)

        for n in names:
            self._m_epub_lb.insert(tk.END, n)

        self._m_epub_lb.selection_set(i - 1)

    def _m_move_down(self):
        sel = self._m_epub_lb.curselection()

        if not sel or sel[0] >= len(self._m_epub_files) - 1:
            return

        i = sel[0]

        self._m_epub_files[i], self._m_epub_files[i + 1] = (
            self._m_epub_files[i + 1],
            self._m_epub_files[i]
        )

        names = [
            os.path.basename(p)
            for p in self._m_epub_files
        ]

        self._m_epub_lb.delete(0, tk.END)

        for n in names:
            self._m_epub_lb.insert(tk.END, n)

        self._m_epub_lb.selection_set(i + 1)

    def _m_remove(self):
        sel = self._m_epub_lb.curselection()

        if not sel:
            return

        i = sel[0]

        self._m_epub_files.pop(i)
        self._m_epub_lb.delete(i)

    def _m_pick_outdir(self):

        d = filedialog.askdirectory(title="Chọn thư mục lưu")

        if not d: return

        self._m_outdir = d

        self._m_outdir_var.set(d)

    def _m_run(self):

        if len(self._m_epub_files) < 2:

            messagebox.showwarning("Thiếu file", "Cần ít nhất 2 file EPUB để gộp.")

            return

        if not self._m_outdir:

            messagebox.showwarning("Thiếu thư mục", "Vui lòng chọn thư mục lưu.")

            return

        title  = self._m_title.get().strip()

        author = self._m_author.get().strip()

        def run():

            all_chapters = []

            first = None

            for ep in self._m_epub_files:

                self._log(self._m_log, f"[►] Đọc: {os.path.basename(ep)}")

                try:

                    data = _read_epub(ep)

                    if first is None:

                        first = data

                    all_chapters.extend(data['chapters'])

                    self._log(self._m_log, f"    {len(data['chapters'])} chương")

                except Exception as e:

                    self._log(self._m_log, f"    ❌ Lỗi: {e}")

                    return

            merged_title  = title  or (first['title']  if first else 'Gop_EPUB')

            merged_author = author or (first['author']  if first else 'Unknown')

            merged_desc   = first['description'] if first else ''

            # Tạm lưu cover từ first epub

            cover_path = ''

            if first and first.get('cover_data'):

                ext = first.get('cover_ext', '.jpg')

                import tempfile

                tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)

                tmp.write(first['cover_data'])

                tmp.close()

                cover_path = tmp.name

            out_name = re.sub(r'[\\/:*?"<>|]','_', merged_title) + '.epub'

            out_path = os.path.join(self._m_outdir, out_name)

            self._log(self._m_log, f"[►] Đang gộp {len(all_chapters)} chương...")

            try:

                _build_epub(merged_title, merged_author, merged_desc,

                            cover_path, all_chapters, out_path,

                            log=lambda m: self._log(self._m_log, m))

                self._log(self._m_log, f"✅ Xong → {out_name}")

                if cover_path and os.path.exists(cover_path):

                    os.unlink(cover_path)

            except Exception as e:

                self._log(self._m_log, f"❌ Lỗi khi build EPUB: {e}")

        Thread(target=run, daemon=True).start()

# ═══════════════════════════════════════════════════════════

#  PHẦN 8 — TAB 5: DỊCH TRUNG → VIỆT (offline, dựa trên từ điển)

#  Engine port từ translateZhToVi.js (Name.json + VP.json + HanViet.json)

# ═══════════════════════════════════════════════════════════

import sys

import json

import threading

import urllib.request

from tkinter import scrolledtext, simpledialog

TRANS_DEFAULT_SETTINGS = {

    "nameUrl": "https://raw.githubusercontent.com/bachhoppo18/slh/refs/heads/main/translate/Name.json",

    "vpUrl":   "https://raw.githubusercontent.com/bachhoppo18/slh/refs/heads/main/translate/VP.json",

    "hvUrl":   "https://raw.githubusercontent.com/bachhoppo18/slh/refs/heads/main/translate/HanViet.json",

    "maxMatchLen": 30,

    "priorityNameFirst": True,

    "punctMap": "vietnamese",

    # Dịch qua server (như app gốc)

    "serverUrl": "https://dichngay.com/translate/text",

    "delayMs": 400,

    "maxChars": 4500,

}

def _trans_app_dir():
    return APP_DATA_DIR

TRANS_DICT_DIR = os.path.join(_trans_app_dir(), "dict")

TRANS_CONFIG_PATH = os.path.join(_trans_app_dir(), "translator_config.json")

_TRANS_CJK_RE = re.compile(r'[㐀-䶿一-鿿豈-﫿]')

def _trans_is_cjk(ch):

    return bool(_TRANS_CJK_RE.match(ch))

def _trans_split_runs(s):

    """Tách chuỗi thành các run CJK / OTHER (port splitRuns)."""

    runs, buf, mode = [], "", None

    for ch in s:

        now = "CJK" if _trans_is_cjk(ch) else "OTHER"

        if mode is None:

            buf, mode = ch, now

            continue

        if now == mode:

            buf += ch

        else:

            runs.append((mode, buf))

            buf, mode = ch, now

    if buf:

        runs.append((mode, buf))

    return runs

def _trans_normalize_dict(raw):

    """Chuẩn hoá dict về {key: {val, alts, skip?}} (port normalizeDictAny)."""

    out = {}

    for k, v in raw.items():

        if not k or v is None:

            continue

        if isinstance(v, str):

            parts = [x.strip() for x in v.split("/")]

            first = parts[0] if parts else ""

            if first == "":

                out[k] = {"val": "", "alts": parts if parts else [""], "skip": True}

            else:

                out[k] = {"val": first, "alts": parts if parts else [first]}

        elif isinstance(v, dict) and "val" in v:

            val = str(v.get("val") or "").strip()

            alts = [str(x).strip() for x in v.get("alts", []) if str(x).strip()] if isinstance(v.get("alts"), list) else ([val] if val else [])

            entry = {"val": val, "alts": alts if alts else [val]}

            if val == "":

                entry["skip"] = True

            out[k] = entry

        else:

            s = str(v).strip()

            out[k] = {"val": s, "alts": [s]}

    return out

def _trans_build_buckets(d):

    """Gom key theo độ dài (port buildBucketsFromDict). → (buckets, maxLen)"""

    buckets, max_len = {}, 0

    for k, v in d.items():

        l = len(k)

        if l == 0:

            continue

        buckets.setdefault(l, {})[k] = v

        if l > max_len:

            max_len = l

    return buckets, max_len

_TRANS_EMPTY_IDX = ({}, 0)

def _trans_longest_match(text, user_idx, name_idx, vp_idx, hv_dict, opts):

    """Khớp dài-nhất-toàn-cục trên 1 run CJK (port globalLongestMatch).

    Ưu tiên: bộ name của người dùng > Name/VP (theo priorityNameFirst) > Hán-Việt từng chữ.

    """

    N = len(text)

    max_from_dict = max(user_idx[1], name_idx[1], vp_idx[1])

    mm = opts.get("maxMatchLen") or 0

    max_len = min(mm, max_from_dict) if mm else max_from_dict

    replaced = [False] * N

    slots = [None] * N

    prio_name = opts.get("priorityNameFirst", True)

    for l in range(max_len, 0, -1):

        ub = user_idx[0].get(l)

        nb = name_idx[0].get(l)

        vb = vp_idx[0].get(l)

        if not ub and not nb and not vb:

            continue

        for i in range(0, N - l + 1):

            if any(replaced[i:i + l]):

                continue

            sub = text[i:i + l]

            hit_user = ub.get(sub) if ub else None

            hit_name = nb.get(sub) if nb else None

            hit_vp = vb.get(sub) if vb else None

            if hit_user is not None:

                chosen, source = hit_user, "User"

            elif hit_name and hit_vp:

                chosen, source = (hit_name, "Name") if prio_name else (hit_vp, "VP")

            elif hit_name:

                chosen, source = hit_name, "Name"

            elif hit_vp:

                chosen, source = hit_vp, "VP"

            else:

                continue

            if chosen.get("skip"):

                slots[i] = {"zh": sub, "val": "", "alts": chosen.get("alts", []), "source": "SKIP", "len": l}

            else:

                slots[i] = {"zh": sub, "val": chosen["val"], "alts": chosen.get("alts") or [chosen["val"]], "source": source, "len": l}

            for k in range(l):

                replaced[i + k] = True

    items, i = [], 0

    while i < N:

        s = slots[i]

        if s:

            items.append(s)

            i += s["len"]

        else:

            ch = text[i]

            hv = hv_dict.get(ch)

            v = hv["val"] if hv else ch

            items.append({"zh": ch, "val": v, "alts": [v], "source": "HanViet" if hv else "RAW", "len": 1})

            i += 1

    return items

_TRANS_NO_SPACE_BEFORE = set('.,:;!?…%»”』)]}，。、：；？！」》')

_TRANS_NO_SPACE_AFTER = set('([{«“『「《')

_TRANS_SENTENCE_END = set('.!?\n。！？')

def _trans_join_pretty(tokens, with_spans=False):
    """Nối token, giữ dấu câu, viết hoa sau dấu kết câu và đầu chuỗi."""
    result = ""
    spans = []
    for tok in tokens:
        val = tok["val"] if tok.get("val") is not None else tok["zh"]
        if not isinstance(val, str):
            val = str(val)
        if not val or not val.strip():
            continue
        if result:
            last, first = result[-1], val[0]
            if first not in _TRANS_NO_SPACE_BEFORE and last not in _TRANS_NO_SPACE_AFTER:
                result += " "
        # ✅ Viết hoa sau dấu câu HOẶC nếu result rỗng (đầu chuỗi)
        if (not result) or (result and result[-1] in _TRANS_SENTENCE_END):
            val = val.lstrip()
            if val and 'a' <= val[0] <= 'z':
                val = val[0].upper() + val[1:]
        start = len(result)
        result += val
        if with_spans:
            spans.append((tok["zh"], val, start, len(result)))
    
    if with_spans:
        return result.strip(), spans
    return result.strip()

_TRANS_PUNCT_MAPS = {

    "ascii": {

        "，": ",", "。": ".", "：": ":", "；": ";", "？": "?", "！": "!",

        "、": ",", "（": "(", "）": ")", "【": "[", "】": "]", "—": "-", "～": "~",

        "「": "“", "」": "”", "『": "“", "』": "”", "《": "<", "》": ">",

    },

    "vietnamese": {

        "，": ",", "。": ".", "：": ":", "；": ";", "？": "?", "！": "!",

        "、": ",", "（": "(", "）": ")",

        "「": "“", "」": "”", "『": "“", "』": "”",

        "《": "«", "》": "»",

    },

}

def _trans_map_punct(s, style="vietnamese"):

    if not s:

        return s

    m = _TRANS_PUNCT_MAPS.get(style, _TRANS_PUNCT_MAPS["vietnamese"])

    for k, v in m.items():

        s = s.replace(k, v)

    return s

def _trans_capitalize_word(w):

    return (w[0].upper() + w[1:]) if w else w

def trans_progressive_capitalizations(s):

    """'lâm phong' → ['lâm phong', 'Lâm phong', 'Lâm Phong', ...]"""

    s = (s or "").strip()

    if not s:

        return []

    words = s.split()

    outs = []

    for i in range(0, len(words) + 1):

        cand = " ".join(_trans_capitalize_word(w) if j < i else w.lower() for j, w in enumerate(words))

        if cand not in outs:

            outs.append(cand)

    return outs

class ZhViTranslator:

    """Engine dịch Trung→Việt offline (port từ translateZhToVi.js)."""

    def __init__(self):

        self.ready = False

        self.name_raw, self.vp_raw, self.hv_dict = {}, {}, {}

        self.name_idx, self.vp_idx = _TRANS_EMPTY_IDX, _TRANS_EMPTY_IDX

    def load(self, name_path, vp_path, hv_path):

        def read_json(path):

            if path and os.path.exists(path):

                with open(path, "r", encoding="utf-8") as f:

                    return json.load(f)

            return {}

        self.name_raw = _trans_normalize_dict(read_json(name_path))

        self.vp_raw = _trans_normalize_dict(read_json(vp_path))

        self.hv_dict = _trans_normalize_dict(read_json(hv_path))

        self.name_idx = _trans_build_buckets(self.name_raw)

        self.vp_idx = _trans_build_buckets(self.vp_raw)

        self.ready = True

    def stats(self):

        return f"Name {len(self.name_raw):,} | VP {len(self.vp_raw):,} | HánViệt {len(self.hv_dict):,}"

    def build_user_idx(self, name_set):

        return _trans_build_buckets(_trans_normalize_dict(name_set or {}))

    def translate_line(self, line, user_idx=None, opts=None, target="vi", with_spans=False):

        opts = dict(TRANS_DEFAULT_SETTINGS, **(opts or {}))

        user_idx = user_idx or _TRANS_EMPTY_IDX

        tokens = []

        for mode, run in _trans_split_runs(line):

            if mode == "CJK":

                if target == "hv":

                    for ch in run:

                        hv = self.hv_dict.get(ch)

                        v = hv["val"] if hv else ch

                        tokens.append({"zh": ch, "val": v, "alts": [v], "source": "HanViet"})

                else:

                    tokens.extend(_trans_longest_match(run, user_idx, self.name_idx, self.vp_idx, self.hv_dict, opts))

            else:

                tokens.append({"zh": run, "val": run, "alts": [run], "source": "TEXT"})

        if with_spans:

            out, spans = _trans_join_pretty(tokens, with_spans=True)

        else:

            out, spans = _trans_join_pretty(tokens), None

        if opts.get("punctMap"):

            out = _trans_map_punct(out, opts["punctMap"])   # map 1 ký tự → 1 ký tự nên span không lệch

        return (out, spans) if with_spans else out

    def translate_chunks(self, chunks, name_set, opts=None, progress_cb=None, target="vi", with_spans=False):

        user_idx = self.build_user_idx(name_set)

        total = max(len(chunks), 1)

        results, spans_list = [], []

        for i, c in enumerate(chunks):

            if not c.strip():

                out, spans = "", []

            elif with_spans:

                out, spans = self.translate_line(c, user_idx, opts, target, with_spans=True)

            else:

                out, spans = self.translate_line(c, user_idx, opts, target), []

            results.append(out)

            spans_list.append(spans or [])

            if progress_cb and (i % 20 == 0 or i == total - 1):

                progress_cb(f"Đang dịch {i + 1}/{total} dòng...", (i + 1) * 100 // total)

        return (results, spans_list) if with_spans else results

    def hanviet_of(self, term):

        parts = []

        for ch in term:

            hv = self.hv_dict.get(ch)

            parts.append(hv["val"] if hv else ch)

        return " ".join(p for p in parts if p).strip()

    def suggest(self, term, limit=50):

        """Gợi ý dịch cho 1 cụm (port suggestName)."""

        res = []

        if term in self.name_raw:

            e = self.name_raw[term]

            res.append({"source": "Name", "zh": term, "val": e["val"], "alts": e["alts"]})

        if term in self.vp_raw:

            e = self.vp_raw[term]

            res.append({"source": "VP", "zh": term, "val": e["val"], "alts": e["alts"]})

        if res:

            return res

        for raw, label in ((self.name_raw, "Name"), (self.vp_raw, "VP")):

            cnt = 0

            for k, e in raw.items():

                if cnt >= limit:

                    break

                if term in k or k in term:

                    res.append({"source": label, "zh": k, "val": e["val"], "alts": e["alts"]})

                    cnt += 1

        if res:

            return res[:limit]

        t = self.translate_line(term)

        return [{"source": "Fallback", "zh": term, "val": t, "alts": [t]}]

def _trans_mirror_urls(url):

    """Trả về [url gốc, mirror jsdelivr] — raw.githubusercontent hay bị chặn ở VN."""

    urls = [url] if url else []

    m = re.match(r'https://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.+)', url or "")

    if m:

        urls.append(f"https://cdn.jsdelivr.net/gh/{m.group(1)}/{m.group(2)}@{m.group(3)}/{m.group(4)}")

    return urls

def _trans_download(url, dest, timeout=90):

    """Tải file, tự thử mirror nếu nguồn chính lỗi."""

    last_err = None

    for u in _trans_mirror_urls(url):

        try:

            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})

            with urllib.request.urlopen(req, timeout=timeout) as r:

                data = r.read()

            with open(dest, "wb") as f:

                f.write(data)

            return

        except Exception as e:

            last_err = e

    raise last_err if last_err else RuntimeError("Không có URL tải.")

def trans_load_config():

    cfg = {}

    try:

        with open(TRANS_CONFIG_PATH, "r", encoding="utf-8") as f:

            cfg = json.load(f)

    except Exception:

        cfg = {}

    cfg.setdefault("nameSets", {"Mặc định": {}})

    if not cfg["nameSets"]:

        cfg["nameSets"] = {"Mặc định": {}}

    cfg.setdefault("activeNameSet", list(cfg["nameSets"].keys())[0])

    settings = dict(TRANS_DEFAULT_SETTINGS)

    settings.update(cfg.get("translator_settings", {}))

    cfg["translator_settings"] = settings

    return cfg

def trans_save_config(cfg):
    with open(TRANS_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

# ═══════════════════════════════════════════════════════════

#  DỊCH QUA SERVER (dichngay.com) — port từ app/core/translator.py

# ═══════════════════════════════════════════════════════════

import time as _time

import unicodedata as _ud

_SRV_CJK_RE = re.compile(r"[㐀-鿿]")

_SRV_INVISIBLE_RE = re.compile("[­​-‏‪-‮⁠-⁤⁦-⁯﻿]")

_SRV_INLINE_SPACE_RE = re.compile(r"[ \t\f\v]+")

def _srv_is_wordish_char(ch):

    if not ch:

        return False

    try:

        return _ud.category(ch)[0] in {"L", "N", "M"}

    except Exception:

        return False

def _srv_should_attach_quote_left(ch):

    return _srv_is_wordish_char(ch) or ch in {".", "!", "?", ",", "…"}

def srv_normalize_input(text):
    value = str(text or "")
    if not value:
        return ""
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = value.replace("\u2028", "\n").replace("\u2029", "\n")  # LINE/PARA SEPARATOR
    return _SRV_INVISIBLE_RE.sub("", value)

def _srv_normalize_straight_quote_pairs(text):

    if not text:

        return ""

    result = []

    inside_quote = False

    i, n = 0, len(text)

    while i < n:

        ch = text[i]

        if ch != '"':

            result.append(ch)

            i += 1

            continue

        if not inside_quote:

            prev = result[-1] if result else ""

            if prev and not (prev.isspace() or prev in "([{"):

                result.append(" ")

            result.append('"')

            i += 1

            while i < n and text[i] in " \t\f\v":

                i += 1

            inside_quote = True

            continue

        while result and result[-1] in " \t\f\v":

            result.pop()

        result.append('"')

        i += 1

        while i < n and text[i] in " \t\f\v":

            i += 1

        if i < n and _srv_is_wordish_char(text[i]):

            result.append(" ")

        inside_quote = False

    return "".join(result)

def srv_normalize_translated(text):

    value = srv_normalize_input(text)

    if not value:

        return ""

    value = re.sub(r'\\+\s*(["”“‘’])', r"\1", value)

    value = _srv_normalize_straight_quote_pairs(value)

    value = re.sub(r'([:;,])([“‘])', r"\1 \2", value)

    value = re.sub(r'(^|[\s([{:])([“‘])[ \t\f\v]+', r"\1\2", value, flags=re.MULTILINE)

    value = re.sub(

        r'(\S)[ \t\f\v]+([”’])',

        lambda m: f"{m.group(1)}{m.group(2)}" if _srv_should_attach_quote_left(m.group(1)) else m.group(0),

        value,

    )

    value = re.sub(

        r'([”’])([^\s\n])',

        lambda m: f'{m.group(1)} {m.group(2)}' if _srv_is_wordish_char(m.group(2)) else m.group(0),

        value,

    )

    value = re.sub(r"[ \t]+\n", "\n", value)

    value = re.sub(r"\n[ \t]+", "\n", value)

    value = _SRV_INLINE_SPACE_RE.sub(" ", value)

    value = re.sub(r"\n{3,}", "\n\n", value)

    # ✅ Capitalize từ đầu dòng
    lines = value.split('\n')
    capitalized_lines = []
    for line in lines:
        stripped = line.lstrip()
        if stripped and 'a' <= stripped[0] <= 'z':
            leading_spaces = line[:len(line) - len(stripped)]
            capitalized_lines.append(leading_spaces + stripped[0].upper() + stripped[1:])
        else:
            capitalized_lines.append(line)
    value = '\n'.join(capitalized_lines)

    return value.strip()

def _srv_build_name_replacer(name_set):

    sorted_keys = sorted(name_set.keys(), key=len, reverse=True)

    placeholder_map = {}

    def replacer(text):

        output_text = text

        for key in sorted_keys:

            if not key:

                continue

            if key in output_text:

                if key not in [v['orig'] for v in placeholder_map.values()]:

                    placeholder_id = f"__TM_NAME_{len(placeholder_map)}__"

                    placeholder_map[placeholder_id] = {'orig': key, 'viet': name_set[key]}

                found = next((pid for pid, d in placeholder_map.items() if d['orig'] == key), None)

                if found:

                    output_text = output_text.replace(key, found)

        return output_text

    return replacer, placeholder_map

def _srv_restore_names(text, placeholder_map):

    if not text or not placeholder_map:

        return text

    result = text

    for placeholder, data in placeholder_map.items():

        result = re.sub(re.escape(placeholder), f"{data['viet']} ", result)

    result = re.sub(r"\s+([,.;!?\)]|”|’|:)", r"\1", result)

    result = re.sub(r"([(\[“‘])\s+", r"\1", result)

    def _colon_spacing(match):

        next_char = match.group(1)

        prev_char = match.string[match.start() - 1] if match.start() > 0 else ""

        if next_char == "/" or (prev_char.isdigit() and next_char.isdigit()):

            return f":{next_char}"

        return f": {next_char}"

    result = re.sub(r":([^\s])", _colon_spacing, result)

    result = _SRV_INLINE_SPACE_RE.sub(" ", result)

    # ✅ Capitalize từ đầu dòng
    lines = result.split('\n')
    capitalized_lines = []
    for line in lines:
        stripped = line.lstrip()
        if stripped and 'a' <= stripped[0] <= 'z':
            leading_spaces = line[:len(line) - len(stripped)]
            capitalized_lines.append(leading_spaces + stripped[0].upper() + stripped[1:])
        else:
            capitalized_lines.append(line)
    result = '\n'.join(capitalized_lines)

    return srv_normalize_translated(result)

def _srv_split_batches(text_list, max_chars):

    batches, current, cur_len = [], [], 0

    max_chars = max(100, min(9000, int(max_chars or 4500)))

    for text in text_list:

        tl = len(text)

        if (cur_len + tl > max_chars) and current:

            batches.append(current)

            current, cur_len = [text], tl

        else:

            current.append(text)

            cur_len += tl

    if current:

        batches.append(current)

    return batches

def _srv_count_cjk(text):

    return len(_SRV_CJK_RE.findall(str(text or "")))

def _srv_looks_untranslated(source_text, translated_text):

    source = str(source_text or "").strip()

    translated = str(translated_text or "").strip()

    if not source or not translated:

        return False

    if translated.startswith("[Lỗi"):

        return False

    source_cjk = _srv_count_cjk(source)

    if source_cjk <= 0:

        return False

    translated_cjk = _srv_count_cjk(translated)

    if translated == source:

        return True

    if translated_cjk >= max(2, int(source_cjk * 0.55)):

        return True

    source_compact = re.sub(r"[\s\W_]+", "", source)

    translated_compact = re.sub(r"[\s\W_]+", "", translated)

    if source_compact and translated_compact and source_compact == translated_compact:

        return True

    return False

def _srv_decode_loose_escape(ch):

    return {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}.get(ch, ch)

def _srv_parse_loose_json_array(content):

    if isinstance(content, list):

        return [str(item or "") for item in content]

    raw = str(content or "").strip()

    if not raw:

        return []

    try:

        parsed = json.loads(raw)

        if isinstance(parsed, list):

            return [str(item or "") for item in parsed]

    except Exception:

        pass

    body = raw

    if body.startswith("["):

        body = body[1:]

    if body.endswith("]"):

        body = body[:-1]

    items = []

    i, n = 0, len(body)

    while i < n:

        while i < n and body[i] in " \t\r\n,":

            i += 1

        if i >= n:

            break

        if body[i] != '"':

            start = i

            while i < n and body[i] != ",":

                i += 1

            token = body[start:i].strip()

            if token:

                items.append(token)

            continue

        i += 1

        buf = []

        while i < n:

            ch = body[i]

            if ch == "\\":

                i += 1

                if i >= n:

                    buf.append("\\")

                    break

                next_ch = body[i]

                if next_ch == "u" and i + 4 < n:

                    hex_part = body[i + 1:i + 5]

                    try:

                        buf.append(chr(int(hex_part, 16)))

                        i += 5

                        continue

                    except Exception:

                        buf.append("u")

                        i += 1

                        continue

                buf.append(_srv_decode_loose_escape(next_ch))

                i += 1

                continue

            if ch == '"':

                j = i + 1

                while j < n and body[j] in " \t\r\n":

                    j += 1

                if j >= n or body[j] == ",":

                    i = j + 1 if j < n and body[j] == "," else j

                    break

                buf.append('"')

                i += 1

                continue

            buf.append(ch)

            i += 1

        items.append("".join(buf))

    return [str(item or "") for item in items]

_SRV_HTTP_HEADERS = {

    'Content-Type': 'application/json',

    'Referer': 'https://dichngay.com/',

    'Origin': 'https://dichngay.com',

    'Accept': 'application/json, text/plain, */*',

    'Accept-Encoding': 'identity',

    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '

                   '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'),

}

def _srv_urlopen(req, timeout):

    """urlopen kèm fallback khi máy thiếu chứng chỉ SSL."""

    import ssl

    try:

        return urllib.request.urlopen(req, timeout=timeout)

    except urllib.error.URLError as e:

        reason = getattr(e, "reason", None)

        if isinstance(reason, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in str(e):

            ctx = ssl._create_unverified_context()

            return urllib.request.urlopen(req, timeout=timeout, context=ctx)

        raise

def _srv_post_batch(content_array, server_url, target_lang='vi',

                    retry_count=2, retry_backoff_ms=700, timeout_sec=60):

    payload = {'content': json.dumps(content_array, ensure_ascii=False), 'tl': target_lang}

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    headers = dict(_SRV_HTTP_HEADERS)

    attempts = max(1, int(retry_count or 0) + 1)

    last_request_error = None

    for attempt in range(attempts):

        try:

            req = urllib.request.Request(server_url, data=body, headers=headers, method="POST")

            with _srv_urlopen(req, timeout=max(10, int(timeout_sec or 60))) as resp:

                json_response = json.loads(resp.read().decode("utf-8", errors="replace"))

            translated_content = (json_response.get('data') or {}).get('content')

            if translated_content in (None, ""):

                translated_content = json_response.get('translatedText', [])

            parsed = [srv_normalize_translated(item) for item in _srv_parse_loose_json_array(translated_content)]

            if len(parsed) == len(content_array):

                return parsed

            if parsed:

                return parsed

        except Exception as e:

            last_request_error = e

        if attempt < attempts - 1:

            _time.sleep(max(0.1, int(retry_backoff_ms or 700) / 1000.0))

    if last_request_error is not None:

        return [f"[Lỗi mạng: {last_request_error}]"] * len(content_array)

    return ["[Lỗi server response]"] * len(content_array)

def _srv_needs_retry(source_text, translated_text):

    source = srv_normalize_input(source_text).strip()

    translated = srv_normalize_translated(translated_text).strip()

    if not source:

        return False

    if (not translated) or translated.startswith("[Lỗi"):

        return True

    return _srv_looks_untranslated(source, translated)

def _srv_translate_single_final(text, server_url, **kw):

    translated = _srv_post_batch([text], server_url, **kw)

    candidate = translated[0] if translated else ""

    if _srv_needs_retry(text, candidate):

        return srv_normalize_translated(text)

    return srv_normalize_translated(candidate)

def _srv_translate_failed_batch_final(content_array, server_url, **kw):

    if not content_array:

        return []

    translated = _srv_post_batch(content_array, server_url, **kw)

    if len(translated) == len(content_array):

        return [

            srv_normalize_translated(item) if not _srv_needs_retry(source, item)

            else _srv_translate_single_final(source, server_url, **kw)

            for source, item in zip(content_array, translated)

        ]

    if len(content_array) <= 1:

        return [_srv_translate_single_final(content_array[0], server_url, **kw)]

    mid = max(1, len(content_array) // 2)

    return (_srv_translate_failed_batch_final(content_array[:mid], server_url, **kw)

            + _srv_translate_failed_batch_final(content_array[mid:], server_url, **kw))

def _srv_retry_suspicious(source_texts, server_url, max_chars=4500, **kw):

    if not source_texts:

        return []

    retry_chars = max(300, min(1800, int(max_chars or 4500)))

    batches = _srv_split_batches(source_texts, retry_chars)

    results = []

    for batch in batches:

        translated = _srv_post_batch(batch, server_url, **kw)

        if len(translated) != len(batch):

            results.extend(_srv_translate_failed_batch_final(batch, server_url, **kw))

            continue

        for source_text, translated_text in zip(batch, translated):

            if _srv_needs_retry(source_text, translated_text):

                results.append(_srv_translate_single_final(source_text, server_url, **kw))

            else:

                results.append(srv_normalize_translated(translated_text))

    return results

def _srv_translate_batch_resilient(content_array, server_url, **kw):

    if not content_array:

        return []

    translated = _srv_post_batch(content_array, server_url, **kw)

    if len(translated) != len(content_array):

        return _srv_translate_failed_batch_final(content_array, server_url, **kw)

    resolved = [srv_normalize_translated(item) for item in translated]

    suspicious = [i for i, (s, t) in enumerate(zip(content_array, resolved)) if _srv_needs_retry(s, t)]

    if not suspicious:

        return resolved

    retried = _srv_retry_suspicious(

        [content_array[i] for i in suspicious], server_url,

        max_chars=max(300, min(9000, int(sum(len(t or "") for t in content_array) or 4500))), **kw)

    for i, candidate in zip(suspicious, retried):

        resolved[i] = srv_normalize_translated(candidate)

    return resolved

def srv_translate_chunks(chunks, name_set, settings, update_progress_callback=None, target_lang='vi'):

    """Dịch qua server dichngay.com — giữ nguyên hành vi app gốc:

    thay name bằng placeholder → dịch theo gói → khôi phục name → chuẩn hoá."""

    if not chunks:

        return []

    server_url = settings.get('serverUrl') or 'https://dichngay.com/translate/text'

    max_chars = max(500, min(9000, int(settings.get('maxChars', 4500) or 4500)))

    delay_ms = settings.get('delayMs', 400)

    kw = dict(

        target_lang=target_lang or 'vi',

        retry_count=settings.get('retryCount', 2),

        retry_backoff_ms=settings.get('retryBackoffMs', 700),

        timeout_sec=settings.get('timeoutSec', 60),

    )

    if update_progress_callback:

        update_progress_callback("Chuẩn bị và thay thế tên...", 0)

    replacer, placeholder_map = _srv_build_name_replacer(name_set or {})

    texts = [replacer(srv_normalize_input(chunk)) for chunk in chunks]

    batches = _srv_split_batches(texts, max_chars)

    total_batches = len(batches)

    all_translated = []

    for i, batch in enumerate(batches):

        if update_progress_callback:

            update_progress_callback(f"Đang dịch gói {i + 1}/{total_batches}...", int((i / total_batches) * 100))

        all_translated.extend(_srv_translate_batch_resilient(batch, server_url, **kw))

        if i < total_batches - 1:

            _time.sleep((delay_ms or 0) / 1000.0)

    if len(all_translated) < len(texts):

        all_translated.extend(texts[len(all_translated):])

    elif len(all_translated) > len(texts):

        all_translated = all_translated[:len(texts)]

    if update_progress_callback:

        update_progress_callback("Khôi phục tên và hoàn tất...", 95)

    final_results = [srv_normalize_translated(_srv_restore_names(t, placeholder_map)) for t in all_translated]

    if update_progress_callback:

        update_progress_callback("Hoàn tất!", 100)

    return final_results

# ═══════════════════════════════════════════════════════════
#  XUẤT KẾT QUẢ "DỊCH NAME" VÀO BỘ NAME (tab Quản lý Name)
# ═══════════════════════════════════════════════════════════

def plan_name_set_merge(existing, pairs, overwrite=False):
    """Lập kế hoạch thêm các cặp (Trung, Việt) vào một bộ name — KHÔNG sửa dữ liệu thật.

    existing : dict {trung: việt} của bộ đích.
    pairs    : iterable (trung, việt).
    overwrite: True -> name đã có nhưng khác nghĩa sẽ bị ghi đè; False -> giữ nghĩa cũ.

    Trả về (items, counts, dup):
      items  : list dict(zh, new, old, status, apply). status ∈ new | same | diff | skip
                 new  = chưa có trong bộ        same = đã có, giống hệt
                 diff = đã có, khác nghĩa        skip = chưa có nghĩa Việt (rỗng / còn chữ Hán)
      counts : Counter đếm theo status
      dup    : số dòng bị gộp vì trùng tiếng Trung trong cùng lô (lấy dòng cuối cùng)
    """
    seen, n_valid = {}, 0
    for zh, val in pairs:
        zh, val = str(zh or "").strip(), str(val or "").strip()
        if not zh:
            continue
        n_valid += 1
        seen[zh] = val
    items, counts = [], Counter()
    for zh, val in seen.items():
        old = existing.get(zh)
        if not val or val == zh or any(_trans_is_cjk(c) for c in val):
            st = "skip"
        elif old is None:
            st = "new"
        elif str(old) == val:
            st = "same"
        else:
            st = "diff"
        items.append({"zh": zh, "new": val, "old": None if old is None else str(old),
                      "status": st, "apply": st == "new" or (st == "diff" and overwrite)})
        counts[st] += 1
    return items, counts, n_valid - len(seen)


def name_capitalize_auto(text):
    """Viết hoa chữ cái đầu của 3 hoặc 4 từ đầu, tùy độ dài của tên.

    • Tên từ 4 từ trở lên  → viết hoa 4 từ đầu   (vd. 'thượng quan uyển nhi' → 'Thượng Quan Uyển Nhi')
    • Tên ngắn hơn         → viết hoa 3 từ đầu   (tên 2–3 từ được viết hoa hết: 'lâm động' → 'Lâm Động')
    """
    words = (text or "").strip().split()
    n = 4 if len(words) >= 4 else 3
    for i in range(min(n, len(words))):
        words[i] = _trans_capitalize_word(words[i])
    return " ".join(words)


class NameTranslateDialog(tk.Toplevel):
    """Dịch name từ kết quả 'Lọc tên nhân vật' rồi thêm vào một bộ tên (Quản lý Name).

    Luồng: mở cửa sổ → tự dịch (Hán Việt + Việt offline, viết hoa 3–4 chữ) → xem/sửa/xóa dòng
           → chọn bộ tên đích → “Thêm vào bộ tên”.
    Bản dịch KHÔNG phụ thuộc bộ tên đích, nên dòng nào đã có sẵn trong bộ sẽ hiện rõ:
    trùng nghĩa / khác nghĩa (mặc định giữ nghĩa cũ để không đè name bạn đã chỉnh tay).
    """

    def __init__(self, names_tab, tr_tab, rows, source_note=""):
        super().__init__(names_tab.winfo_toplevel())
        self.names_tab = names_tab
        self.tr = tr_tab                    # TabTranslate: giữ engine dịch + bộ tên + cấu hình
        self.rows = {}                      # iid -> {"zh","freq","hv","vi"}   (hv/vi = None khi chưa dịch)
        self._items = []
        self._closed = False
        self._translating = False
        self._after_id = None
        self.title("Dịch name → thêm vào bộ tên")
        self.geometry("1000x700")
        self.minsize(860, 580)
        self.transient(names_tab.winfo_toplevel())
        self._build(source_note)
        self.protocol("WM_DELETE_WINDOW", self._close)
        for zh, freq, _group in rows:
            self._insert_row(zh, freq)
        self._recompute()
        self._start_translate()
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass

    # ── giao diện ──────────────────────────────────────────────────────────
    def _build(self, source_note):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)
        sets = self.tr.app_config["nameSets"]

        head = ttk.Frame(self)
        head.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 2))
        head.columnconfigure(0, weight=1)
        ttk.Label(head, text=f"Nguồn: {source_note}" if source_note else "Nguồn: kết quả lọc tên",
                  style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        self.var_info = tk.StringVar()
        ttk.Label(head, textvariable=self.var_info, style="Ok.TLabel").grid(row=1, column=0, sticky="w")

        f1 = ttk.LabelFrame(self, text="Bộ tên đích (trong Quản lý Name)")
        f1.grid(row=1, column=0, sticky="ew", padx=10, pady=4)
        f1.columnconfigure(0, weight=1)
        self.combo = ttk.Combobox(f1, state="readonly", values=list(sets.keys()))
        active = self.tr.name_set_combo.get()
        self.combo.set(active if active in sets else next(iter(sets)))
        self.combo.grid(row=0, column=0, sticky="ew", padx=(8, 6), pady=8)
        self.combo.bind("<<ComboboxSelected>>", lambda e: self._recompute())
        ttk.Button(f1, text="＋ Bộ mới…", command=self._new_set).grid(row=0, column=1, padx=(0, 8))
        self.lbl_set = ttk.Label(f1, style="Muted.TLabel")
        self.lbl_set.grid(row=1, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 6))

        f2 = ttk.LabelFrame(self, text="Tùy chọn")
        f2.grid(row=2, column=0, sticky="ew", padx=10, pady=4)
        self.var_src = tk.StringVar(value="hv")
        self.var_scope = tk.StringVar(value="all")
        self.var_policy = tk.StringVar(value="keep")
        self.var_open = tk.BooleanVar(value=False)

        def add_row(r, label, options):
            ttk.Label(f2, text=label).grid(row=r, column=0, sticky="w", padx=(8, 10), pady=3)
            widgets = []
            for c, (text, var, value) in enumerate(options, start=1):
                rb = ttk.Radiobutton(f2, text=text, variable=var, value=value, command=self._recompute)
                rb.grid(row=r, column=c, sticky="w", padx=(0, 14))
                widgets.append(rb)
            return widgets

        add_row(0, "Nghĩa Việt lấy từ:", [("Hán Việt", self.var_src, "hv"),
                                          ("Việt offline", self.var_src, "vi")])
        _, self.rb_sel = add_row(1, "Phạm vi thêm:", [("Tất cả các dòng", self.var_scope, "all"),
                                                     ("Chỉ dòng đang chọn (0)", self.var_scope, "sel")])
        add_row(2, "Name đã có nhưng khác nghĩa:", [("Giữ nghĩa cũ", self.var_policy, "keep"),
                                                   ("Ghi đè bằng nghĩa mới", self.var_policy, "over")])

        f3 = ttk.LabelFrame(self, text="Kết quả dịch (viết hoa 3–4 chữ tự động • bấm đúp để sửa • chuột phải: sửa/xóa)")
        f3.grid(row=3, column=0, sticky="nsew", padx=10, pady=4)
        f3.rowconfigure(1, weight=1)
        f3.columnconfigure(0, weight=1)
        tools = ttk.Frame(f3)
        tools.grid(row=0, column=0, columnspan=2, sticky="ew", padx=6, pady=(6, 0))
        ttk.Button(tools, text="＋ Thêm tên…", command=self._add_names).pack(side=tk.LEFT)
        ttk.Button(tools, text="🗑 Xóa dòng đã chọn", style="Pink.TButton",
                   command=lambda: self._delete_rows(self.tree.selection())).pack(side=tk.LEFT, padx=6)

        cols = ("zh", "freq", "hv", "vi", "st")
        self.tree = ttk.Treeview(f3, columns=cols, show="headings", selectmode="extended")
        for col, text, width in (("zh", "Tiếng Trung", 115), ("freq", "Số lần", 65), ("hv", "Hán Việt", 190),
                                 ("vi", "Việt offline", 190), ("st", "Trạng thái so với bộ tên", 300)):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="w", stretch=(col == "st"))
        self.tree.grid(row=1, column=0, sticky="nsew", padx=(6, 0), pady=6)
        sb = ttk.Scrollbar(f3, orient=tk.VERTICAL, command=self.tree.yview)
        sb.grid(row=1, column=1, sticky="ns", pady=6)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.tag_configure("new", background=THEME["g100"])
        self.tree.tag_configure("diff", background=THEME["p100"])
        for t in ("same", "skip", "out"):
            self.tree.tag_configure(t, foreground=THEME["muted"])
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Button-3>", self._on_context_menu)
        self.tree.bind("<Delete>", lambda e: self._delete_rows(self.tree.selection()))
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        self.lbl_sum = ttk.Label(self, style="Ok.TLabel")
        self.lbl_sum.grid(row=4, column=0, sticky="w", padx=12, pady=(2, 0))

        bar = ttk.Frame(self)
        bar.grid(row=5, column=0, sticky="ew", padx=10, pady=10)
        ttk.Button(bar, text="💾 Xuất .txt", command=self._export_file).pack(side=tk.LEFT)
        ttk.Button(bar, text="📋 Sao chép", command=self._copy).pack(side=tk.LEFT, padx=6)
        ttk.Checkbutton(bar, text="Mở Quản lý Name sau khi thêm",
                        variable=self.var_open).pack(side=tk.LEFT, padx=(14, 0))
        self.btn_ok = ttk.Button(bar, text="✔ Thêm vào bộ tên", style="Accent.TButton", command=self._apply)
        self.btn_ok.pack(side=tk.RIGHT)
        ttk.Button(bar, text="Hủy", command=self._close).pack(side=tk.RIGHT, padx=8)

    # ── dữ liệu dòng ───────────────────────────────────────────────────────
    def _insert_row(self, zh, freq="—"):
        iid = self.tree.insert("", tk.END, values=(zh, freq, "…", "…", ""))
        self.rows[iid] = {"zh": zh, "freq": freq, "hv": None, "vi": None}
        return iid

    def _col(self):
        return "hv" if self.var_src.get() == "hv" else "vi"

    def _in_scope(self):
        iids = list(self.tree.get_children())
        if self.var_scope.get() == "sel":
            chosen = set(self.tree.selection())
            return [i for i in iids if i in chosen]
        return iids

    def _delete_rows(self, iids):
        iids = list(iids)
        if not iids:
            messagebox.showinfo("Thông báo", "Chọn các dòng cần xóa trong bảng.", parent=self)
            return
        for iid in iids:
            self.tree.delete(iid)
            self.rows.pop(iid, None)
        self.var_info.set(f"Đã xóa {len(iids)} dòng.")
        self._recompute()

    # ── dịch tự động ───────────────────────────────────────────────────────
    def _start_translate(self):
        if self._closed or self._translating:
            return
        todo = [(iid, r["zh"]) for iid, r in self.rows.items() if r["hv"] is None]
        if not todo:
            return
        eng = self.tr.engine
        if not eng.ready:            # từ điển nạp nền lúc khởi động -> đợi rồi tự dịch
            self.var_info.set("⏳ Đang đợi từ điển nạp xong… sẽ tự dịch khi sẵn sàng.")
            self._after_id = self.after(600, self._start_translate)
            return
        settings = self.tr._collect_runtime_settings()       # đọc biến Tk ở luồng chính
        self._translating = True
        self.var_info.set(f"Đang dịch {len(todo):,} name…")

        def worker():
            out, err = {}, None
            try:
                for iid, zh in todo:
                    hv = eng.translate_line(zh, None, settings, target="hv")
                    vi = eng.translate_line(zh, None, settings, target="vi")
                    out[iid] = (name_capitalize_auto(hv), name_capitalize_auto(vi))
            except Exception as exc:                          # noqa: BLE001
                err = exc
            try:
                self.after(0, lambda: self._translated(out, err))
            except (tk.TclError, RuntimeError):               # cửa sổ đã đóng
                pass
        threading.Thread(target=worker, daemon=True).start()

    def _translated(self, out, err):
        self._translating = False
        if self._closed:
            return
        if err is not None:
            self.var_info.set(f"Lỗi khi dịch: {err}")
            return
        for iid, (hv, vi) in out.items():
            r = self.rows.get(iid)
            if r is None:
                continue
            r["hv"], r["vi"] = hv, vi
            self.tree.set(iid, "hv", hv)
            self.tree.set(iid, "vi", vi)
        self.var_info.set("✔ Đã dịch xong — kiểm tra, sửa nếu cần, chọn bộ tên rồi bấm “Thêm vào bộ tên”.")
        self._recompute()
        self._start_translate()       # tên vừa được thêm tay trong lúc đang dịch

    # ── so sánh với bộ tên & hiển thị ──────────────────────────────────────
    def _recompute(self):
        if self._closed:
            return
        target = self.combo.get()
        existing = self.tr.app_config["nameSets"].get(target, {}) or {}
        overwrite = self.var_policy.get() == "over"
        col = self._col()
        scope = self._in_scope()
        scope_set = set(scope)
        pairs = [(self.rows[i]["zh"], self.rows[i][col] or "") for i in scope]
        self._items, counts, dup = plan_name_set_merge(existing, pairs, overwrite)
        by_zh = {it["zh"]: it for it in self._items}
        last = {self.rows[i]["zh"].strip(): i for i in scope}

        for iid in self.tree.get_children():
            r = self.rows[iid]
            if iid not in scope_set:
                text, tag = "— ngoài phạm vi (không thêm)", "out"
            elif r[col] is None:
                text, tag = "⏳ Đang dịch…", "skip"
            else:
                zh = r["zh"].strip()
                it = by_zh.get(zh)
                if it is None:
                    text, tag = "✖ Thiếu tiếng Trung", "skip"
                elif last.get(zh) != iid:
                    text, tag = "⋯ Trùng dòng khác (gộp)", "same"
                elif it["status"] == "new":
                    text, tag = "🆕 Mới", "new"
                elif it["status"] == "same":
                    text, tag = "＝ Đã có, giống nhau", "same"
                elif it["status"] == "diff":
                    text = f"⚠ Khác — cũ: {it['old']}  →  " + ("sẽ ghi đè" if overwrite else "giữ nghĩa cũ")
                    tag = "diff"
                else:
                    text, tag = "✖ Chưa có nghĩa Việt (bỏ qua)", "skip"
            self.tree.set(iid, "st", text)
            self.tree.item(iid, tags=(tag,))

        self.lbl_set.config(text=f"Bộ “{target}” hiện có {len(existing):,} name.")
        if self.var_scope.get() == "sel" and not scope:
            self.lbl_sum.config(text="Chưa chọn dòng nào trong bảng.")
        else:
            parts = [f"{counts['new']} mới", f"{counts['same']} trùng", f"{counts['diff']} khác nghĩa",
                     f"{counts['skip']} bỏ qua"]
            if dup:
                parts.append(f"{dup} dòng trùng đã gộp")
            self.lbl_sum.config(text=" • ".join(parts))
        n_apply = sum(1 for it in self._items if it["apply"])
        self.btn_ok.config(text=f"✔ Thêm {n_apply:,} name vào bộ tên", state="normal" if n_apply else "disabled")

    def _on_select(self, _e=None):
        self.rb_sel.config(text=f"Chỉ dòng đang chọn ({len(self.tree.selection())})")
        if self.var_scope.get() == "sel":
            self._recompute()

    # ── sửa / thêm dòng ────────────────────────────────────────────────────
    def _on_double_click(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
            self._edit_row(iid)

    def _on_context_menu(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        if iid not in self.tree.selection():
            self.tree.selection_set(iid)
        menu = tk.Menu(self.tree, tearoff=0)
        menu.add_command(label="✏ Sửa dòng này…", command=lambda: self._edit_row(iid))
        menu.add_command(label="🗑 Xóa các dòng đã chọn", command=lambda: self._delete_rows(self.tree.selection()))
        menu.tk_popup(event.x_root, event.y_root)

    def _edit_row(self, iid):
        r = self.rows.get(iid)
        if r is None:
            return
        win = tk.Toplevel(self)
        win.title("Sửa name")
        win.geometry("460x230")
        win.resizable(False, False)
        win.transient(self)
        frm = ttk.Frame(win, padding=15)
        frm.pack(fill=tk.BOTH, expand=True)
        frm.columnconfigure(1, weight=1)
        entries = {}
        for i, (key, label) in enumerate((("zh", "Tiếng Trung:"), ("hv", "Hán Việt:"), ("vi", "Việt offline:"))):
            ttk.Label(frm, text=label, font=FONT_BOLD).grid(row=i, column=0, sticky="w", pady=6)
            e = ttk.Entry(frm, font=FONT_TEXT)
            e.insert(0, r[key] or "")
            e.grid(row=i, column=1, sticky="ew", pady=6)
            entries[key] = e

        def on_save(_e=None):
            zh, hv, vi = (entries[k].get().strip() for k in ("zh", "hv", "vi"))
            if not zh or not hv:
                messagebox.showwarning("Không hợp lệ", "Tiếng Trung và Hán Việt không được để trống.", parent=win)
                return
            r.update(zh=zh, hv=hv, vi=vi)
            self.tree.item(iid, values=(zh, r["freq"], hv, vi, ""))
            win.destroy()
            self._recompute()

        btns = ttk.Frame(frm)
        btns.grid(row=3, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(btns, text="Lưu", style="Accent.TButton", command=on_save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Hủy", command=win.destroy).pack(side=tk.LEFT)
        win.bind("<Return>", on_save)
        entries["hv"].focus_set()

    def _add_names(self):
        """Nhập thêm tên tiếng Trung (mỗi dòng một tên) — được dịch tự động như các tên đã lọc."""
        win = tk.Toplevel(self)
        win.title("Thêm tên tiếng Trung")
        win.geometry("420x360")
        win.transient(self)
        ttk.Label(win, text="Nhập mỗi tên tiếng Trung trên một dòng:").pack(anchor="w", padx=12, pady=(12, 4))
        box = scrolledtext.ScrolledText(win, height=10, wrap=tk.WORD, font=FONT_TEXT)
        box.pack(fill=tk.BOTH, expand=True, padx=12)

        def do_add():
            have = {r["zh"] for r in self.rows.values()}
            added = 0
            for line in box.get("1.0", "end-1c").splitlines():
                zh = line.strip()
                if zh and zh not in have:
                    self._insert_row(zh)
                    have.add(zh)
                    added += 1
            win.destroy()
            if added:
                self.var_info.set(f"Đã thêm {added} tên, đang dịch…")
                self._recompute()
                self._start_translate()

        bar = ttk.Frame(win)
        bar.pack(fill=tk.X, padx=12, pady=10)
        ttk.Button(bar, text="Thêm & dịch", style="Accent.TButton", command=do_add).pack(side=tk.RIGHT)
        ttk.Button(bar, text="Hủy", command=win.destroy).pack(side=tk.RIGHT, padx=8)
        box.focus_set()

    def _new_set(self):
        name = simpledialog.askstring("Tạo bộ mới", "Nhập tên cho bộ mới:", parent=self)
        name = (name or "").strip()
        if not name:
            return
        sets = self.tr.app_config["nameSets"]
        if name in sets:
            messagebox.showerror("Lỗi", "Tên bộ đã tồn tại.", parent=self)
            return
        sets[name] = {}
        self.tr.name_set_combo["values"] = list(sets.keys())
        self.combo["values"] = list(sets.keys())
        self.combo.set(name)
        self.tr.save_config()
        self._recompute()

    # ── xuất file / sao chép ───────────────────────────────────────────────
    def _export_text(self):
        col, lines = self._col(), []
        for iid in self._in_scope():
            r = self.rows[iid]
            zh, val = r["zh"].strip(), (r[col] or "").strip()
            if zh and val:
                lines.append(f"{zh}={val}")
        return "\n".join(lines)

    def _copy(self):
        content = self._export_text()
        if not content:
            messagebox.showinfo("Thông báo", "Chưa có kết quả để sao chép.", parent=self)
            return
        self.clipboard_clear()
        self.clipboard_append(content)
        self.var_info.set(f"Đã sao chép {content.count(chr(10)) + 1:,} dòng Trung=Việt.")

    def _export_file(self):
        content = self._export_text()
        if not content:
            messagebox.showinfo("Thông báo", "Chưa có kết quả để xuất.", parent=self)
            return
        path = filedialog.asksaveasfilename(
            title="Xuất Name: Trung=Việt", defaultextension=".txt",
            filetypes=[("Text file", "*.txt"), ("All files", "*.*")], parent=self)
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)            # chỉ hai cột, đúng dấu '=' để nhập lại vào Quản lý Name
        except Exception as exc:            # noqa: BLE001
            messagebox.showerror("Lỗi", f"Không thể xuất file: {exc}", parent=self)
            return
        self.var_info.set(f"Đã xuất {content.count(chr(10)) + 1:,} dòng ra file.")

    # ── thêm vào bộ tên ────────────────────────────────────────────────────
    def _apply(self):
        todo = [it for it in self._items if it["apply"]]
        if not todo:
            return
        tr, target = self.tr, self.combo.get()
        bucket = tr.app_config["nameSets"].setdefault(target, {})
        added = sum(1 for it in todo if it["status"] == "new")
        replaced = len(todo) - added
        for it in todo:
            bucket[it["zh"]] = it["new"]
        tr.save_config()

        keys = [it["zh"] for it in todo]
        if self.var_open.get():
            tr.name_set_combo.set(target)
            tr._on_set_changed()                       # lưu bộ đang dùng + làm mới danh sách
            for t in tr.left_nb.tabs():
                if tr.left_nb.tab(t, "text") == "Quản lý Name":
                    tr.left_nb.select(t)
                    break
            try:
                self.names_tab.master.select(tr)       # chuyển sang tab Dịch Trung → Việt
            except tk.TclError:
                pass
        elif target == tr.name_set_combo.get():
            tr._refresh_name_list()
        if target == tr.name_set_combo.get():
            tr._smart_retranslate(keys)                # dịch lại các đoạn có chứa name mới

        msg = f"Đã thêm {added:,} name" + (f", ghi đè {replaced:,}" if replaced else "") + f" vào bộ “{target}”."
        tr.status_label.config(text=msg)
        self.names_tab.status_var.set(msg)
        self._close()
        messagebox.showinfo("Thành công", msg, parent=self.names_tab)

    def _close(self):
        if self._closed:
            return
        self._closed = True
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except tk.TclError:
                pass
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()


class TabTranslate(ttk.Frame):

    """Tab dịch thuật + quản lý name-set (dựa trên translate_tab_mixin.py)."""

    def __init__(self, parent):

        super().__init__(parent)

        self.app_config = trans_load_config()

        self.engine = ZhViTranslator()

        self.is_translating = False

        self._last_translation_lang = "vi"

        self._build()

        self._load_dicts_async()

    # ── cấu hình ──────────────────────────────────────────

    def save_config(self):
        try:
            trans_save_config(self.app_config)
        except Exception as e:
            messagebox.showerror(
                "Không lưu được cấu hình",
                f"Không ghi được file cấu hình:\n{TRANS_CONFIG_PATH}\n\n"
                f"Lỗi: {e}\n\n"
                "Nguyên nhân thường gặp:\n"
                "• Đang chạy EXE trực tiếp trong file .zip (chưa giải nén)\n"
                "• EXE đặt trong thư mục cần quyền Admin (Program Files...)\n\n"
                "→ Hãy giải nén EXE ra thư mục thường (Desktop/Documents) rồi thử lại.",
                parent=self,
            )

    def _settings(self):

        return self.app_config["translator_settings"]

    def _collect_runtime_settings(self):

        s = self._settings()

        s["nameUrl"] = self.adv_name_url.get().strip()

        s["vpUrl"] = self.adv_vp_url.get().strip()

        s["hvUrl"] = self.adv_hv_url.get().strip()

        try:

            s["maxMatchLen"] = int(self.adv_max_match.get())

        except Exception:

            s["maxMatchLen"] = TRANS_DEFAULT_SETTINGS["maxMatchLen"]

        s["priorityNameFirst"] = bool(self.adv_prio_name.get())

        if hasattr(self, "adv_server_url"):

            s["serverUrl"] = self.adv_server_url.get().strip()

            try:

                s["delayMs"] = int(self.adv_delay.get())

            except Exception:

                s["delayMs"] = TRANS_DEFAULT_SETTINGS["delayMs"]

            try:

                s["maxChars"] = int(self.adv_max_chars.get())

            except Exception:

                s["maxChars"] = TRANS_DEFAULT_SETTINGS["maxChars"]

        self.save_config()

        return dict(s)

    def _active_name_set(self):

        set_name = self.name_set_combo.get()

        return dict(self.app_config.get("nameSets", {}).get(set_name, {}) or {})

    # ── UI ────────────────────────────────────────────────

    def _build(self):

        self.rowconfigure(0, weight=1)

        self.columnconfigure(0, weight=1)

        main_paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)

        main_paned.grid(row=0, column=0, sticky="nsew", padx=6, pady=(6, 0))

        left_frame = ttk.Frame(main_paned)

        main_paned.add(left_frame, weight=1)

        left_frame.rowconfigure(0, weight=1)

        left_frame.columnconfigure(0, weight=1)

        left_nb = ttk.Notebook(left_frame)

        left_nb.grid(row=0, column=0, sticky="nsew")

        self.left_nb = left_nb

        input_tab = ttk.Frame(left_nb, padding=5)

        left_nb.add(input_tab, text="Dịch QT")

        input_tab.rowconfigure(0, weight=1)

        input_tab.columnconfigure(0, weight=1)
        

        self.input_text = tk.Text(input_tab, wrap=tk.WORD, font=("Segoe UI", 11), undo=True, foreground="#1a1a1a")

        self.input_text.grid(row=0, column=0, sticky="nsew")

        self.input_text.bind("<Button-3>", self._show_input_context_menu)

        name_tab = ttk.Frame(left_nb, padding=8)

        left_nb.add(name_tab, text="Quản lý Name")

        self._build_name_manager(name_tab)

        adv_tab = ttk.Frame(left_nb, padding=8)

        left_nb.add(adv_tab, text="Nâng cao")

        self._build_advanced(adv_tab)


        right_frame = ttk.LabelFrame(main_paned, text="Kết quả dịch", padding=6)

        main_paned.add(right_frame, weight=1)

        right_frame.rowconfigure(0, weight=1)

        right_frame.columnconfigure(0, weight=1)

        self.output_text = scrolledtext.ScrolledText(
            right_frame, 
            wrap=tk.WORD, 
            state="disabled",
            font=("Segoe UI", 11),  # ← Thay từ "Consolas" 10
            background="#f0fff0",
            foreground="#1a1a1a",  # ← Thêm màu chữ tối hơn
            insertbackground="#0066cc"
        )

        self.output_text.grid(row=0, column=0, sticky="nsew")

        self.output_text.chunk_data = {}

        self.output_text.bind("<Button-3>", self._show_output_context_menu)

        ctrl = ttk.Frame(self, padding=(6, 8))

        ctrl.grid(row=1, column=0, sticky="ew")

        ctrl.columnconfigure(3, weight=1)

        ttk.Button(ctrl, text="📂 Tải file...", command=self._load_file).grid(row=0, column=0)

        ttk.Button(ctrl, text="📋 Dán", command=self._paste_input).grid(row=0, column=1, padx=4)

        ttk.Button(ctrl, style="Pink.TButton", text="🗑 Xóa hết", command=self._clear_active_input).grid(row=0, column=2)

        self.progress_bar = ttk.Progressbar(ctrl, orient="horizontal", mode="determinate")

        self.progress_bar.grid(row=0, column=3, sticky="ew", padx=10)

        self.progress_bar.grid_remove()

        ttk.Button(ctrl, text="▶ Việt (offline)", style="Accent.TButton", command=lambda: self._start_translation("vi")).grid(row=0, column=4, padx=(0, 4))

        ttk.Button(ctrl, text="☁ Việt (server)", command=lambda: self._start_translation("vi-server")).grid(row=0, column=5, padx=(0, 4))

        ttk.Button(ctrl, text="▶ Hán Việt", command=lambda: self._start_translation("hv")).grid(row=0, column=6, padx=(0, 4))

        ttk.Button(ctrl, text="📋 Sao chép", command=self._copy_result).grid(row=0, column=7, padx=(0, 4))

        ttk.Button(ctrl, text="💾 Xuất kết quả...", command=self._export_result).grid(row=0, column=8, padx=(0, 8))

        self.status_label = ttk.Label(ctrl, text="Đang khởi động...", foreground="#555")

        self.status_label.grid(row=0, column=9, sticky="e")

    # ── nạp / tải từ điển ─────────────────────────────────

    def _set_status(self, msg):

        self.after(0, lambda: self.status_label.config(text=msg))

    def _load_dicts_async(self, force_download=False):

        def worker():

            try:

                os.makedirs(TRANS_DICT_DIR, exist_ok=True)

                s = self._settings()

                files = [("Name.json", s.get("nameUrl")), ("VP.json", s.get("vpUrl")), ("HanViet.json", s.get("hvUrl"))]

                for fname, url in files:

                    path = os.path.join(TRANS_DICT_DIR, fname)

                    if (force_download or not os.path.exists(path)) and url:

                        self._set_status(f"Đang tải {fname}...")

                        try:

                            _trans_download(url, path)

                        except Exception as e:

                            self._set_status(f"Không tải được {fname}: {e}")

                self._set_status("Đang nạp từ điển...")

                self.engine.load(

                    os.path.join(TRANS_DICT_DIR, "Name.json"),

                    os.path.join(TRANS_DICT_DIR, "VP.json"),

                    os.path.join(TRANS_DICT_DIR, "HanViet.json"),

                )

                missing = [f for f in ("Name.json", "VP.json", "HanViet.json")

                           if not os.path.exists(os.path.join(TRANS_DICT_DIR, f))]

                msg = f"Sẵn sàng. {self.engine.stats()}"

                if missing:

                    msg += f"  (thiếu: {', '.join(missing)})"

                self._set_status(msg)

                self.after(0, self._refresh_dict_stats)

                if missing and not getattr(self, "_warned_missing_dict", False):

                    self._warned_missing_dict = True

                    def warn():

                        messagebox.showwarning(

                            "Thiếu từ điển",

                            f"Chưa có file: {', '.join(missing)}\n\n"

                            "Đặc biệt VP.json (VietPhrase) là từ điển cụm từ chính — "

                            "thiếu nó thì nút 'Việt' chỉ cho kết quả như Hán Việt.\n\n"

                            f"Cách khắc phục:\n"

                            f"  1. Chép file vào thư mục:\n      {TRANS_DICT_DIR}\n"

                            "  2. Hoặc vào tab 'Nâng cao' → '⬇ Tải lại từ điển từ web'\n"

                            "  3. Rồi bấm '🔄 Nạp lại từ điển'.",

                            parent=self)

                    self.after(0, warn)

            except Exception as e:

                self._set_status(f"Lỗi nạp từ điển: {e}")

        threading.Thread(target=worker, daemon=True).start()

    # ── thao tác input/output ─────────────────────────────

    def _load_file(self):

        path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])

        if not path:

            return

        content = None

        for enc in ["utf-8", "utf-8-sig", "gb18030", "gbk"]:

            try:

                with open(path, "r", encoding=enc) as f:

                    content = f.read()

                break

            except Exception:

                content = None

        if content is None:

            with open(path, "r", encoding="utf-8", errors="replace") as f:

                content = f.read()

        self.input_text.delete("1.0", tk.END)

        self.input_text.insert("1.0", content)

        self.status_label.config(text=f"Đã mở: {os.path.basename(path)}")

    def _active_input_widget(self):
        """Ô text theo tab con đang mở bên trái."""
        try:
            tab_text = self.left_nb.tab(self.left_nb.select(), "text")
        except Exception:
            return self.input_text
        if tab_text == "Quản lý Name":
            return getattr(self, "quick_add_text", self.input_text)
        return self.input_text

    def _clear_active_input(self):
        self._active_input_widget().delete("1.0", tk.END)

    def _paste_input(self):
        try:
            clip = self.clipboard_get()
        except tk.TclError:
            messagebox.showinfo("Clipboard trống", "Không có nội dung text.", parent=self)
            return
        w = self._active_input_widget()
        w.delete("1.0", tk.END)
        w.insert("1.0", clip)

    def _copy_result(self):

        content = self.output_text.get("1.0", "end-1c")

        if not content.strip():

            messagebox.showinfo("Trống", "Chưa có kết quả dịch.", parent=self)

            return

        self.clipboard_clear()

        self.clipboard_append(content)

        self.status_label.config(text="Đã sao chép kết quả.")

    def _export_result(self):

        content = self.output_text.get("1.0", tk.END).strip()

        if not content:

            messagebox.showinfo("Thông báo", "Chưa có nội dung dịch để xuất.", parent=self)

            return

        path = filedialog.asksaveasfilename(

            title="Xuất kết quả dịch", defaultextension=".txt",

            filetypes=[("Text file", "*.txt"), ("JSON (list)", "*.json"), ("All files", "*.*")],

        )

        if not path:

            return

        try:

            if path.lower().endswith(".json"):

                with open(path, "w", encoding="utf-8") as f:

                    json.dump(content.split("\n"), f, ensure_ascii=False, indent=2)

            else:

                with open(path, "w", encoding="utf-8") as f:

                    f.write(content)

            messagebox.showinfo("Thành công", f"Đã xuất kết quả: {path}", parent=self)

        except Exception as e:

            messagebox.showerror("Lỗi", f"Không thể lưu file: {e}", parent=self)

    def _set_output_chunks(self, original_chunks, translated_chunks, spans_list=None):

        w = self.output_text

        w.config(state="normal")

        w.delete("1.0", tk.END)

        w.chunk_data = {}

        w.chunk_spans = {}

        for i, tr in enumerate(translated_chunks):

            tag = f"chunk_{i}"

            w.chunk_data[tag] = original_chunks[i] if i < len(original_chunks) else ""

            w.chunk_spans[tag] = spans_list[i] if spans_list and i < len(spans_list) else []

            w.insert(tk.END, tr + "\n", (tag,))

        w.config(state="disabled")

    # ── dịch ──────────────────────────────────────────────

    def _start_translation(self, target_lang="vi"):

        content = self.input_text.get("1.0", tk.END).strip()

        if not content:

            messagebox.showwarning("Cảnh báo", "Không có nội dung để dịch.", parent=self)

            return

        if target_lang != "vi-server" and not self.engine.ready:

            messagebox.showwarning("Chưa sẵn sàng", "Từ điển chưa nạp xong, vui lòng đợi.", parent=self)

            return

        if self.is_translating:

            return

        self.is_translating = True

        settings = self._collect_runtime_settings()

        name_set = self._active_name_set()

        threading.Thread(target=self._translation_worker,

                         args=(content, name_set, settings, target_lang), daemon=True).start()

    def _translation_worker(self, content, name_set, settings, target_lang):

        def progress(msg, val):

            self.after(0, lambda: [self.status_label.config(text=msg),

                                   self.progress_bar.config(value=val),

                                   self.progress_bar.grid()])

        try:

            chunks = content.split("\n")

            if target_lang == "vi-server":

                translated = srv_translate_chunks(chunks, name_set, settings, progress, target_lang="vi")

                spans_list = None

            else:

                translated, spans_list = self.engine.translate_chunks(

                    chunks, name_set, settings, progress, target=target_lang, with_spans=True)

            def done():

                self._set_output_chunks(chunks, translated, spans_list)

                self._last_translation_lang = target_lang

                self.progress_bar.grid_remove()

                self.status_label.config(text=f"Dịch xong {len(chunks):,} dòng.")

            self.after(0, done)

        except Exception as e:

            self._set_status(f"Lỗi dịch: {e}")

        finally:

            self.is_translating = False

    def _smart_retranslate(self, affected_keys):

        """Dịch lại các dòng bị ảnh hưởng khi name thay đổi."""

        w = self.output_text

        if not getattr(w, "chunk_data", None):

            return

        if self._last_translation_lang != "vi-server" and not self.engine.ready:

            return

        chunks_to_do, update_plan = [], {}

        for tag, original in w.chunk_data.items():

            if any(k in original for k in affected_keys):

                update_plan[len(chunks_to_do)] = tag

                chunks_to_do.append(original)

        if not chunks_to_do:

            return

        def worker():

            self._set_status(f"Đang cập nhật {len(chunks_to_do)} đoạn...")

            name_set = self._active_name_set()

            settings = dict(self._settings())

            if self._last_translation_lang == "vi-server":

                new_texts = srv_translate_chunks(chunks_to_do, name_set, settings, target_lang="vi")

                new_spans = None

            else:

                new_texts, new_spans = self.engine.translate_chunks(

                    chunks_to_do, name_set, settings,

                    target=self._last_translation_lang, with_spans=True)

            def update_ui():

                w.config(state="normal")

                for i, new_text in enumerate(new_texts):

                    tag = update_plan.get(i)

                    if tag:

                        rng = w.tag_ranges(tag)

                        if rng:

                            w.delete(rng[0], rng[1])

                            w.insert(rng[0], new_text + "\n", (tag,))

                        if hasattr(w, "chunk_spans"):

                            w.chunk_spans[tag] = new_spans[i] if new_spans else []

                w.config(state="disabled")

                self.status_label.config(text="Cập nhật hoàn tất.")

            self.after(0, update_ui)

        threading.Thread(target=worker, daemon=True).start()

    # ── menu chuột phải trên văn bản gốc ──────────────────

    def _input_sel_to_vi(self):
        """Bôi đen ở input → (zh, vi bên output nếu có)."""
        try:
            sel = self.input_text.get("sel.first", "sel.last").strip()
        except tk.TclError:
            return "", ""
        if not sel:
            return "", ""

        try:
            line_idx = int(self.input_text.index("sel.first").split(".")[0]) - 1
        except Exception:
            return sel, ""

        w = self.output_text
        tag = f"chunk_{line_idx}"
        vi = ""
        if getattr(w, "chunk_data", None) is not None:
            rng = w.tag_ranges(tag)
            if rng:
                vi = w.get(rng[0], rng[1]).strip()
            spans = getattr(w, "chunk_spans", {}).get(tag) or []
            if spans:
                line_start = f"{line_idx + 1}.0"
                try:
                    off1 = len(self.input_text.get(line_start, "sel.first"))
                    off2 = off1 + len(self.input_text.get("sel.first", "sel.last"))
                    vi_bits = [s[1] for s in spans if s[2] < off2 and s[3] > off1]
                    if vi_bits:
                        vi = "".join(vi_bits).strip() or vi
                except Exception:
                    pass
        return sel, vi

    def _show_input_context_menu(self, event):
        """Menu trên input — bôi đen chữ Trung, kèm Việt nếu đã dịch."""
        zh, vi = self._input_sel_to_vi()
        menu = tk.Menu(self.input_text, tearoff=0)
        if zh:
            label = zh if len(zh) <= 20 else zh[:20] + "…"
            menu.add_command(
                label=f"Thêm/Sửa Name: {label}",
                command=lambda: self._edit_name(zh, vi, original_zh=zh, translated_vi=vi),
            )
            menu.add_command(
                label=f"Gợi ý dịch cho: {label}",
                command=lambda: self._show_suggestion_window(
                    zh, lambda v: self._quick_save_name(zh, v)
                ),
            )
        else:
            menu.add_command(
                label="(Bôi đen cụm chữ Trung để thêm/sửa Name)",
                state="disabled",
            )
        menu.tk_popup(event.x_root, event.y_root)

    def _show_output_context_menu(self, event):
        """Menu trên output — luôn cố lấy cả Trung + Việt."""
        w = event.widget
        menu = tk.Menu(w, tearoff=0)
        added = False

        zh, sel_text = self._selection_to_zh(w)

        # Fallback: cả dòng Trung của chunk đang trỏ
        index = w.index(f"@{event.x},{event.y}")
        tags = [t for t in w.tag_names(index) if t.startswith("chunk_")]
        chunk_tag = tags[0] if tags else None
        if not zh and chunk_tag:
            zh = (w.chunk_data.get(chunk_tag) or "").strip() or None

        if sel_text:
            if zh:
                zh_lbl = zh if len(zh) <= 15 else zh[:15] + "…"
                vi_lbl = sel_text if len(sel_text) <= 25 else sel_text[:25] + "…"
                menu.add_command(
                    label=f"✏ Sửa Name: {zh_lbl} = {vi_lbl}",
                    command=lambda z=zh, v=sel_text: self._edit_name(
                        z, v, original_zh=z, translated_vi=v
                    ),
                )
                menu.add_command(
                    label=f"Gợi ý dịch cho: {zh_lbl}",
                    command=lambda z=zh: self._show_suggestion_window(
                        z, lambda v: self._quick_save_name(z, v)
                    ),
                )
            else:
                vi_lbl = sel_text if len(sel_text) <= 25 else sel_text[:25] + "…"
                menu.add_command(
                    label=f"✏ Thêm Name cho nghĩa: {vi_lbl}",
                    command=lambda v=sel_text: self._edit_name(
                        "", v, original_zh="", translated_vi=v
                    ),
                )
            added = True

        if chunk_tag:
            original = w.chunk_data.get(chunk_tag)
            if original:
                rng = w.tag_ranges(chunk_tag)
                viet = w.get(rng[0], rng[1]).strip() if rng else ""
                if added:
                    menu.add_separator()
                menu.add_command(
                    label="Sửa Name cả dòng...",
                    command=lambda o=original, v=viet: self._edit_name(
                        o, v, original_zh=o, translated_vi=v
                    ),
                )
                added = True

        if not added:
            menu.add_command(
                label="(Bôi đen phần dịch muốn sửa rồi chuột phải)",
                state="disabled",
            )
        menu.tk_popup(event.x_root, event.y_root)

    def _quick_save_name(self, zh, vi):

        zh, vi = (zh or "").strip(), (vi or "").strip()

        if not zh or not vi:

            return

        set_name = self.name_set_combo.get()

        self.app_config["nameSets"][set_name][zh] = vi

        self.save_config()

        self._refresh_name_list()

        self.status_label.config(text=f"Đã lưu name: {zh} = {vi}")

        self._smart_retranslate([zh])

    # ── menu chuột phải trên kết quả ──────────────────────

    def _selection_to_zh(self, w):

        """Từ đoạn Việt đang bôi đen trong output, suy ra cụm chữ Trung gốc.

        Trả về (zh, sel_text) hoặc (None, sel_text)."""

        try:

            sel_first, sel_last = w.index("sel.first"), w.index("sel.last")

        except tk.TclError:

            return None, ""

        sel_text = w.get(sel_first, sel_last).strip()

        if not sel_text:

            return None, ""

        tags = [t for t in w.tag_names(sel_first) if t.startswith("chunk_")]

        if not tags:

            return None, sel_text

        chunk_tag = tags[0]

        rng = w.tag_ranges(chunk_tag)

        spans = getattr(w, "chunk_spans", {}).get(chunk_tag) or []

        if not rng or not spans:

            return None, sel_text

        off1 = len(w.get(rng[0], sel_first))

        off2 = off1 + len(w.get(sel_first, sel_last))

        zh = "".join(s[0] for s in spans if s[3] > off1 and s[2] < off2).strip()

        return (zh or None), sel_text

    def _build_name_manager(self, parent):

        parent.columnconfigure(0, weight=1)

        parent.rowconfigure(3, weight=1)

        sel = ttk.Frame(parent)

        sel.grid(row=0, column=0, sticky="ew")

        ttk.Label(sel, text="Bộ tên:").pack(side=tk.LEFT)

        self.name_set_combo = ttk.Combobox(sel, state="readonly",

                                           values=list(self.app_config["nameSets"].keys()))

        self.name_set_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        active = self.app_config.get("activeNameSet", "")

        if active not in self.app_config["nameSets"]:

            active = list(self.app_config["nameSets"].keys())[0]

        self.name_set_combo.set(active)

        self.name_set_combo.bind("<<ComboboxSelected>>", self._on_set_changed)

        ttk.Button(sel, text="Tạo mới", command=self._create_new_set).pack(side=tk.LEFT)

        ttk.Button(sel, style="Pink.TButton", text="Xóa bộ", command=self._delete_current_set).pack(side=tk.LEFT, padx=(5, 0))

        tools = ttk.Frame(parent)

        tools.grid(row=1, column=0, sticky="ew", pady=(6, 0))

        ttk.Button(tools, text="Nhập từ file", command=self._import_names).pack(side=tk.LEFT)

        ttk.Button(tools, text="Xuất ra TXT", command=self._export_names_txt).pack(side=tk.LEFT, padx=5)

        ttk.Button(tools, style="Pink.TButton", text="Xóa hết name", command=self._clear_names).pack(side=tk.LEFT)

        quick = ttk.LabelFrame(parent, text="Thêm/Sửa nhanh (mỗi dòng: Trung=Việt)")

        quick.grid(row=2, column=0, sticky="ew", pady=(8, 0))

        quick.columnconfigure(0, weight=1)

        self.quick_add_text = scrolledtext.ScrolledText(quick, height=4, wrap=tk.WORD, undo=True)

        self.quick_add_text.grid(row=0, column=0, sticky="ew", padx=4, pady=4)

        ttk.Button(quick, text="Thêm/Cập nhật các cặp này", style="Accent.TButton", command=self._quick_add_names).grid(row=1, column=0, pady=(0, 6))

        lf = ttk.LabelFrame(parent, text="Danh sách name")

        lf.grid(row=3, column=0, sticky="nsew", pady=(8, 0))

        lf.rowconfigure(1, weight=1)

        lf.columnconfigure(0, weight=1)

        search_fr = ttk.Frame(lf)

        search_fr.grid(row=0, column=0, columnspan=2, sticky="ew", padx=4, pady=(4, 0))

        ttk.Label(search_fr, text="Tìm:").pack(side=tk.LEFT)

        self.name_search_var = tk.StringVar()

        self.name_search_var.trace_add("write", lambda *a: self._refresh_name_list())

        ttk.Entry(search_fr, textvariable=self.name_search_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        ttk.Button(search_fr, text="➕ Thêm", command=lambda: self._edit_name("", "")).pack(side=tk.LEFT)

        ttk.Button(search_fr, text="✏ Sửa", command=self._edit_selected_name).pack(side=tk.LEFT, padx=4)

        ttk.Button(search_fr, style="Pink.TButton", text="🗑 Xóa", command=self._delete_selected_names).pack(side=tk.LEFT)

        self.name_tree = ttk.Treeview(lf, columns=("zh", "vi"), show="headings", selectmode="extended")

        self.name_tree.heading("zh", text="Tiếng Trung")

        self.name_tree.heading("vi", text="Tiếng Việt")

        self.name_tree.column("zh", width=140)

        self.name_tree.column("vi", width=180)

        self.name_tree.grid(row=1, column=0, sticky="nsew", padx=(4, 0), pady=4)

        tsb = ttk.Scrollbar(lf, orient=tk.VERTICAL, command=self.name_tree.yview)

        tsb.grid(row=1, column=1, sticky="ns", pady=4)

        self.name_tree.configure(yscrollcommand=tsb.set)

        self.name_tree.bind("<Double-1>", lambda e: self._edit_selected_name())

        self.name_tree.bind("<Delete>", lambda e: self._delete_selected_names())

        self._refresh_name_list()

    def _on_set_changed(self, event=None):

        self.app_config["activeNameSet"] = self.name_set_combo.get()

        self.save_config()

        self._refresh_name_list()

    def _refresh_name_list(self):

        tree = self.name_tree

        tree.delete(*tree.get_children())

        current = self.app_config["nameSets"].get(self.name_set_combo.get(), {})

        q = (self.name_search_var.get() or "").strip().lower()

        for k in sorted(current.keys()):

            v = current[k]

            if q and q not in k.lower() and q not in str(v).lower():

                continue

            tree.insert("", tk.END, values=(k, v))

    def _quick_add_names(self):

        lines = self.quick_add_text.get("1.0", tk.END).strip().split("\n")

        set_name = self.name_set_combo.get()

        if not set_name:

            return

        count, added_keys = 0, []

        for line in lines:

            parts = line.split("=")

            if len(parts) == 2:

                ch, vi = parts[0].strip(), parts[1].strip()

                if ch and vi:

                    self.app_config["nameSets"][set_name][ch] = vi

                    added_keys.append(ch)

                    count += 1

        if count:

            self.save_config()

            self.quick_add_text.delete("1.0", tk.END)

            self._refresh_name_list()

            self.status_label.config(text=f"Đã thêm/cập nhật {count} tên.")

            self._smart_retranslate(added_keys)

    def _create_new_set(self):

        name = simpledialog.askstring("Tạo bộ mới", "Nhập tên cho bộ mới:", parent=self)

        if name and name not in self.app_config["nameSets"]:

            self.app_config["nameSets"][name] = {}

            self.name_set_combo["values"] = list(self.app_config["nameSets"].keys())

            self.name_set_combo.set(name)

            self._on_set_changed()

        elif name:

            messagebox.showerror("Lỗi", "Tên bộ đã tồn tại.", parent=self)

    def _delete_current_set(self):

        set_name = self.name_set_combo.get()

        if len(self.app_config["nameSets"]) <= 1:

            messagebox.showerror("Lỗi", "Không thể xóa bộ tên cuối cùng.", parent=self)

            return

        if messagebox.askyesno("Xác nhận", f"Bạn có chắc muốn xóa bộ '{set_name}'?", parent=self):

            del self.app_config["nameSets"][set_name]

            self.name_set_combo["values"] = list(self.app_config["nameSets"].keys())

            self.name_set_combo.set(list(self.app_config["nameSets"].keys())[0])

            self._on_set_changed()

    def _import_names(self):

        path = filedialog.askopenfilename(filetypes=[("Text & JSON", "*.txt *.json"), ("All files", "*.*")], parent=self)

        if not path:

            return

        try:

            with open(path, "r", encoding="utf-8") as f:

                content = f.read()

            new_names = {}

            if path.lower().endswith(".json"):

                raw = json.loads(content)

                for k, v in raw.items():

                    if isinstance(v, dict):

                        v = v.get("val", "")

                    if k and str(v).strip():

                        new_names[k] = str(v).strip()

            else:

                for line in content.split("\n"):

                    parts = line.split("=")

                    if len(parts) == 2 and parts[0].strip() and parts[1].strip():

                        new_names[parts[0].strip()] = parts[1].strip()

            set_name = self.name_set_combo.get()

            self.app_config["nameSets"][set_name].update(new_names)

            self.save_config()

            self._refresh_name_list()

            messagebox.showinfo("Thành công", f"Đã nhập và cập nhật {len(new_names)} tên.", parent=self)

        except Exception as e:

            messagebox.showerror("Lỗi", f"Không thể đọc file: {e}", parent=self)

    def _export_names_txt(self):

        set_name = self.name_set_combo.get()

        current = self.app_config["nameSets"].get(set_name, {})

        path = filedialog.asksaveasfilename(defaultextension=".txt", initialfile=f"{set_name}.txt",

                                            filetypes=[("Text files", "*.txt")], parent=self)

        if not path:

            return

        try:

            with open(path, "w", encoding="utf-8") as f:

                f.write("\n".join(f"{k}={v}" for k, v in current.items()))

            messagebox.showinfo("Thành công", "Đã xuất file thành công.", parent=self)

        except Exception as e:

            messagebox.showerror("Lỗi", f"Không thể lưu file: {e}", parent=self)

    def _clear_names(self):

        set_name = self.name_set_combo.get()

        if messagebox.askyesno("Xác nhận", f"Xóa TẤT CẢ name trong bộ '{set_name}'?", icon="warning", parent=self):

            self.app_config["nameSets"][set_name] = {}

            self.save_config()

            self._refresh_name_list()

    def _edit_selected_name(self):

        sel = self.name_tree.selection()

        if not sel:

            messagebox.showinfo("Thông báo", "Chọn một name trong danh sách trước.", parent=self)

            return

        k, v = self.name_tree.item(sel[0], "values")

        self._edit_name(k, v)

    def _delete_selected_names(self):

        sel = self.name_tree.selection()

        if not sel:

            return

        set_name = self.name_set_combo.get()

        keys = [self.name_tree.item(i, "values")[0] for i in sel]

        if messagebox.askyesno("Xác nhận", f"Xóa {len(keys)} name đã chọn?", parent=self):

            for k in keys:

                self.app_config["nameSets"][set_name].pop(k, None)

            self.save_config()

            self._refresh_name_list()

    # ── dialog thêm/sửa name + gợi ý ──────────────────────

    def _edit_name(self, key, current_viet="", original_zh="", translated_vi=""):
        """Dialog thêm/sửa name với preview tiếng Trung + Việt gốc.
        
        original_zh: chữ Trung gốc (từ input khi người dùng bôi đen)
        translated_vi: bản dịch Việt tương ứng (từ output)
        """
        original_key = key
        win = tk.Toplevel(self)
        win.title("Thêm / Sửa Name")
        win.geometry("560x240")
        win.resizable(False, False)
        
        fr = ttk.Frame(win, padding=15)
        fr.pack(fill=tk.BOTH, expand=True)
        fr.columnconfigure(1, weight=1)
        
        # ═══ Preview ═══
        if original_zh or translated_vi:
            preview_lf = ttk.LabelFrame(fr, text="📌 Context gốc (không sửa)")
            preview_lf.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
            preview_lf.columnconfigure(1, weight=1)
            
            if original_zh:
                ttk.Label(preview_lf, text="Tiếng Trung:", font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", padx=4, pady=3)
                ttk.Label(preview_lf, text=original_zh, foreground="#0066cc", 
                        font=FONT_BOLD).grid(row=0, column=1, sticky="w", padx=4, pady=3)
            
            if translated_vi:
                ttk.Label(preview_lf, text="Tiếng Việt:", font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", padx=4, pady=3)
                ttk.Label(preview_lf, text=translated_vi, foreground="#009933", 
                        font=FONT_BOLD).grid(row=1, column=1, sticky="w", padx=4, pady=3)
            
            row_offset = 1
        else:
            row_offset = 0
        
        # ═══ Input ═══
        ttk.Label(fr, text="Tiếng Trung:", font=("Segoe UI", 10, "bold")).grid(row=row_offset, column=0, sticky="w", pady=4)
        key_entry = ttk.Entry(fr, font=FONT_TEXT)
        key_entry.insert(0, key)
        key_entry.grid(row=row_offset, column=1, sticky="ew", pady=4)
        
        ttk.Label(fr, text="Tiếng Việt:", font=("Segoe UI", 10, "bold")).grid(row=row_offset+1, column=0, sticky="w", pady=4)
        viet_entry = ttk.Entry(fr, font=FONT_TEXT)
        set_name = self.name_set_combo.get()
        initial = current_viet or self.app_config["nameSets"][set_name].get(key, "")
        viet_entry.insert(0, initial)
        viet_entry.grid(row=row_offset+1, column=1, sticky="ew", pady=4)
        viet_entry.focus_set()
        viet_entry.selection_range(0, len(initial))
        
        # ═══ Buttons ═══
        btns = ttk.Frame(fr)
        btns.grid(row=row_offset+2, column=0, columnspan=2, pady=(15, 0), sticky="e")
        
        def on_save():
            new_key = key_entry.get().strip()
            new_viet = viet_entry.get().strip()
            if not new_key or not new_viet:
                messagebox.showerror("Lỗi", "Không được để trống.", parent=win)
                return
            sname = self.name_set_combo.get()
            if original_key and original_key != new_key:
                self.app_config["nameSets"][sname].pop(original_key, None)
            self.app_config["nameSets"][sname][new_key] = new_viet
            self.save_config()
            self._refresh_name_list()
            win.destroy()
            self._smart_retranslate([new_key])
        
        def on_delete():
            k = key_entry.get().strip()
            if not k:
                return
            sname = self.name_set_combo.get()
            if messagebox.askyesno("Xác nhận", f"Bạn có chắc muốn xóa name '{k}'?", parent=win):
                self.app_config["nameSets"][sname].pop(k, None)
                self.save_config()
                self._refresh_name_list()
                win.destroy()
        
        suggest_btn = ttk.Button(
            btns, text="Gợi ý...",
            command=lambda: self._show_suggestion_window(
                key_entry.get().strip(),
                lambda v: (viet_entry.delete(0, tk.END), viet_entry.insert(0, v), win.lift(), viet_entry.focus_set()),
            ),
        )
        cancel_btn = ttk.Button(btns, text="Hủy", command=win.destroy)
        save_btn = ttk.Button(btns, text="Lưu", style="Accent.TButton", command=on_save)
        update_btn = ttk.Button(btns, text="Sửa", style="Accent.TButton", command=on_save)
        delete_btn = ttk.Button(btns, style="Pink.TButton", text="Xóa", command=on_delete)
        
        def update_buttons(event=None):
            cur = key_entry.get().strip()
            sname = self.name_set_combo.get()
            exists = cur in self.app_config["nameSets"][sname]
            save_btn.grid_remove()
            update_btn.grid_remove()
            delete_btn.grid_remove()
            if exists:
                update_btn.grid(row=0, column=2, padx=5)
                delete_btn.grid(row=0, column=3, padx=5)
            else:
                save_btn.grid(row=0, column=2, padx=5)
        
        suggest_btn.grid(row=0, column=0)
        cancel_btn.grid(row=0, column=1, padx=5)
        key_entry.bind("<KeyRelease>", update_buttons)
        update_buttons()

    def _show_suggestion_window(self, key, on_select):

        if not key:

            return

        win = tk.Toplevel(self)

        win.title(f"Gợi ý cho '{key}'")

        win.geometry("640x420")

        paned = ttk.PanedWindow(win, orient=tk.HORIZONTAL)

        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        hv_lf = ttk.LabelFrame(paned, text="Hán-Việt")

        paned.add(hv_lf, weight=1)

        hv_txt = scrolledtext.ScrolledText(hv_lf, wrap=tk.WORD, state="disabled")

        hv_txt.pack(fill=tk.BOTH, expand=True)

        tr_lf = ttk.LabelFrame(paned, text="Gợi ý dịch")

        paned.add(tr_lf, weight=1)

        tr_txt = scrolledtext.ScrolledText(tr_lf, wrap=tk.WORD, state="disabled")

        tr_txt.pack(fill=tk.BOTH, expand=True)

        def pick(value):

            on_select(value)

            win.destroy()

        def add_link(widget, text):

            widget.config(state="normal")

            tag = f"link_{widget.index(tk.END)}"

            widget.insert(tk.END, text + "\n", (tag,))

            widget.tag_config(tag, foreground="blue", underline=True, spacing1=3, spacing3=3)

            widget.tag_bind(tag, "<Enter>", lambda e: widget.config(cursor="hand2"))

            widget.tag_bind(tag, "<Leave>", lambda e: widget.config(cursor=""))

            widget.tag_bind(tag, "<Button-1>", lambda e, t=text: pick(t))

            widget.config(state="disabled")

        def worker():

            hv_lines, tr_lines = [], []

            if self.engine.ready:

                hv_lines = trans_progressive_capitalizations(self.engine.hanviet_of(key))

                seen = []

                for sug in self.engine.suggest(key, limit=15):

                    for alt in (sug.get("alts") or [sug.get("val", "")]):

                        for line in trans_progressive_capitalizations(alt):

                            if line and line not in seen:

                                seen.append(line)

                tr_lines = seen[:60]

            def update_ui():

                if not win.winfo_exists():

                    return

                for line in hv_lines:

                    add_link(hv_txt, line)

                for line in tr_lines:

                    add_link(tr_txt, line)

            self.after(0, update_ui)

        threading.Thread(target=worker, daemon=True).start()

    # ── tab nâng cao ──────────────────────────────────────

    def _build_advanced(self, parent):

        parent.columnconfigure(1, weight=1)

        s = self._settings()

        self.adv_name_url = tk.StringVar(value=s.get("nameUrl", ""))

        self.adv_vp_url = tk.StringVar(value=s.get("vpUrl", ""))

        self.adv_hv_url = tk.StringVar(value=s.get("hvUrl", ""))

        self.adv_max_match = tk.IntVar(value=s.get("maxMatchLen", 30))

        self.adv_prio_name = tk.BooleanVar(value=s.get("priorityNameFirst", True))

        self.adv_server_url = tk.StringVar(value=s.get("serverUrl", ""))

        self.adv_delay = tk.IntVar(value=s.get("delayMs", 400))

        self.adv_max_chars = tk.IntVar(value=s.get("maxChars", 4500))

        ttk.Label(parent, text="URL Name.json:").grid(row=0, column=0, sticky="w", padx=5, pady=4)

        ttk.Entry(parent, textvariable=self.adv_name_url).grid(row=0, column=1, sticky="ew", padx=5)

        ttk.Label(parent, text="URL VP.json:").grid(row=1, column=0, sticky="w", padx=5, pady=4)

        ttk.Entry(parent, textvariable=self.adv_vp_url).grid(row=1, column=1, sticky="ew", padx=5)

        ttk.Label(parent, text="URL HanViet.json:").grid(row=2, column=0, sticky="w", padx=5, pady=4)

        ttk.Entry(parent, textvariable=self.adv_hv_url).grid(row=2, column=1, sticky="ew", padx=5)

        ttk.Label(parent, text="Độ dài khớp tối đa:").grid(row=3, column=0, sticky="w", padx=5, pady=4)

        ttk.Spinbox(parent, from_=2, to=200, textvariable=self.adv_max_match, width=8).grid(row=3, column=1, sticky="w", padx=5)

        ttk.Checkbutton(parent, text="Ưu tiên Name khi trùng với VP",

                        variable=self.adv_prio_name).grid(row=4, column=0, columnspan=2, sticky="w", padx=5, pady=4)

        ttk.Separator(parent, orient="horizontal").grid(row=5, column=0, columnspan=2, sticky="ew", padx=5, pady=6)

        ttk.Label(parent, text="URL Server dịch:").grid(row=6, column=0, sticky="w", padx=5, pady=4)

        ttk.Entry(parent, textvariable=self.adv_server_url).grid(row=6, column=1, sticky="ew", padx=5)

        ttk.Label(parent, text="Delay giữa các gói (ms):").grid(row=7, column=0, sticky="w", padx=5, pady=4)

        ttk.Entry(parent, textvariable=self.adv_delay, width=10).grid(row=7, column=1, sticky="w", padx=5)

        ttk.Label(parent, text="Số ký tự tối đa / gói:").grid(row=8, column=0, sticky="w", padx=5, pady=4)

        ttk.Entry(parent, textvariable=self.adv_max_chars, width=10).grid(row=8, column=1, sticky="w", padx=5)

        btn_fr = ttk.Frame(parent)

        btn_fr.grid(row=9, column=0, columnspan=2, sticky="w", padx=5, pady=(10, 4))

        ttk.Button(btn_fr, text="🔄 Nạp lại từ điển",

                   command=lambda: (self._collect_runtime_settings(), self._load_dicts_async())).pack(side=tk.LEFT)

        ttk.Button(btn_fr, text="⬇ Tải lại từ điển từ web",

                   command=self._force_redownload).pack(side=tk.LEFT, padx=8)

        self.dict_stats_label = ttk.Label(parent, text="Từ điển: chưa nạp.", foreground="#555")

        self.dict_stats_label.grid(row=10, column=0, columnspan=2, sticky="w", padx=5, pady=(10, 2))

        ttk.Label(parent, text=f"Thư mục từ điển: {TRANS_DICT_DIR}",

                  foreground="#888", wraplength=420).grid(row=11, column=0, columnspan=2, sticky="w", padx=5)

        ttk.Label(parent, text="Có thể đặt sẵn Name.json / VP.json / HanViet.json vào thư mục trên;\n"

                               "file nào thiếu sẽ tự tải từ URL khi mở tab.",

                  foreground="#888").grid(row=12, column=0, columnspan=2, sticky="w", padx=5, pady=(4, 0))
        
        ttk.Label(parent, text=f"File cấu hình (Name Sets): {TRANS_CONFIG_PATH}",
                  foreground="#888", wraplength=420).grid(row=13, column=0, columnspan=2, sticky="w", padx=5, pady=(4, 0))
        self.config_status_label = ttk.Label(parent, text="", foreground="#c0392b", wraplength=420)
        self.config_status_label.grid(row=14, column=0, columnspan=2, sticky="w", padx=5, pady=(2, 0))
        self._check_config_status()

    def _check_config_status(self):
        exists = os.path.exists(TRANS_CONFIG_PATH)
        if not exists:
            self.config_status_label.config(text="⚠ File config CHƯA TỪNG được tạo — mọi lần lưu đều thất bại!")
            return
        try:
            with open(TRANS_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            mac_dinh_count = len(data.get("nameSets", {}).get("Mặc định", {}))
            self.config_status_label.config(
                text=f"✓ File tồn tại. Bộ 'Mặc định' hiện có {mac_dinh_count} name lúc mở app.")
        except Exception as e:
            self.config_status_label.config(text=f"⚠ File tồn tại nhưng ĐỌC LỖI: {e}")
    def _refresh_dict_stats(self):

        if hasattr(self, "dict_stats_label") and self.engine.ready:

            self.dict_stats_label.config(text=f"Từ điển: {self.engine.stats()}")

    def _force_redownload(self):

        if messagebox.askyesno("Xác nhận", "Tải lại toàn bộ từ điển từ web (ghi đè file hiện có)?", parent=self):

            self._collect_runtime_settings()

            self._load_dicts_async(force_download=True)

def _first_font(root, candidates, fallback):
    """Chọn font đầu tiên có trên máy (Segoe UI có sẵn trên Windows)."""
    import tkinter.font as tkfont
    try:
        have = set(tkfont.families(root))
    except tk.TclError:
        return fallback
    return next((f for f in candidates if f in have), fallback)


def apply_theme(root):
    """Áp dụng giao diện xanh lá + hồng pastel và font Segoe UI cho TOÀN app.

    Gọi 1 lần khi tạo cửa sổ chính. Muốn đổi màu: sửa bảng THEME ở đầu file.
    """
    import tkinter.font as tkfont
    T = THEME

    ui = _first_font(root, ("Segoe UI", "Noto Sans", "DejaVu Sans", "Helvetica", "Arial"),
                     tkfont.nametofont("TkDefaultFont").actual("family"))
    mono = _first_font(root, ("Consolas", "DejaVu Sans Mono", "Menlo", "Courier New"), "Courier")

    # Font mặc định cho mọi widget (kể cả tk.Text, Menu, hộp thoại)
    for name, size in (("TkDefaultFont", 10), ("TkTextFont", 10), ("TkMenuFont", 10),
                       ("TkHeadingFont", 10), ("TkCaptionFont", 10), ("TkIconFont", 10),
                       ("TkTooltipFont", 9)):
        try:
            tkfont.nametofont(name).configure(family=ui, size=size)
        except tk.TclError:
            pass
    try:
        tkfont.nametofont("TkFixedFont").configure(family=mono, size=10)
    except tk.TclError:
        pass

    style = ttk.Style(root)
    try:
        style.theme_use("clam")          # 'clam' cho phép tô màu đồng nhất trên mọi hệ điều hành
    except tk.TclError:
        pass
    root.configure(background=T["bg"])

    # ── widget tk.* (không thuộc ttk) chỉnh qua option database ──
    o = root.option_add
    o("*Text.font", "TkTextFont")                    # tk.Text mặc định là font đơn cách, đổi lại
    o("*Text.background", T["panel"]);        o("*Text.foreground", T["ink"])
    o("*Text.selectBackground", T["p300"]);   o("*Text.selectForeground", T["ink"])
    o("*Text.insertBackground", T["g700"])
    o("*Text.relief", "flat");                o("*Text.borderWidth", 0)
    o("*Text.highlightThickness", 1)
    o("*Text.highlightBackground", T["border"]); o("*Text.highlightColor", T["g500"])
    o("*Text.padX", 6);                       o("*Text.padY", 4)
    o("*Listbox.background", T["panel"]);     o("*Listbox.foreground", T["ink"])
    o("*Listbox.selectBackground", T["p300"]); o("*Listbox.selectForeground", T["ink"])
    o("*Listbox.relief", "flat");             o("*Listbox.borderWidth", 0)
    o("*Listbox.highlightThickness", 1)
    o("*Listbox.highlightBackground", T["border"]); o("*Listbox.highlightColor", T["g500"])
    o("*Listbox.activeStyle", "none")
    o("*Menu.background", T["panel"]);        o("*Menu.foreground", T["ink"])
    o("*Menu.activeBackground", T["p200"]);   o("*Menu.activeForeground", T["ink"])
    o("*Menu.relief", "flat");                o("*Menu.borderWidth", 1)
    o("*Toplevel.background", T["bg"]);       o("*Frame.background", T["bg"])
    o("*Scrollbar.background", T["g200"]);    o("*Scrollbar.troughColor", T["bg"])
    o("*Scrollbar.activeBackground", T["g500"]); o("*Scrollbar.relief", "flat")
    o("*Scrollbar.borderWidth", 0);           o("*Scrollbar.width", 12)
    o("*TCombobox*Listbox.background", T["panel"]); o("*TCombobox*Listbox.foreground", T["ink"])
    o("*TCombobox*Listbox.selectBackground", T["p300"])
    o("*TCombobox*Listbox.selectForeground", T["ink"])
    o("*TCombobox*Listbox.font", "TkDefaultFont")

    # ── widget ttk ──
    style.configure(".", background=T["bg"], foreground=T["ink"], font=(ui, 10),
                    bordercolor=T["border"], lightcolor=T["bg"], darkcolor=T["bg"],
                    troughcolor=T["g100"], focuscolor=T["g500"],
                    selectbackground=T["p300"], selectforeground=T["ink"])
    style.configure("TFrame", background=T["bg"])
    style.configure("TLabel", background=T["bg"], foreground=T["ink"], font=(ui, 10))
    style.configure("Ok.TLabel", foreground=T["g700"])
    style.configure("Muted.TLabel", foreground=T["muted"])

    # Nút: thường (xanh nhạt) / Accent (xanh đậm, việc chính) / Pink (hồng pastel, xóa)
    def _button(name, bg, fg, border, hover, press, bold=False):
        style.configure(name, background=bg, foreground=fg, bordercolor=border,
                        lightcolor=bg, darkcolor=bg, focusthickness=1, focuscolor=T["g500"],
                        padding=(10, 5), relief="flat", anchor="center",
                        font=(ui, 10, "bold") if bold else (ui, 10))
        style.map(name,
                  background=[("disabled", T["dis_bg"]), ("pressed", press), ("active", hover)],
                  lightcolor=[("disabled", T["dis_bg"]), ("pressed", press), ("active", hover)],
                  darkcolor=[("disabled", T["dis_bg"]), ("pressed", press), ("active", hover)],
                  bordercolor=[("disabled", T["dis_bg"]), ("active", T["g500"])],
                  foreground=[("disabled", T["muted"])])
    _button("TButton", T["g100"], T["ink"], T["border"], T["g200"], T["g200"])
    _button("Accent.TButton", T["g700"], "#ffffff", T["g700"], T["g500"], "#245a3e", bold=True)
    _button("Pink.TButton", T["p100"], T["p700"], T["p300"], T["p300"], T["p200"])

    for s in ("TCheckbutton", "TRadiobutton"):
        style.configure(s, background=T["bg"], foreground=T["ink"], font=(ui, 10),
                        indicatorbackground=T["panel"], indicatorforeground=T["g700"],
                        upperbordercolor=T["border"], lowerbordercolor=T["border"])
        style.map(s, background=[("active", T["bg"])],
                  indicatorbackground=[("selected", T["g500"]), ("pressed", T["g200"])],
                  foreground=[("disabled", T["muted"])])

    style.configure("TLabelframe", background=T["bg"], bordercolor=T["border"],
                    lightcolor=T["border"], darkcolor=T["border"], relief="solid", borderwidth=1)
    style.configure("TLabelframe.Label", background=T["bg"], foreground=T["g700"],
                    font=(ui, 10, "bold"))

    for s in ("TEntry", "TCombobox", "TSpinbox"):
        style.configure(s, fieldbackground=T["panel"], foreground=T["ink"], padding=4,
                        bordercolor=T["border"], lightcolor=T["panel"], darkcolor=T["panel"],
                        insertcolor=T["g700"], selectbackground=T["p300"], selectforeground=T["ink"])
        style.map(s, bordercolor=[("focus", T["g500"]), ("hover", T["g500"])],
                  lightcolor=[("focus", T["g500"])], darkcolor=[("focus", T["g500"])])
    style.configure("TCombobox", background=T["g100"], arrowcolor=T["g700"])
    style.configure("TSpinbox", background=T["g100"], arrowcolor=T["g700"])
    style.map("TCombobox", fieldbackground=[("readonly", T["panel"]), ("disabled", T["dis_bg"])],
              selectbackground=[("readonly", T["panel"])], selectforeground=[("readonly", T["ink"])],
              background=[("active", T["g200"])])

    style.configure("TNotebook", background=T["bg"], bordercolor=T["border"],
                    lightcolor=T["bg"], darkcolor=T["bg"], tabmargins=(2, 4, 2, 0))
    style.configure("TNotebook.Tab", background=T["g200"], foreground=T["ink"], padding=(14, 6),
                    bordercolor=T["border"], lightcolor=T["g200"], darkcolor=T["g200"],
                    font=(ui, 10, "bold"))
    style.map("TNotebook.Tab",
              background=[("selected", T["bg"]), ("active", T["p100"])],
              lightcolor=[("selected", T["bg"]), ("active", T["p100"])],
              darkcolor=[("selected", T["bg"]), ("active", T["p100"])],
              foreground=[("selected", T["g700"])])

    style.configure("Treeview", background=T["panel"], fieldbackground=T["panel"],
                    foreground=T["ink"], rowheight=26, bordercolor=T["border"],
                    lightcolor=T["panel"], darkcolor=T["panel"], font=(ui, 10))
    style.map("Treeview", background=[("selected", T["p300"])], foreground=[("selected", T["ink"])])
    style.configure("Treeview.Heading", background=T["g100"], foreground=T["g700"],
                    bordercolor=T["border"], lightcolor=T["g100"], darkcolor=T["g100"],
                    relief="flat", padding=(6, 5), font=(ui, 10, "bold"))
    style.map("Treeview.Heading", background=[("active", T["g200"])])

    for s in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
        style.configure(s, background=T["g200"], troughcolor=T["bg"], bordercolor=T["bg"],
                        lightcolor=T["g200"], darkcolor=T["g200"], arrowcolor=T["g700"],
                        gripcount=0, relief="flat")
        style.map(s, background=[("active", T["g500"]), ("pressed", T["g700"])])
    style.configure("Horizontal.TProgressbar", background=T["g500"], troughcolor=T["g100"],
                    bordercolor=T["border"], lightcolor=T["g500"], darkcolor=T["g500"], thickness=10)
    style.configure("TPanedwindow", background=T["bg"])
    style.configure("Sash", sashthickness=6, gripcount=0, background=T["g200"],
                    lightcolor=T["bg"], darkcolor=T["bg"], bordercolor=T["bg"])
    style.configure("TSeparator", background=T["border"])

# ═══════════════════════════════════════════════════════════

#  PHẦN 9 — APP CHÍNH

# ═══════════════════════════════════════════════════════════

class App(tk.Tk):

    def __init__(self):

        super().__init__()

        apply_theme(self)

        self.title("Tool Dịch QT — Lọc tên | EPUB | Dịch QT")

        self.geometry("1350x800")

        self.minsize(900, 600)

        # Icon cửa sổ (app.ico nhúng trong exe hoặc nằm cạnh file)

        try:

            icon_path = os.path.join(getattr(sys, "_MEIPASS", _bundled_dir()), "app.ico")

            if os.path.exists(icon_path):

                self.iconbitmap(icon_path)

        except Exception:

            pass

        nb = ttk.Notebook(self)

        nb.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        tab1 = TabNames(nb)

        tab2 = TabEpub(nb)

        tab3 = TabTranslate(nb)

        nb.add(tab1, text="  👤 Lọc tên nhân vật  ")

        nb.add(tab2, text="  📚 Tạo & Gộp EPUB  ")

        nb.add(tab3, text="  🌐 Dịch Trung → Việt  ")
        tab1.translate_tab = tab3        # nút 'Dịch name' ở tab Lọc tên dùng engine + bộ tên của tab Dịch
        self.title(f"{self.title()}  —  v{APP_VERSION}")
        sync_admin_lists_async(lambda changed: tab1._remove_blacklisted_from_results() if changed else None)
        check_for_update_async(self._on_update_checked)

    def _on_update_checked(self, has_new, tag, url):
        if not has_new:
            return
        def ask():
            if messagebox.askyesno(
                    "Có bản cập nhật",
                    f"Đã có bản mới {tag} (bạn đang dùng v{APP_VERSION}).\n\n"
                    "Mở trang tải về?", parent=self):
                webbrowser.open(url)
        self.after(0, ask)

if __name__ == "__main__":

    app = App()

    app.mainloop()