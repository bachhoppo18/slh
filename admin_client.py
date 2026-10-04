"""Authenticated client for the SLH administration service."""
import json
import urllib.error
import urllib.request


class AdminApiError(RuntimeError):
    pass


class AdminClient:
    def __init__(self, base_url, token=None, role=None):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.role = role

    def _request(self, method, path, payload=None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        headers = {"Accept": "application/json", "User-Agent": "SLHTool"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(self.base_url + path, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                message = json.loads(exc.read().decode("utf-8")).get("detail", str(exc))
            except Exception:
                message = str(exc)
            raise AdminApiError(str(message)) from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise AdminApiError(f"Không kết nối được máy chủ: {exc}") from exc

    def login(self, username, password):
        result = self._request("POST", "/auth/login", {"username": username, "password": password})
        self.token = result["access_token"]
        self.role = result["role"]
        return result

    def get_datasets(self):
        return self._request("GET", "/datasets")

    def add_entry(self, dataset, key, value):
        return self._request("POST", f"/datasets/{dataset}/entries", {"key": key, "value": value})

    def list_users(self):
        return self._request("GET", "/users")

    def create_user(self, username, password):
        return self._request("POST", "/users", {"username": username, "password": password})