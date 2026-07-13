import unittest

from modules.file_paste.address_splitter import (
    display_width,
    split_japanese_address,
)


class JapaneseAddressSplitterTest(unittest.TestCase):
    def test_l_keeps_administrative_prefix_and_fills_to_thirteen_full_width_characters(self):
        address = "東京都世田谷区北沢二丁目サンライズマンション101号室"

        parts = split_japanese_address(address)

        self.assertTrue(parts["L"].startswith("東京都世田谷区"))
        self.assertEqual(display_width(parts["L"]), 13)
        self.assertEqual("".join(parts[key] for key in "LMNO"), address)
        self.assertLessEqual(display_width(parts["M"]), 16)
        self.assertLessEqual(display_width(parts["N"]), 25)

    def test_keeps_block_and_room_tokens_intact(self):
        parts = split_japanese_address(
            "東京都世田谷区北沢二丁目24-5-101 サンライズマンション 101号室"
        )

        all_parts = "".join(parts[key] for key in "LMNO")
        self.assertIn("二丁目", all_parts)
        self.assertIn("24-5-101", all_parts)
        self.assertIn("101号室", all_parts)
        self.assertLessEqual(display_width(parts["L"]), 13)
        self.assertLessEqual(display_width(parts["M"]), 16)
        self.assertLessEqual(display_width(parts["N"]), 25)

    def test_preserves_overflow_in_o_and_marks_it(self):
        address = (
            "東京都港区芝公園一丁目1-2-3 "
            + "VeryLongBuildingName " * 8
            + "101号室"
        )

        parts = split_japanese_address(address)

        self.assertTrue(parts["overflow"])
        self.assertTrue(parts["O"].endswith("101号室"))


if __name__ == "__main__":
    unittest.main()
