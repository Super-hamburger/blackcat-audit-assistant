import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook, load_workbook

from modules.file_paste.converter import (
    MARK_ADDRESS_SPLIT,
    MARK_ITEM_SPLIT,
    MARK_MISSING_REQUIRED,
    NEW_BLACKCAT_HEADERS,
    ONE_PIECE_HEADERS,
    UploadConverter,
)


def color_suffix(fill):
    return (fill.fgColor.rgb or "")[-6:]


class UploadConverterTest(unittest.TestCase):
    def create_workbook(self, path, headers, rows):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(headers)
        for row in rows:
            sheet.append([row.get(header, "") for header in headers])
        workbook.save(path)

    def convert_and_load(self, source_path, temp_dir):
        result = UploadConverter().convert(source_path, Path(temp_dir), open_after=False)
        workbook = load_workbook(result["output_path"])
        return result, workbook.active

    def assert_fill_color(self, cell, expected_fill):
        self.assertEqual(cell.fill.patternType, expected_fill.patternType)
        self.assertEqual(color_suffix(cell.fill), color_suffix(expected_fill))

    def test_one_piece_uses_shelf_alias_sorts_rows_and_maps_sku_to_ad(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "one-piece-shelf.xlsx"
            headers = ONE_PIECE_HEADERS + ["货架", "货位"]
            rows = [
                {
                    "参考单号": "REF-LETTER",
                    "SKU": "SKU-B",
                    "运输方式": "宅急便",
                    "收件人": "张三",
                    "收件电话": "13000000001",
                    "州": "東京都",
                    "城市": "港区",
                    "地址": "芝公園1-1",
                    "地址2": "",
                    "收件公司": "",
                    "收件邮编": "1050011",
                    "货架": "B-2",
                    "货位": "ALIAS-IGNORED",
                },
                {
                    "参考单号": "REF-10",
                    "SKU": "SKU-10",
                    "运输方式": "宅急便",
                    "收件人": "张三",
                    "收件电话": "13000000002",
                    "州": "東京都",
                    "城市": "港区",
                    "地址": "芝公園1-2",
                    "地址2": "",
                    "收件公司": "",
                    "收件邮编": "1050011",
                    "货架": "10-2",
                    "货位": "",
                },
                {
                    "参考单号": "REF-2",
                    "SKU": "SKU-2",
                    "运输方式": "宅急便",
                    "收件人": "张三",
                    "收件电话": "13000000003",
                    "州": "東京都",
                    "城市": "港区",
                    "地址": "芝公園1-3",
                    "地址2": "",
                    "收件公司": "",
                    "收件邮编": "1050011",
                    "货架": "",
                    "货位": "2-3",
                },
                {
                    "参考单号": "REF-WEIRD",
                    "SKU": "SKU-WEIRD",
                    "运输方式": "宅急便",
                    "收件人": "张三",
                    "收件电话": "13000000004",
                    "州": "東京都",
                    "城市": "港区",
                    "地址": "芝公園1-4",
                    "地址2": "",
                    "收件公司": "",
                    "收件邮编": "1050011",
                    "货架": "??",
                    "货位": "",
                },
                {
                    "参考单号": "REF-BLANK",
                    "SKU": "SKU-BLANK",
                    "运输方式": "宅急便",
                    "收件人": "张三",
                    "收件电话": "13000000005",
                    "州": "東京都",
                    "城市": "港区",
                    "地址": "芝公園1-5",
                    "地址2": "",
                    "收件公司": "",
                    "收件邮编": "1050011",
                    "货架": "",
                    "货位": "",
                },
            ]
            self.create_workbook(source_path, headers, rows)

            result, sheet = self.convert_and_load(source_path, temp_dir)

            self.assertEqual(result["source_type"], "一件代发表格")
            self.assertEqual(
                [sheet[f"A{row_no}"].value for row_no in range(2, 7)],
                ["REF-2", "REF-10", "REF-LETTER", "REF-WEIRD", "REF-BLANK"],
            )
            self.assertEqual(
                [sheet[f"AB{row_no}"].value for row_no in range(2, 7)],
                ["2-3", "10-2", "B-2", "??", None],
            )
            self.assertEqual(
                [sheet[f"AD{row_no}"].value for row_no in range(2, 7)],
                ["SKU-2*1", "SKU-10*1", "SKU-B*1", "SKU-WEIRD*1", "SKU-BLANK*1"],
            )

    def test_one_piece_allocates_address_columns_marks_overflow_and_uses_company_in_o(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "one-piece-address.xlsx"
            headers = ONE_PIECE_HEADERS + ["货架"]
            rows = [
                {
                    "参考单号": "REF-OVERFLOW",
                    "SKU": "SKU-OVERFLOW",
                    "运输方式": "宅急便",
                    "收件人": "张三",
                    "收件电话": "13000000010",
                    "州": "東京都",
                    "城市": "港区",
                    "地址": "芝公園1-2-3 BuildingAlpha BuildingBeta BuildingGamma BuildingDelta BuildingEpsilon BuildingZeta",
                    "地址2": "Room505",
                    "收件公司": "Should Not Fit",
                    "收件邮编": "1050011",
                    "货架": "1-1",
                },
                {
                    "参考单号": "REF-COMPANY",
                    "SKU": "SKU-COMPANY",
                    "运输方式": "宅急便",
                    "收件人": "李四",
                    "收件电话": "13000000011",
                    "州": "大阪府",
                    "城市": "堺市",
                    "地址": "東1-2-3 BuildingAlpha",
                    "地址2": "Room505",
                    "收件公司": "Acme Co",
                    "收件邮编": "5900000",
                    "货架": "1-2",
                },
            ]
            self.create_workbook(source_path, headers, rows)

            _, sheet = self.convert_and_load(source_path, temp_dir)

            self.assertEqual(sheet["L2"].value, "東京都港区芝公園1-2-3")
            self.assertEqual(sheet["M2"].value, "BuildingAlpha BuildingBeta")
            self.assertEqual(sheet["N2"].value, "BuildingGamma BuildingDelta")
            self.assertEqual(sheet["O2"].value, "BuildingEpsilon BuildingZeta Room505")
            self.assert_fill_color(sheet["L2"], MARK_ADDRESS_SPLIT)
            self.assert_fill_color(sheet["M2"], MARK_ADDRESS_SPLIT)
            self.assert_fill_color(sheet["N2"], MARK_ADDRESS_SPLIT)
            self.assert_fill_color(sheet["O2"], MARK_MISSING_REQUIRED)

            self.assertEqual(sheet["L3"].value, "大阪府堺市東1-2-3")
            self.assertEqual(sheet["M3"].value, "BuildingAlpha Room505")
            self.assertIsNone(sheet["N3"].value)
            self.assertEqual(sheet["O3"].value, "Acme Co")
            self.assert_fill_color(sheet["L3"], MARK_ADDRESS_SPLIT)
            self.assert_fill_color(sheet["M3"], MARK_ADDRESS_SPLIT)
            self.assertNotEqual(color_suffix(sheet["O3"].fill), color_suffix(MARK_MISSING_REQUIRED))

            self.assertEqual(sheet.max_row, 3)

    def test_new_blackcat_keeps_legacy_address_placement_and_item_mapping(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "new-blackcat.xlsx"
            headers = NEW_BLACKCAT_HEADERS + ["备注"]
            detail = "X" * 55
            rows = [
                {
                    "单号": "NB-1",
                    "收件人电话": "09012345678",
                    "收件邮编": "1050011",
                    "收件地址": "東京都世田谷区北沢二丁目24-5-101",
                    "详细地址": "サンライズマンション千歳船橋 101号室",
                    "收件姓名": "王五",
                    "发件人电话": "0312345678",
                    "sku": "SKU-NB",
                    "明细": detail,
                    "备注": "宅急便",
                }
            ]
            self.create_workbook(source_path, headers, rows)

            result, sheet = self.convert_and_load(source_path, temp_dir)

            self.assertEqual(result["source_type"], "黑猫新版表格")
            self.assertEqual(sheet["L2"].value, "東京都世田谷区北沢二丁目")
            self.assertEqual(sheet["M2"].value, "24-5-101 サンライズマンション千歳船橋 101号室")
            self.assertIsNone(sheet["N2"].value)
            self.assertIsNone(sheet["O2"].value)
            self.assert_fill_color(sheet["L2"], MARK_ADDRESS_SPLIT)
            self.assert_fill_color(sheet["M2"], MARK_ADDRESS_SPLIT)
            self.assertIsNone(sheet["N2"].fill.patternType)
            self.assertIsNone(sheet["O2"].fill.patternType)
            self.assertEqual(sheet["AB2"].value, "SKU-NB")
            self.assertEqual(sheet["AD2"].value, "X" * 50)
            self.assertEqual(sheet["AF2"].value, "X" * 5)
            self.assertEqual(sheet["B2"].value, "0")
            self.assert_fill_color(sheet["AD2"], MARK_ITEM_SPLIT)
            self.assert_fill_color(sheet["AF2"], MARK_ITEM_SPLIT)


if __name__ == "__main__":
    unittest.main()
