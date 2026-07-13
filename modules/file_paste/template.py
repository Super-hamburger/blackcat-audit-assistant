from pathlib import Path
import sys

from openpyxl import load_workbook


def template_path():
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return root / "assets" / "templates" / "blackcat_upload_template.xlsx"


def load_upload_template():
    workbook = load_workbook(template_path())
    sheet = workbook.worksheets[0]
    sheet.freeze_panes = "A2"
    return workbook, sheet
