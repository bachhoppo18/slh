import json
import os
import tempfile
import unittest

from slhtool import (
    ZhViTranslator,
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


if __name__ == "__main__":
    unittest.main()