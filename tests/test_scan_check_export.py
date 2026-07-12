import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook, load_workbook

from modules.scan_check.module import ScanCheckService


class ScanCheckExceptionExportTest(unittest.TestCase):
    def test_export_exceptions_preserves_full_source_rows_and_trace_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "source.xlsx"
            output_path = Path(temp_dir) / "exceptions.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            sheet.append(["出库单号", "SKU", "数量", "商品名称", "客户", "备注"])
            sheet.append(["SO-100", "SKU-01", 1, "测试商品", "客户 A", "原始备注"])
            workbook.save(source_path)

            service = ScanCheckService()
            service.load_excel(source_path)
            service.start()
            service.scan("SO-100")
            service.scan("SKU-01")
            service.scan("SKU-01")
            service.scan("SKU-01")
            service.scan("UNKNOWN-SKU")

            service.export_exceptions(output_path)

            exported = load_workbook(output_path, data_only=True).active
            rows = list(exported.iter_rows(values_only=True))
            self.assertEqual(
                rows[0],
                ("出库单号", "SKU", "数量", "商品名称", "客户", "备注", "异常时间", "异常原因", "扫码内容"),
            )

            source_rows = [row for row in rows[1:] if row[0] == "SO-100"]
            self.assertEqual(len(source_rows), 2)
            for row in source_rows:
                self.assertEqual(row[:6], ("SO-100", "SKU-01", 1, "测试商品", "客户 A", "原始备注"))
                self.assertEqual(row[7], "该 SKU 已扫够数量")
                self.assertEqual(row[8], "SKU-01")

            unmatched_rows = [row for row in rows[1:] if row[8] == "UNKNOWN-SKU"]
            self.assertEqual(len(unmatched_rows), 1)
            self.assertEqual(unmatched_rows[0][:6], (None, None, None, None, None, None))
            self.assertEqual(unmatched_rows[0][7], "SKU 不属于当前出库单")

    def test_export_unmatched_source_rows_ignores_quantity_two_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "source.xlsx"
            output_path = Path(temp_dir) / "unmatched.csv"
            workbook = Workbook()
            sheet = workbook.active
            headers = ["出库单号", "SKU", "数量", "商品名称", "客户", "备注"]
            matched_source_row = ["SO-100", "SKU-01", 1, "已匹配商品", "客户 A", "保留完整数据"]
            ignored_source_row = ["SO-100", "SKU-02", 2, "忽略商品", "客户 A", "数量为二"]
            unmatched_source_row = ["SO-200", "SKU-03", 1, "未匹配商品", "客户 B", "保留完整数据"]
            sheet.append(headers)
            sheet.append(matched_source_row)
            sheet.append(ignored_source_row)
            sheet.append(unmatched_source_row)
            workbook.save(source_path)

            service = ScanCheckService()
            summary = service.load_excel(source_path)
            self.assertEqual(summary["item_count"], 2)
            self.assertEqual(summary["total_quantity"], 2)

            service.start()
            service.scan("SO-100")
            service.scan("SKU-01")
            output = service.export_unmatched_source_rows(output_path)

            self.assertEqual(Path(output).suffix, ".xlsx")
            exported = load_workbook(output, data_only=True).active
            self.assertEqual(list(exported.iter_rows(values_only=True)), [tuple(headers), tuple(unmatched_source_row)])


if __name__ == "__main__":
    unittest.main()
