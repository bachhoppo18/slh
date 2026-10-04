import json
import os
import tempfile
import unittest

from admin_ui import (
    LOCAL_ADMIN_DEFAULT_PASSWORD,
    LOCAL_ADMIN_USERNAME,
    change_local_admin_password,
    initialize_local_admin,
    verify_local_admin,
)


class LocalAdminAuthTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.directory.name, "admin_config.json")

    def tearDown(self):
        self.directory.cleanup()

    def test_first_run_creates_local_admin_with_hashed_default_password(self):
        initialize_local_admin(self.config_path)

        self.assertTrue(verify_local_admin(
            self.config_path, LOCAL_ADMIN_USERNAME, LOCAL_ADMIN_DEFAULT_PASSWORD
        ))
        with open(self.config_path, encoding="utf-8") as file:
            config = json.load(file)
        self.assertNotIn(LOCAL_ADMIN_DEFAULT_PASSWORD, str(config))

    def test_previous_api_config_migrates_to_local_admin(self):
        with open(self.config_path, "w", encoding="utf-8") as file:
            json.dump({"api_url": "https://old.example"}, file)

        initialize_local_admin(self.config_path)

        self.assertTrue(verify_local_admin(
            self.config_path, LOCAL_ADMIN_USERNAME, LOCAL_ADMIN_DEFAULT_PASSWORD
        ))

    def test_password_can_be_changed_and_old_password_stops_working(self):
        initialize_local_admin(self.config_path)

        change_local_admin_password(self.config_path, "123456", "new-password-123")

        self.assertFalse(verify_local_admin(self.config_path, "admin", "123456"))
        self.assertTrue(verify_local_admin(self.config_path, "admin", "new-password-123"))

    def test_password_change_requires_valid_current_password_and_minimum_length(self):
        initialize_local_admin(self.config_path)

        with self.assertRaisesRegex(ValueError, "hiện tại"):
            change_local_admin_password(self.config_path, "wrong", "new-password-123")
        with self.assertRaisesRegex(ValueError, "8 ký tự"):
            change_local_admin_password(self.config_path, "123456", "short")


if __name__ == "__main__":
    unittest.main()