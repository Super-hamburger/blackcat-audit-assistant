import tempfile
import unittest
import csv
from pathlib import Path

import fitz
from openpyxl import Workbook

from modules.label_printing.processor import LabelPrintProcessor, LabelPrintingError


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
                ["12027", "REF-ONE", "SKU-ONE", 1, "10-1"],
                ["12028", "REF-TOUKAN", "SKU-TOUKAN", 1, "2-1"],
                ["12027", "REF-MANY", "SKU-MANY", 2, "1-1"],
                ["12028", "REF-MULTI", "SKU-A,SKU-B", 1, "3-1"],
            ],
        )
        self.create_workbook(
            self.finished_path,
            ["单号", "收件人电话", "收件邮编", "收件地址", "详细地址", "收件姓名"],
            [
                ["REF-ONE", "09012345678", "1000001", "Tokyo", "1-2-3", "Hanako Sato"],
                ["REF-TOUKAN", "08087654321", "1234567", "Tokyo", "4-5-6", "Taro Yamada"],
                ["REF-MANY", "07011112222", "1000002", "Tokyo", "7-8-9", "Jiro Sato"],
                ["REF-MULTI", "07033334444", "1000003", "Tokyo", "10-11-12", "Yuki Sato"],
            ],
        )
        self.pdf_paths = [base_path / "labels-1.pdf", base_path / "labels-2.pdf"]
        self.create_pdf(
            self.pdf_paths[0],
            [
                "TEL 090-1234-5678 a123456789012a RACK-2",
                "TOUKAN 123-4567 Taro Yamada a123456789013a RACK-1",
            ],
        )
        self.create_pdf(
            self.pdf_paths[1],
            [
                "TEL 070-1111-2222 a123456789014a EXCLUDED-MANY",
                "TEL 070-3333-4444 a123456789015a EXCLUDED-MULTI",
            ],
        )
        self.processor = LabelPrintProcessor(
            self.source_path, self.finished_path, self.pdf_paths,
            self.output_dir, "all", False, False,
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

    @staticmethod
    def create_pdf(path, page_texts):
        document = fitz.open()
        try:
            for text in page_texts:
                page = document.new_page()
                page.insert_text((72, 72), text)
            document.save(path)
        finally:
            document.close()

    def run_processor(self, scope, split_types):
        return LabelPrintProcessor(
            self.source_path, self.finished_path, self.pdf_paths,
            self.output_dir, scope, split_types, False,
        ).run()

    def run_processor_with_ambiguous_page(self):
        self.create_pdf(
            self.pdf_paths[0],
            ["TEL 090-1234-5678 a123456789012a RACK-2"],
        )
        self.create_pdf(
            self.pdf_paths[1],
            ["TEL 090-1234-5678 a123456789013a DUPLICATE-MATCH"],
        )
        self.create_workbook(
            self.source_path,
            ["客户编号", "参考单号", "SKU", "数量", "货架"],
            [
                ["12027", "REF-ONE", "SKU-ONE", 1, "10-1"],
                ["12028", "REF-TWO", "SKU-TWO", 1, "2-1"],
            ],
        )
        self.create_workbook(
            self.finished_path,
            ["单号", "收件人电话", "收件邮编", "收件地址", "详细地址", "收件姓名"],
            [
                ["REF-ONE", "09012345678", "1000001", "Tokyo", "1-2-3", "Hanako Sato"],
                ["REF-TWO", "09012345678", "1000002", "Tokyo", "4-5-6", "Jiro Sato"],
            ],
        )
        return self.run_processor("all", False)

    @staticmethod
    def output_markers(path):
        document = fitz.open(path)
        try:
            return [page.get_text().strip().split()[-1] for page in document]
        finally:
            document.close()

    def test_all_merged_keeps_only_single_sku_pages_in_shelf_order(self):
        result = self.run_processor(scope="all", split_types=False)

        self.assertEqual(self.output_markers(result["output_paths"][0]), ["RACK-1", "RACK-2"])
        self.assertEqual(result["excluded_pages"], 2)
        self.assertEqual(Path(result["output_paths"][0]).name, "全部客户_合并_货架排序.pdf")

    def test_all_split_writes_toukan_before_takkyubin(self):
        result = self.run_processor(scope="all", split_types=True)

        self.assertEqual([Path(path).name for path in result["output_paths"]], [
            "全部客户_投函_货架排序.pdf", "全部客户_宅急便_货架排序.pdf",
        ])

    def test_customer_scope_writes_one_file_per_customer(self):
        result = self.run_processor(scope="by_customer", split_types=False)

        self.assertEqual([Path(path).name for path in result["output_paths"]], [
            "客户12027_合并_货架排序.pdf", "客户12028_合并_货架排序.pdf",
        ])

    def test_customer_scope_split_skips_empty_type_files(self):
        result = self.run_processor(scope="by_customer", split_types=True)

        self.assertEqual([Path(path).name for path in result["output_paths"]], [
            "客户12027_宅急便_货架排序.pdf", "客户12028_投函_货架排序.pdf",
        ])

    def test_ambiguous_page_writes_no_partial_pdf(self):
        with self.assertRaisesRegex(LabelPrintingError, "无法唯一匹配"):
            self.run_processor_with_ambiguous_page()

        self.assertEqual(list(self.output_dir.glob("**/*.pdf")), [])
        self.assertTrue(any(self.output_dir.glob("**/异常报告.csv")))

    def test_exception_report_records_match_candidates(self):
        with self.assertRaisesRegex(LabelPrintingError, "无法唯一匹配"):
            self.run_processor_with_ambiguous_page()

        report_path = next(self.output_dir.glob("**/异常报告.csv"))
        with report_path.open(encoding="utf-8-sig", newline="") as report_file:
            rows = list(csv.DictReader(report_file))
        self.assertIn("REF-ONE", rows[0]["candidates"])
        self.assertIn("REF-TWO", rows[0]["candidates"])

    def test_duplicate_label_writes_no_partial_pdf(self):
        self.create_pdf(
            self.pdf_paths[1],
            ["TOUKAN 123-4567 Taro Yamada a123456789012a RACK-1"],
        )

        with self.assertRaisesRegex(LabelPrintingError, "重复面单"):
            self.run_processor("all", False)

        self.assertEqual(list(self.output_dir.glob("**/*.pdf")), [])
        self.assertTrue(any(self.output_dir.glob("**/异常报告.csv")))

    def test_finished_rows_map_to_source_customer_and_shelf(self):
        orders = self.processor.load_orders()
        self.assertEqual(orders["REF-ONE"].customer_id, "12027")
        self.assertEqual(orders["REF-ONE"].shelf, "10-1")

    def test_takkyubin_matches_normalized_phone(self):
        page = self.processor.match_page("TEL 090-1234-5678", 0)
        self.assertEqual((page.order.reference, page.label_type), ("REF-ONE", "宅急便"))

    def test_toukan_matches_postal_and_recipient(self):
        page = self.processor.match_page("投函 123-4567 Taro Yamada", 1)
        self.assertEqual((page.order.reference, page.label_type), ("REF-TOUKAN", "投函"))

    def test_japanese_blackcat_finished_headers_map_internal_id_and_recipient_fields(self):
        self.create_workbook(
            self.finished_path,
            [
                "お客様管理番号(内部ID)", "お届け先電話番号", "お届け先郵便番号",
                "お届け先住所", "お届け先住所（アパートマンション名）", "お届け先名",
            ],
            [["REF-ONE", "09012345678", "1000001", "Tokyo", "1-2-3", "Hanako Sato"]],
        )

        order = self.processor.load_orders()["REF-ONE"]

        self.assertEqual(order.reference, "REF-ONE")
        self.assertEqual(order.recipient_name, "Hanako Sato")
        self.assertEqual(order.recipient_phone, "09012345678")
        self.assertEqual(order.recipient_postal, "1000001")
        self.assertEqual(order.recipient_address, "Tokyo 1-2-3")

    def test_phone_ambiguity_reports_original_candidate_references(self):
        self.create_workbook(
            self.source_path,
            ["客户编号", "参考单号", "SKU", "数量", "货架"],
            [
                ["12027", "REF-ONE", "SKU-ONE", 1, "2-1"],
                ["12028", "REF-TWO", "SKU-TWO", 1, "1-1"],
            ],
        )
        self.create_workbook(
            self.finished_path,
            ["单号", "收件人电话", "收件邮编", "收件地址", "详细地址", "收件姓名"],
            [
                ["REF-ONE", "09012345678", "1000001", "Tokyo", "1-2-3", "Hanako Sato"],
                ["REF-TWO", "09012345678", "1000002", "Tokyo", "4-5-6", "Jiro Sato"],
            ],
        )

        with self.assertRaisesRegex(
            Exception, r"REF-ONE.*REF-TWO"
        ):
            self.processor.match_page("TEL 090-1234-5678", 0)
