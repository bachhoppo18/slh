import json
import os
import tempfile
import unittest

from slhtool import ZhViTranslator


class TranslatorAdminOverlayTests(unittest.TestCase):
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