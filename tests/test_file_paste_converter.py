import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook, load_workbook

from modules.file_paste.converter import (
    MARK_ADDRESS_OVERFLOW,
    MARK_QUANTITY_ISSUE,
    NEW_BLACKCAT_HEADERS,
    ONE_PIECE_HEADERS,
    UploadConverter,
)
from modules.file_paste.template import load_upload_template


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

    def convert_and_load_one_piece(self, rows):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "one-piece.xlsx"
            headers = ONE_PIECE_HEADERS + ["数量", "货架"]
            self.create_workbook(source_path, headers, rows)
            result, sheet = self.convert_and_load(source_path, temp_dir)
            values = [[cell.value for cell in row] for row in sheet.iter_rows()]
            fills = {
                coordinate: color_suffix(sheet[coordinate].fill)
                for coordinate in ("AD2", "O2")
            }
        return result, values, fills

    def convert_and_load_blackcat(self, row):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "blackcat.xlsx"
            self.create_workbook(source_path, NEW_BLACKCAT_HEADERS, [row])
            result, sheet = self.convert_and_load(source_path, temp_dir)
            values = [[cell.value for cell in line] for line in sheet.iter_rows()]
        return result, values

    def one_piece_row(self, reference, sku, quantity, shelf, address="芝公園1-2-3"):
        return {
            "参考单号": reference,
            "SKU": sku,
            "数量": quantity,
            "货架": shelf,
            "运输方式": "宅急便",
            "收件人": "山田太郎",
            "收件电话": "0312345678",
            "州": "東京都",
            "城市": "港区",
            "地址": address,
            "地址2": "101号室",
            "收件公司": "",
            "收件邮编": "1050011",
        }

    def test_one_piece_merges_each_sku_with_quantity_and_sorts_shelves(self):
        result, values, _ = self.convert_and_load_one_piece([
            self.one_piece_row("MULTI", "sku-a,sku-b", "*1+*1", "13-6-3-2"),
            self.one_piece_row("EARLY", "sku-c", 1, "13-3-3-2"),
            self.one_piece_row("BOTTOM", "sku-d", 1, "16-1-1-3,13-6-3-3"),
        ])

        self.assertEqual([row[0] for row in values[1:4]], ["EARLY", "MULTI", "BOTTOM"])
        self.assertEqual(values[1][27], "13-3-3-2")
        self.assertEqual(values[2][29], "sku-a*1,sku-b*1")
        self.assertEqual(result["quantity_issue_count"], 0)

    def test_one_piece_moves_complete_sku_overflow_items_from_ad_to_ac(self):
        sku_one = "a" * 20
        sku_two = "b" * 20
        sku_three = "c" * 20
        result, values, _ = self.convert_and_load_one_piece([
            self.one_piece_row(
                "OVERFLOW",
                f"{sku_one},{sku_two},{sku_three}",
                "*1+*1+*1",
                "1-1",
            ),
        ])

        self.assertEqual(values[1][28], f"{sku_three}*1")
        self.assertEqual(values[1][29], f"{sku_one}*1,{sku_two}*1")
        self.assertLessEqual(len(values[1][29]), 50)
        self.assertEqual(result["quantity_issue_count"], 0)

    def test_one_piece_moves_a_single_overlong_sku_item_to_ac(self):
        long_sku = "x" * 51
        _, values, _ = self.convert_and_load_one_piece([
            self.one_piece_row("LONG-SKU", long_sku, 1, "1-1"),
        ])

        self.assertEqual(values[1][28], f"{long_sku}*1")
        self.assertIsNone(values[1][29])

    def test_blackcat_uses_template_header_sku_and_detail_columns(self):
        result, values = self.convert_and_load_blackcat({
            "单号": "NB-1",
            "收件人电话": "09012345678",
            "收件邮编": "1050011",
            "收件地址": "東京都世田谷区北沢二丁目24-5-101",
            "详细地址": "サンライズマンション 101号室",
            "收件姓名": "王五",
            "发件人电话": "0312345678",
            "sku": "sku-a",
            "明细": "*3",
        })
        template_book, template_sheet = load_upload_template()
        expected_headers = [cell.value for cell in template_sheet[1]]
        template_book.close()

        self.assertEqual(values[0], expected_headers)
        self.assertEqual(len(values[0]), 98)
        self.assertEqual(values[1][0], "NB-1")
        self.assertEqual(values[1][27], "sku-a")
        self.assertEqual(values[1][29], "*3")
        self.assertEqual(result["source_type"], "黑猫新版表格")

    def test_converter_marks_ambiguous_quantity_without_dropping_order(self):
        result, values, fills = self.convert_and_load_one_piece([
            self.one_piece_row("AMBIGUOUS", "sku-a,sku-b", 5, "1-1"),
        ])

        self.assertEqual(values[1][0], "AMBIGUOUS")
        self.assertIsNone(values[1][29])
        self.assertEqual(result["quantity_issue_count"], 1)
        self.assertEqual(result["quantity_issue_orders"], ["AMBIGUOUS"])
        self.assertEqual(fills["AD2"], color_suffix(MARK_QUANTITY_ISSUE))

    def test_converter_preserves_overlong_address_in_o_and_marks_it(self):
        long_address = "芝公園一丁目1-2-3 " + "VeryLongBuildingName " * 8 + "101号室"
        result, values, fills = self.convert_and_load_one_piece([
            self.one_piece_row("LONG", "sku-long", 1, "1-1", long_address),
        ])

        self.assertTrue(values[1][14].endswith("101号室"))
        self.assertEqual(result["address_overflow_count"], 1)
        self.assertEqual(fills["O2"], color_suffix(MARK_ADDRESS_OVERFLOW))


if __name__ == "__main__":
    unittest.main()
