import unittest

from modules.file_paste.template import load_upload_template


class UploadTemplateTest(unittest.TestCase):
    def test_upload_template_has_the_exact_blackcat_layout(self):
        workbook, sheet = load_upload_template()

        self.assertEqual(sheet.max_column, 98)
        self.assertEqual(sheet["A1"].value, "お客様管理番号(内部ID)")
        self.assertEqual(sheet["AB1"].value, "品名１(明细半角50字符以内)")
        self.assertEqual(
            sheet["AD1"].value,
            "品名２(明细超过半角50字符部分放这列，这列也最多50字符)",
        )
        self.assertEqual(sheet.freeze_panes, "A2")
        self.assertIn(sheet["R2"].value, ("様", ""))
        self.assertIn(sheet["S2"].value, (None, ""))
        self.assertIn(sheet["U2"].value, (None, ""))
        self.assertIn(sheet["X2"].value, (None, ""))
        workbook.close()


if __name__ == "__main__":
    unittest.main()
