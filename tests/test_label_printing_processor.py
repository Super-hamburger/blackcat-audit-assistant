import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from modules.label_printing.processor import LabelPrintProcessor


class LabelPrintingProcessorTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        base_path = Path(self.temp_dir.name)
        self.source_path = base_path / "source.xlsx"
        self.finished_path = base_path / "finished.xlsx"
        self.output_dir = base_path / "output"

        self.create_workbook(
            self.source_path,
            ["客户编号", "参考单号", "SKU", "数量", "货架"],
            [
                ["12027", "REF-ONE", "SKU-ONE", 1, "2-1"],
                ["12028", "REF-TOUKAN", "SKU-TOUKAN", 1, "1-1"],
            ],
        )
        self.create_workbook(
            self.finished_path,
            ["单号", "收件人电话", "收件邮编", "收件地址", "详细地址", "收件姓名"],
            [
                ["REF-ONE", "09012345678", "1000001", "Tokyo", "1-2-3", "Hanako Sato"],
                ["REF-TOUKAN", "08087654321", "1234567", "Tokyo", "4-5-6", "Taro Yamada"],
            ],
        )
        self.processor = LabelPrintProcessor(
            self.source_path, self.finished_path, [], self.output_dir, "all", False, False
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def create_workbook(path, headers, rows):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(headers)
        for row in rows:
            sheet.append(row)
        workbook.save(path)
        workbook.close()

    def test_finished_rows_map_to_source_customer_and_shelf(self):
        orders = self.processor.load_orders()
        self.assertEqual(orders["REF-ONE"].customer_id, "12027")
        self.assertEqual(orders["REF-ONE"].shelf, "2-1")

    def test_takkyubin_matches_normalized_phone(self):
        page = self.processor.match_page("TEL 090-1234-5678", 0)
        self.assertEqual((page.order.reference, page.label_type), ("REF-ONE", "宅急便"))

    def test_toukan_matches_postal_and_recipient(self):
        page = self.processor.match_page("投函 123-4567 Taro Yamada", 1)
        self.assertEqual((page.order.reference, page.label_type), ("REF-TOUKAN", "投函"))
