import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fitz

from modules.label_printing import processor as label_printing_processor
from modules.label_printing.processor import LabelPrintingError


class PdfOnlyLabelPrintingProcessorTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.pdf_path = self.base_path / "labels.pdf"
        self.second_pdf_path = self.base_path / "labels-second.pdf"
        self.output_dir = self.base_path / "output"

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def make_pdf(path, page_texts):
        document = fitz.open()
        try:
            for text in page_texts:
                page = document.new_page()
                page.insert_text((72, 72), text)
            document.save(path)
        finally:
            document.close()

    @staticmethod
    def output_markers(path):
        document = fitz.open(path)
        try:
            return [page.get_text().strip().split()[-1] for page in document]
        finally:
            document.close()

    def run_pdf_only(self, scope="all", split_types=False, open_after=False, output_dir=None):
        pdf_paths = [self.pdf_path]
        if self.second_pdf_path.exists():
            pdf_paths.append(self.second_pdf_path)
        return label_printing_processor.PdfOnlyLabelPrintProcessor(
            pdf_paths,
            output_dir or self.output_dir,
            scope=scope,
            split_types=split_types,
            open_after=open_after,
        ).run()

    def test_pdf_only_processor_has_no_legacy_excel_processor_dependency(self):
        self.make_pdf(self.pdf_path, ["TEL a123456789012a LP[2-1/12027]"])

        self.assertFalse(hasattr(label_printing_processor, "LabelPrintProcessor"))
        result = self.run_pdf_only(scope="all", split_types=False)
        self.assertEqual(result["printed_pages"], 1)

    def test_pdf_only_prints_marked_pages_in_natural_shelf_order(self):
        self.make_pdf(self.pdf_path, [
            "TEL a123456789012a LP[10-1/12029]",
            "TEL a123456789013a ordinary-multi-sku-page",
            "TOUKAN a123456789014a LP[2-1/12027]",
        ])
        result = self.run_pdf_only(scope="all", split_types=False)

        self.assertEqual(
            self.output_markers(result["output_paths"][0]),
            ["LP[2-1/12027]", "LP[10-1/12029]"],
        )
        self.assertEqual(
            (
                result["total_pages"], result["matched_pages"],
                result["printed_pages"], result["excluded_pages"],
            ),
            (3, 2, 2, 1),
        )

    def test_pdf_only_malformed_marker_writes_no_pdf(self):
        self.make_pdf(self.pdf_path, ["LP[2-1/12027", "LP[3-1/12028]"])

        with self.assertRaisesRegex(LabelPrintingError, "标记格式错误"):
            self.run_pdf_only()

        self.assertEqual(list(self.output_dir.glob("**/*.pdf")), [])
        self.assertTrue(any(self.output_dir.glob("**/异常报告.csv")))

    def test_pdf_only_rejects_marker_outside_writer_contract_without_pdf(self):
        invalid_markers = (
            "LP[ /12027]",
            "LP[2-1/ ]",
            f"LP[{'x' * 41}/12027]",
            "LP[2-1/customer]",
            "LP[2/1/12027]",
        )

        for marker_index, marker in enumerate(invalid_markers):
            with self.subTest(marker=marker):
                self.make_pdf(self.pdf_path, [f"TEL a123456789012a {marker}"])
                marker_output_dir = self.output_dir / str(marker_index)

                with self.assertRaises(LabelPrintingError):
                    self.run_pdf_only(output_dir=marker_output_dir)

                self.assertEqual(list(marker_output_dir.glob("**/*.pdf")), [])

    def test_pdf_only_rejects_incomplete_marker_alongside_valid_marker(self):
        self.make_pdf(
            self.pdf_path,
            ["TEL a123456789012a LP[2-1/12027] LP[3-1/12028"],
        )

        with self.assertRaisesRegex(LabelPrintingError, "标记格式错误"):
            self.run_pdf_only()

        self.assertEqual(list(self.output_dir.glob("**/*.pdf")), [])
        self.assertTrue(any(self.output_dir.glob("**/异常报告.csv")))

    def test_pdf_only_rejects_multiple_different_markers_without_partial_pdf(self):
        self.make_pdf(
            self.pdf_path,
            ["TEL a123456789012a LP[2-1/12027] LP[3-1/12028]"],
        )

        with self.assertRaisesRegex(LabelPrintingError, "多个不同 LP 标记"):
            self.run_pdf_only()

        self.assertEqual(list(self.output_dir.glob("**/*.pdf")), [])
        self.assertTrue(any(self.output_dir.glob("**/异常报告.csv")))

    def test_pdf_only_split_writes_toukan_before_takkyubin(self):
        self.make_pdf(self.pdf_path, [
            "TEL a123456789012a LP[2-1/12027]",
            "TOUKAN a123456789013a LP[1-1/12028]",
        ])
        result = self.run_pdf_only(split_types=True)

        self.assertEqual([Path(path).name for path in result["output_paths"]], [
            "全部客户_投函_货架排序.pdf", "全部客户_宅急便_货架排序.pdf",
        ])

    def test_pdf_only_customer_scope_skips_empty_type_files(self):
        self.make_pdf(self.pdf_path, [
            "TEL a123456789012a LP[2-1/12027]",
            "TOUKAN a123456789013a LP[1-1/12028]",
        ])
        result = self.run_pdf_only(scope="by_customer", split_types=True)

        self.assertEqual([Path(path).name for path in result["output_paths"]], [
            "客户12027_宅急便_货架排序.pdf",
            "客户12028_投函_货架排序.pdf",
        ])

    def test_pdf_only_detects_formatted_twelve_digit_duplicate_label_id(self):
        self.make_pdf(self.pdf_path, ["TEL a123456789012a LP[2-1/12027]"])
        self.make_pdf(
            self.second_pdf_path,
            ["TOUKAN a1234-5678-9012a LP[1-1/12028]"],
        )

        with self.assertRaisesRegex(LabelPrintingError, "重复面单"):
            self.run_pdf_only()

        self.assertEqual(list(self.output_dir.glob("**/*.pdf")), [])
        self.assertTrue(any(self.output_dir.glob("**/异常报告.csv")))

    def test_pdf_only_keeps_input_order_for_pages_on_the_same_shelf(self):
        self.make_pdf(self.pdf_path, ["TEL a123456789012a LP[2-1/12027]"])
        self.make_pdf(
            self.second_pdf_path,
            ["TOUKAN a123456789013a LP[2-1/12028]"],
        )
        result = self.run_pdf_only()

        self.assertEqual(
            self.output_markers(result["output_paths"][0]),
            ["LP[2-1/12027]", "LP[2-1/12028]"],
        )

    def test_pdf_only_open_after_false_does_not_open_output_directory(self):
        self.make_pdf(self.pdf_path, ["TEL a123456789012a LP[2-1/12027]"])

        with patch.object(label_printing_processor, "open_directory") as opener:
            self.run_pdf_only(open_after=False)

        opener.assert_not_called()

    def test_cleanup_continues_after_one_created_file_cannot_be_deleted(self):
        first_path = self.base_path / "first.pdf"
        second_path = self.base_path / "second.pdf"
        deleted_paths = []

        def unlink(path, *, missing_ok=False):
            deleted_paths.append(path)
            if path == first_path:
                raise OSError("first output is locked")

        with patch.object(Path, "unlink", autospec=True, side_effect=unlink):
            label_printing_processor._remove_created_files([first_path, second_path])

        self.assertEqual(deleted_paths, [first_path, second_path])

    def test_pdf_only_with_no_markers_returns_zero_outputs(self):
        self.make_pdf(self.pdf_path, ["TEL a123456789012a ordinary-multi-sku-page"])
        result = self.run_pdf_only()

        self.assertEqual(result["output_paths"], [])
        self.assertEqual(
            (
                result["total_pages"], result["matched_pages"],
                result["printed_pages"], result["excluded_pages"],
            ),
            (1, 0, 0, 1),
        )
        self.assertEqual(list(self.output_dir.glob("**/*.pdf")), [])
