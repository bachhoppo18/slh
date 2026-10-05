"""Read-only license verification against the SLH secret Gist."""
import hashlib
import hmac
import json
import platform
import urllib.error
import urllib.request
import uuid


GIST_RAW_URL = (
    "https://gist.githubusercontent.com/bachhoppo18/"
    "f58e9f0d5fbe8baa8d8cdc8556c6d31e/raw/licenses.json"
)


class LicenseError(RuntimeError):
    pass


def get_hwid():
    machine_id = ""
    if platform.system() == "Windows":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                machine_id = winreg.QueryValueEx(key, "MachineGuid")[0]
        except (ImportError, OSError):
            pass
    else:
        for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            try:
                with open(path, "r", encoding="ascii") as file:
                    machine_id = file.read().strip()
                if machine_id:
                    break
            except OSError:
                pass
    if not machine_id:
        machine_id = f"{platform.node()}:{uuid.getnode():012x}"
    return hashlib.sha256(f"SLHTool-HWID-v1:{machine_id}".encode("utf-8")).hexdigest()


def _read_license_index():
    request = urllib.request.Request(
        GIST_RAW_URL,
        headers={"Accept": "application/json", "User-Agent": "SLHTool"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise LicenseError(f"Không tải được danh sách license (HTTP {exc.code}).") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise LicenseError(f"Không tải được danh sách license từ GitHub: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("keys"), dict) or not isinstance(data.get("machines"), dict):
        raise LicenseError("Danh sách license trên Gist không đúng định dạng.")
    return data


def activate(key, hwid=None):
    key_hash = hashlib.sha256(key.strip().encode("utf-8")).hexdigest()
    machine_hash = hwid or get_hwid()
    data = _read_license_index()
    licensed_hwid = data["keys"].get(key_hash)
    licensed_key = data["machines"].get(machine_hash)
    if not isinstance(licensed_hwid, str) or not hmac.compare_digest(licensed_hwid, machine_hash):
        raise LicenseError("Key chưa được cấp cho máy này hoặc đã bị thu hồi.")
    if not isinstance(licensed_key, str) or not hmac.compare_digest(licensed_key, key_hash):
        raise LicenseError("Máy này đã được cấp một mã license khác.")
    return {"status": "activated"}