import hashlib
import json
import unittest
from unittest.mock import patch

import license_client


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class LicenseClientTests(unittest.TestCase):
    def test_valid_key_is_verified_with_read_only_gist_request(self):
        key = "a-valid-license-key"
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        hwid = "a" * 64
        payload = {"keys": {key_hash: hwid}, "machines": {hwid: key_hash}}
        with patch.object(
            license_client.urllib.request, "urlopen", return_value=_Response(payload)
        ) as urlopen:
            result = license_client.activate(key, hwid)

        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, license_client.GIST_RAW_URL)
        self.assertEqual(request.get_method(), "GET")
        self.assertIsNone(request.data)
        self.assertNotIn("Authorization", request.headers)
        self.assertEqual(result["status"], "activated")

    def test_key_bound_to_another_machine_is_rejected(self):
        key = "a-valid-license-key"
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        payload = {"keys": {key_hash: "a" * 64}, "machines": {"a" * 64: key_hash}}
        with patch.object(
            license_client.urllib.request, "urlopen", return_value=_Response(payload)
        ):
            with self.assertRaises(license_client.LicenseError):
                license_client.activate(key, "b" * 64)

    def test_machine_bound_to_another_key_is_rejected(self):
        key = "a-valid-license-key"
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        hwid = "a" * 64
        payload = {"keys": {key_hash: hwid}, "machines": {hwid: "b" * 64}}
        with patch.object(
            license_client.urllib.request, "urlopen", return_value=_Response(payload)
        ):
            with self.assertRaises(license_client.LicenseError):
                license_client.activate(key, hwid)


if __name__ == "__main__":
    unittest.main()