"""Small self-hosted authentication and GitHub-backed data API for SLH Tool."""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field


GITHUB_REPO = os.environ.get("SLH_GITHUB_REPO", "bachhoppo18/slh")
GITHUB_BRANCH = os.environ.get("SLH_GITHUB_BRANCH", "main")
GITHUB_TOKEN = os.environ.get("SLH_GITHUB_TOKEN", "")
AUTH_SECRET = os.environ.get("SLH_AUTH_SECRET", "")
DB_PATH = os.environ.get("SLH_DB_PATH", "slh-admin.sqlite3")
DATASETS = {"hanviet", "name", "vp", "blacklist"}
DICT_DATASETS = {"hanviet", "name", "vp"}
TOKEN_TTL_SECONDS = 12 * 60 * 60
PASSWORD_ITERATIONS = 310_000
security = HTTPBearer(auto_error=False)
app = FastAPI(title="SLH Admin API", docs_url=None, redoc_url=None)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class UserRequest(LoginRequest):
    pass


class EntryRequest(BaseModel):
    key: str = Field(default="", max_length=500)
    value: str = Field(min_length=1, max_length=10_000)


@contextmanager
def _connection():
    connection = sqlite3.connect(DB_PATH, timeout=20)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def _password_hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)


def initialize_database():
    username = os.environ.get("SLH_ADMIN_USERNAME", "").strip()
    password = os.environ.get("SLH_ADMIN_PASSWORD", "")
    if not username or len(password) < 12:
        raise RuntimeError("Set SLH_ADMIN_USERNAME and SLH_ADMIN_PASSWORD (at least 12 characters).")
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    with _connection() as db:
        db.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, salt BLOB NOT NULL, password_hash BLOB NOT NULL, role TEXT NOT NULL, created_at INTEGER NOT NULL)")
        admin_count = db.execute("SELECT count(*) FROM users WHERE role = 'admin'").fetchone()[0]
        if not admin_count:
            salt = secrets.token_bytes(16)
            db.execute("INSERT INTO users VALUES (?, ?, ?, 'admin', ?)", (username, salt, _password_hash(password, salt), int(time.time())))


@app.on_event("startup")
def _startup():
    if not GITHUB_TOKEN:
        raise RuntimeError("SLH_GITHUB_TOKEN is required.")
    if len(AUTH_SECRET) < 32:
        raise RuntimeError("SLH_AUTH_SECRET must contain at least 32 characters.")
    initialize_database()


def _b64url(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _issue_token(username, role):
    payload = _b64url(json.dumps({"sub": username, "role": role, "exp": int(time.time()) + TOKEN_TTL_SECONDS}, separators=(",", ":")).encode())
    signature = _b64url(hmac.new(AUTH_SECRET.encode(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}"


def _authenticate(credentials=Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Đăng nhập để tiếp tục.")
    try:
        payload, signature = credentials.credentials.split(".", 1)
        expected = _b64url(hmac.new(AUTH_SECRET.encode(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("signature")
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if claims["exp"] < int(time.time()):
            raise ValueError("expired")
        with _connection() as db:
            user = db.execute("SELECT username, role FROM users WHERE username = ?", (claims["sub"],)).fetchone()
        if not user or user["role"] != claims["role"]:
            raise ValueError("user")
        return {"username": user["username"], "role": user["role"]}
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Phiên đăng nhập không hợp lệ hoặc đã hết hạn.") from exc


def _admin(user=Depends(_authenticate)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin được phép thực hiện thao tác này.")
    return user


def _github_request(method, path, payload=None):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{urllib.parse.quote(path, safe='/')}"
    if method == "GET":
        url += "?ref=" + urllib.parse.quote(GITHUB_BRANCH)
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=body, method=method, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "SLHTool-Admin-API",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if method == "GET" and exc.code == 404:
            return None
        if method == "PUT" and exc.code == 409:
            raise HTTPException(status_code=409, detail="Dữ liệu vừa được cập nhật ở nơi khác; hãy đồng bộ rồi thử lại.") from exc
        raise HTTPException(status_code=502, detail=f"GitHub API trả về lỗi HTTP {exc.code}.") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise HTTPException(status_code=502, detail=f"Không kết nối được GitHub: {exc}") from exc


def _read_dataset(name):
    path = f"slh-data/admin/{name}.json"
    result = _github_request("GET", path)
    if result is None:
        return {} if name in DICT_DATASETS else []
    try:
        raw = base64.b64decode(result["content"]).decode("utf-8")
        return json.loads(raw)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Dữ liệu {name} trên GitHub không hợp lệ.") from exc


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/login")
def login(request: LoginRequest):
    with _connection() as db:
        user = db.execute("SELECT username, salt, password_hash, role FROM users WHERE username = ?", (request.username.strip(),)).fetchone()
    if not user or not hmac.compare_digest(_password_hash(request.password, user["salt"]), user["password_hash"]):
        raise HTTPException(status_code=401, detail="Tên đăng nhập hoặc mật khẩu không đúng.")
    return {"access_token": _issue_token(user["username"], user["role"]), "token_type": "bearer", "role": user["role"], "username": user["username"]}


@app.get("/datasets")
def get_datasets(_user=Depends(_authenticate)):
    return {name: _read_dataset(name) for name in sorted(DATASETS)}


@app.post("/datasets/{name}/entries")
def add_entry(name: str, request: EntryRequest, _user=Depends(_admin)):
    if name not in DATASETS:
        raise HTTPException(status_code=404, detail="Danh sách không tồn tại.")
    key, value = request.key.strip(), request.value.strip()
    if not value:
        raise HTTPException(status_code=422, detail="Giá trị không được để trống.")
    if name in DICT_DATASETS:
        if not key:
            raise HTTPException(status_code=422, detail="Từ khóa không được để trống.")
        values = _read_dataset(name)
        if not isinstance(values, dict):
            raise HTTPException(status_code=502, detail="Dữ liệu từ điển không đúng định dạng.")
        values[key] = value
    else:
        values = _read_dataset(name)
        if not isinstance(values, list):
            raise HTTPException(status_code=502, detail="Dữ liệu blacklist không đúng định dạng.")
        if value not in values:
            values.append(value)
        values.sort(key=str.casefold)
    content = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    if len(content.encode("utf-8")) > 700_000:
        raise HTTPException(status_code=413, detail="Danh sách bổ sung đã đạt giới hạn; cần chia nhỏ hoặc chuyển sang kho dữ liệu khác.")
    path = f"slh-data/admin/{name}.json"
    current = _github_request("GET", path)
    payload = {"message": f"SLHTool: add {name} entry", "branch": GITHUB_BRANCH, "content": base64.b64encode(content.encode()).decode()}
    if current:
        payload["sha"] = current["sha"]
    _github_request("PUT", path, payload)
    return {"status": "saved", "dataset": name, "count": len(values)}


@app.get("/users")
def list_users(_user=Depends(_admin)):
    with _connection() as db:
        rows = db.execute("SELECT username, role, created_at FROM users ORDER BY username COLLATE NOCASE").fetchall()
    return [{"username": row["username"], "role": row["role"], "created_at": row["created_at"]} for row in rows]


@app.post("/users", status_code=201)
def create_user(request: UserRequest, _user=Depends(_admin)):
    username = request.username.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,64}", username):
        raise HTTPException(status_code=422, detail="Tên user cần 3-64 ký tự: chữ, số, dấu chấm, gạch ngang hoặc gạch dưới.")
    if len(request.password) < 12:
        raise HTTPException(status_code=422, detail="Mật khẩu cần ít nhất 12 ký tự.")
    salt = secrets.token_bytes(16)
    try:
        with _connection() as db:
            db.execute("INSERT INTO users VALUES (?, ?, ?, 'user', ?)", (username, salt, _password_hash(request.password, salt), int(time.time())))
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Tên user đã tồn tại.") from exc
    return {"username": username, "role": "user"}