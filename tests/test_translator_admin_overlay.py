import json
import os
import tempfile
import unittest

from slhtool import (
    TRANS_DEFAULT_SETTINGS,
    ZhViTranslator,
    _trans_migrate_dictionary_urls,
    _trans_mirror_urls,
    exclude_names_already_in_set,
    filter_name_counter_by_set,
)


class TranslatorAdminOverlayTests(unittest.TestCase):
    def test_hanlp_counter_excludes_names_in_selected_set(self):
        filtered, excluded = filter_name_counter_by_set(
            {"林动": 8, "牧尘": 4}, {"林动": "Lâm Động"}
        )

        self.assertEqual(filtered, {"牧尘": 4})
        self.assertEqual(excluded, ["林动"])

    def test_names_already_in_selected_set_are_excluded(self):
        rows = [("林动", "3 lần", "Chính"), ("牧尘", "2 lần", "Phụ")]

        new_rows, existing_rows = exclude_names_already_in_set(
            rows, {"林动": "Lâm Động"}
        )

        self.assertEqual(new_rows, [("牧尘", "2 lần", "Phụ")])
        self.assertEqual(existing_rows, [(("林动", "3 lần", "Chính"), "Lâm Động")])

    def test_remote_entries_merge_over_cached_dictionary_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = {
                "name": os.path.join(directory, "Name.json"),
                "vp": os.path.join(directory, "VP.json"),
                "hanviet": os.path.join(directory, "HanViet.json"),
            }
            for name, path in paths.items():
                with open(path, "w", encoding="utf-8") as file:
                    json.dump({"cached": "cũ", "replace": "cũ"}, file, ensure_ascii=False)

            translator = ZhViTranslator()
            translator.load(paths["name"], paths["vp"], paths["hanviet"], overlays={
                "name": {"replace": "mới", "remote": "mục mới"},
                "vp": {"remote-vp": "dịch VP"},
                "hanviet": {"远": "viễn"},
            })

        self.assertEqual(translator.name_raw["cached"]["val"], "cũ")
        self.assertEqual(translator.name_raw["replace"]["val"], "mới")
        self.assertEqual(translator.name_raw["remote"]["val"], "mục mới")
        self.assertEqual(translator.vp_raw["remote-vp"]["val"], "dịch VP")
        self.assertEqual(translator.hv_dict["远"]["val"], "viễn")

    def test_default_dictionary_urls_do_not_use_refs_heads(self):
        self.assertNotIn("refs/heads/main", TRANS_DEFAULT_SETTINGS["nameUrl"])
        self.assertNotIn("refs/heads/main", TRANS_DEFAULT_SETTINGS["vpUrl"])
        self.assertNotIn("refs/heads/main", TRANS_DEFAULT_SETTINGS["hvUrl"])

    def test_dictionary_urls_use_release_assets(self):
        for key in ("nameUrl", "vpUrl", "hvUrl"):
            self.assertIn("/releases/latest/download/", TRANS_DEFAULT_SETTINGS[key])

    def test_migrate_old_dictionary_urls_but_preserve_custom_urls(self):
        settings = {
            "nameUrl": "https://raw.githubusercontent.com/bachhoppo18/slh/refs/heads/main/translate/Name.json",
            "vpUrl": "https://raw.githubusercontent.com/bachhoppo18/slh/main/translate/VP.json",
            "hvUrl": "https://example.com/custom-hanviet.json",
        }

        migrated = _trans_migrate_dictionary_urls(settings)

        self.assertEqual(migrated["nameUrl"], TRANS_DEFAULT_SETTINGS["nameUrl"])
        self.assertEqual(migrated["vpUrl"], TRANS_DEFAULT_SETTINGS["vpUrl"])
        self.assertEqual(migrated["hvUrl"], "https://example.com/custom-hanviet.json")

    def test_trans_mirror_urls_strip_refs_prefixes(self):
        urls = _trans_mirror_urls(
            "https://raw.githubusercontent.com/bachhoppo18/slh/refs/heads/main/translate/Name.json"
        )
        self.assertIn("https://raw.githubusercontent.com/bachhoppo18/slh/main/translate/Name.json", urls)
        self.assertIn("https://cdn.jsdelivr.net/gh/bachhoppo18/slh@main/translate/Name.json", urls)

    def test_load_handles_invalid_or_empty_dictionary_files(self):
        with tempfile.TemporaryDirectory() as directory:
            name_path = os.path.join(directory, "Name.json")
            vp_path = os.path.join(directory, "VP.json")
            hv_path = os.path.join(directory, "HanViet.json")
            for path in (name_path, vp_path, hv_path):
                with open(path, "w", encoding="utf-8") as file:
                    file.write("{not valid json")

            translator = ZhViTranslator()
            translator.load(name_path, vp_path, hv_path)

        self.assertEqual(translator.name_raw, {})
        self.assertEqual(translator.vp_raw, {})
        self.assertEqual(translator.hv_dict, {})


if __name__ == "__main__":
    unittest.main()