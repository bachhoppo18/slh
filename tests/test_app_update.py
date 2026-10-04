import hashlib
import os
import tempfile
import unittest
from unittest.mock import patch

import slhtool


class _Response:
    def __init__(self, content):
        self.content = content

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _size=-1):
        content, self.content = self.content, b""
        return content


class AppUpdateTests(unittest.TestCase):
    def test_new_release_finds_setup_asset(self):
        info = slhtool._release_update_info({
            "tag_name": "v1.0.1",
            "html_url": "https://github.com/bachhoppo18/slh/releases/tag/v1.0.1",
            "assets": [{
                "name": "SLHTool_Setup.exe",
                "browser_download_url": "https://github.com/bachhoppo18/slh/releases/download/v1.0.1/SLHTool_Setup.exe",
                "size": 1234,
                "digest": "sha256:" + ("a" * 64),
            }],
        })

        self.assertEqual(info, (
            True,
            "v1.0.1",
            "https://github.com/bachhoppo18/slh/releases/tag/v1.0.1",
            "https://github.com/bachhoppo18/slh/releases/download/v1.0.1/SLHTool_Setup.exe",
            1234,
            "sha256:" + ("a" * 64),
        ))

    def test_current_or_older_release_is_not_an_update(self):
        info = slhtool._release_update_info({"tag_name": "v1.0.0", "assets": []})

        self.assertFalse(info[0])
        self.assertEqual(info[1], "v1.0.0")

    def test_new_release_without_setup_asset_has_no_download_url(self):
        info = slhtool._release_update_info({"tag_name": "v1.0.1", "assets": []})

        self.assertTrue(info[0])
        self.assertIsNone(info[3])

    def test_new_release_without_valid_digest_disables_auto_install(self):
        info = slhtool._release_update_info({
            "tag_name": "v1.0.1",
            "assets": [{
                "name": "SLHTool_Setup.exe",
                "browser_download_url": "https://github.com/bachhoppo18/slh/releases/download/v1.0.1/SLHTool_Setup.exe",
                "size": 1234,
            }],
        })

        self.assertTrue(info[0])
        self.assertIsNone(info[3])

    def test_installer_download_checks_size_and_digest(self):
        content = b"test installer bytes"
        digest = hashlib.sha256(content).hexdigest()
        release_url = "https://github.com/bachhoppo18/slh/releases/download/v1.0.1/SLHTool_Setup.exe"
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(slhtool, "APP_DATA_DIR", directory), patch.object(
                    slhtool.urllib.request, "urlopen", return_value=_Response(content)):
                path = slhtool.download_update_installer(
                    release_url, "v1.0.1", len(content), f"sha256:{digest}")
                with open(path, "rb") as installer:
                    self.assertEqual(installer.read(), content)

    def test_installer_download_rejects_non_release_url(self):
        with self.assertRaises(ValueError):
            slhtool.download_update_installer(
                "https://example.com/SLHTool_Setup.exe", "v1.0.1", 10)

    def test_installer_download_rejects_digest_mismatch(self):
        content = b"tampered installer bytes"
        release_url = "https://github.com/bachhoppo18/slh/releases/download/v1.0.1/SLHTool_Setup.exe"
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(slhtool, "APP_DATA_DIR", directory), patch.object(
                    slhtool.urllib.request, "urlopen", return_value=_Response(content)):
                with self.assertRaisesRegex(ValueError, "SHA-256"):
                    slhtool.download_update_installer(
                        release_url, "v1.0.1", len(content), "sha256:" + ("0" * 64))
                self.assertFalse(os.path.exists(os.path.join(
                    directory, "updates", "SLHTool_Setup-v1.0.1.exe")))


if __name__ == "__main__":
    unittest.main()