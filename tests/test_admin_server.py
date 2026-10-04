import base64
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

import admin_server


class AdminServerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(admin_server, "DB_PATH", os.path.join(self.temp_dir.name, "users.sqlite3"))
        self.db_patch.start()
        self.env_patch = patch.dict(os.environ, {
            "SLH_ADMIN_USERNAME": "root-admin",
            "SLH_ADMIN_PASSWORD": "initial-admin-password",
        })
        self.env_patch.start()
        self.secret_patch = patch.object(admin_server, "AUTH_SECRET", "test-secret-that-is-at-least-thirty-two-characters")
        self.secret_patch.start()
        self.github_patch = patch.object(admin_server, "GITHUB_TOKEN", "test-token")
        self.github_patch.start()
        admin_server.initialize_database()

    def tearDown(self):
        self.github_patch.stop()
        self.secret_patch.stop()
        self.env_patch.stop()
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def _user(self, username, password):
        result = admin_server.login(admin_server.LoginRequest(username=username, password=password))
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=result["access_token"])
        return admin_server._authenticate(credentials)

    def test_only_admin_can_provision_users(self):
        admin = self._user("root-admin", "initial-admin-password")
        user = admin_server.create_user(admin_server.UserRequest(username="writer-01", password="user-password-123"), admin)
        self.assertEqual(user["role"], "user")
        self.assertEqual(self._user("writer-01", "user-password-123")["role"], "user")
        with self.assertRaises(HTTPException) as error:
            admin_server._admin({"username": "writer-01", "role": "user"})
        self.assertEqual(error.exception.status_code, 403)

    def test_admin_dictionary_entry_is_written_to_github_overlay(self):
        admin = self._user("root-admin", "initial-admin-password")
        stored = {}

        def fake_github_request(method, path, payload=None):
            if method == "GET":
                if not stored:
                    return None
                encoded = base64.b64encode(json.dumps(stored, ensure_ascii=False).encode()).decode()
                return {"content": encoded, "sha": "test-sha"}
            stored.update(json.loads(base64.b64decode(payload["content"]).decode()))
            return {"content": payload["content"], "sha": "next-sha"}

        with patch.object(admin_server, "_github_request", side_effect=fake_github_request):
            result = admin_server.add_entry("name", admin_server.EntryRequest(key="林風", value="Lâm Phong"), admin)

        self.assertEqual(result["status"], "saved")
        self.assertEqual(stored, {"林風": "Lâm Phong"})

    def test_user_cannot_write_dataset(self):
        user = {"username": "member", "role": "user"}
        with self.assertRaises(HTTPException) as error:
            admin_server._admin(user)
        self.assertEqual(error.exception.status_code, 403)

    def test_http_routes_enforce_login_and_admin_role(self):
        with TestClient(admin_server.app) as client:
            denied = client.get("/datasets")
            self.assertEqual(denied.status_code, 401)

            login = client.post("/auth/login", json={"username": "root-admin", "password": "initial-admin-password"})
            self.assertEqual(login.status_code, 200)
            admin_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            with patch.object(admin_server, "_github_request", return_value=None):
                datasets = client.get("/datasets", headers=admin_headers)
            self.assertEqual(datasets.status_code, 200)
            self.assertEqual(set(datasets.json()), {"hanviet", "name", "vp", "blacklist"})

            create = client.post("/users", headers=admin_headers, json={"username": "route-user", "password": "route-password-123"})
            self.assertEqual(create.status_code, 201)
            user_login = client.post("/auth/login", json={"username": "route-user", "password": "route-password-123"})
            user_headers = {"Authorization": f"Bearer {user_login.json()['access_token']}"}
            denied_create = client.post("/users", headers=user_headers, json={"username": "other-user", "password": "route-password-456"})
            denied_write = client.post("/datasets/name/entries", headers=user_headers, json={"key": "词", "value": "từ"})
            self.assertEqual(denied_create.status_code, 403)
            self.assertEqual(denied_write.status_code, 403)


if __name__ == "__main__":
    unittest.main()