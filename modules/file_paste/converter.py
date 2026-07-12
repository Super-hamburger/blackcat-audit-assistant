from pathlib import Path
from datetime import datetime
import os
import re
import unicodedata

from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

from modules.file_paste.address_splitter import split_delivery_address, split_delivery_address_cells
from core.file_safe import ensure_writable_dir


OUTPUT_HEADERS = [
    "お客様管理番号(内部ID)", "送り状種類", "クール区分", "伝票番号",
    "出荷予定日(发货日期)", "お届け予定（指定）日(配达日期)", "配達時間帯",
    "お届け先コード", "お届け先電話番号", "お届け先電話番号枝番",
    "お届け先郵便番号", "お届け先住所", "お届け先住所（アパートマンション名）",
    "お届け先会社・部門名１", "お届け先会社・部門名２", "お届け先名",
    "お届け先名略称カナ", "敬称", "ご依頼主コード", "ご依頼主電話番号",
    "ご依頼主電話番号枝番", "ご依頼主郵便番号", "ご依頼主住所",
    "ご依頼主住所（アパートマンション名）", "ご依頼主名", "ご依頼主略称カナ",
    "品名コード１", "品名１(明细半角50字符以内)", "品名コード２",
    "品名２(明细超过半角50字符部分放这列，这列也最多50字符)", "荷扱い１(商家)",
    "荷扱い２", "記事", "コレクト代金引換額（税込）", "コレクト内消費税額等",
    "営業所止置き", "営業所コード", "発行枚数", "個数口枠の印字",
    "ご請求先顧客コード", "ご請求先分類コード", "運賃管理番号",
]

ONE_PIECE_HEADERS = [
    "参考单号", "SKU", "运输方式", "收件人", "收件电话",
    "州", "城市", "地址", "地址2", "收件公司", "收件邮编"
]

NEW_BLACKCAT_HEADERS = [
    "单号", "收件人电话", "收件邮编", "收件地址", "详细地址",
    "收件姓名", "发件人电话", "sku", "明细"
]

MARK_ADDRESS_SPLIT = PatternFill("solid", fgColor="FFF2CC")  # light yellow
MARK_MISSING_REQUIRED = PatternFill("solid", fgColor="F4CCCC")  # light red
MARK_ITEM_SPLIT = PatternFill("solid", fgColor="D9EAD3")  # light green


def norm(value):
    if value is None:
        return ""
    return str(value).strip()


def normalized_header(value):
    return norm(value).replace("\n", "").replace("\r", "").replace(" ", "")


def build_header_map(ws):
    result = {}
    for cell in ws[1]:
        key = normalized_header(cell.value)
        if key:
            result[key] = cell.column
    return result


def has_headers(header_map, names):
    return all(normalized_header(name) in header_map for name in names)


def read(row, header_map, name):
    idx = header_map.get(normalized_header(name))
    return "" if idx is None else norm(row[idx - 1].value)


def ship_code(value):
    value = norm(value)
    if "投函" in value:
        return "A"
    if "宅急便" in value:
        return "0"
    return ""


def split_pref_city_from_full_address(full_address):
    full_address = norm(full_address)
    if not full_address:
        return "", "", ""

    prefecture = ""
    city = ""
    street = full_address

    for marker in ["都", "道", "府", "県"]:
        pos = street.find(marker)
        if 0 < pos <= 4:
            prefecture = street[:pos + 1]
            street = street[pos + 1:]
            break

    positions = []
    for marker in ["市", "区", "郡", "町", "村"]:
        pos = street.find(marker)
        if pos >= 0:
            positions.append(pos)
    if positions:
        pos = min(positions)
        city = street[:pos + 1]
        street = street[pos + 1:]

    return prefecture, city, street


def split_item_text(value):
    value = norm(value)
    if len(value) <= 50:
        return value, ""
    return value[:50], value[50:100]


def normalize_digits(value):
    return unicodedata.normalize("NFKC", value)


def shelf_sort_key(value):
    value = norm(value)
    if not value:
        return (2,)

    if re.match(r"^[0-9０-９]", value):
        parts = re.split(r"[-－]", value)
        if all(re.fullmatch(r"[0-9０-９]+", part) for part in parts):
            return (0, tuple(int(normalize_digits(part)) for part in parts))
        return (2,)

    if re.match(r"^[A-Za-z]", value):
        return (1, value.casefold())

    return (2,)


class UploadConverter:
    def convert(self, source_path, output_dir, open_after=True):
        source_path = Path(source_path)
        output_dir = ensure_writable_dir(output_dir, 'output')

        wb = load_workbook(source_path, data_only=True)
        ws = wb.worksheets[0]

        header_map = build_header_map(ws)

        if has_headers(header_map, ONE_PIECE_HEADERS):
            source_type = "一件代发表格"
            row_reader = self.read_one_piece_row
        elif has_headers(header_map, NEW_BLACKCAT_HEADERS):
            source_type = "黑猫新版表格"
            row_reader = self.read_new_blackcat_row
        else:
            raise ValueError(
                "无法识别表格格式。需要一件代发表格或黑猫新版表格。\n"
                "一件代发表格需要：参考单号、SKU、运输方式、收件人、收件电话、州、城市、地址、地址2、收件公司、收件邮编\n"
                "黑猫新版表格需要：单号、收件人电话、收件邮编、收件地址、详细地址、收件姓名、发件人电话、sku、明细"
            )

        out_wb = Workbook()
        out_ws = out_wb.active
        out_ws.title = "output"

        for col, header in enumerate(OUTPUT_HEADERS, 1):
            cell = out_ws.cell(1, col, header)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="1F2937")
            cell.alignment = Alignment(horizontal="center", vertical="center")

        row_no = 2
        split_count = 0
        item_split_count = 0
        missing_count = 0

        source_rows = [row_reader(source_row, header_map) for source_row in ws.iter_rows(min_row=2)]
        if source_type == "一件代发表格":
            source_rows.sort(key=lambda data: shelf_sort_key(data["shelf"]))

        for data in source_rows:
            if not data["reference"]:
                continue

            if source_type == "一件代发表格":
                address = split_delivery_address_cells(
                    data["prefecture"],
                    data["city"],
                    data["street"],
                    data["apartment"],
                )
                address_was_split = any(address[column] for column in ("M", "N", "O"))
                company_value = "" if address["O"] else data["company"]
            else:
                address_l, address_m = split_delivery_address(
                    data["prefecture"],
                    data["city"],
                    data["street"],
                    data["apartment"],
                )
                address = {"L": address_l, "M": address_m, "N": data["company"], "O": ""}
                original_main = data["prefecture"] + data["city"] + data["street"]
                address_was_split = bool(address_m and original_main != address_l)
                company_value = ""

            if address_was_split:
                split_count += 1

            item_text = data["item_name"]
            if source_type == "一件代发表格":
                item_text = f'{data["sku"]}*1' if data["sku"] else "*1"
            item1, item2 = split_item_text(item_text)
            item_was_split = bool(item2)
            if item_was_split:
                item_split_count += 1

            values = {
                "A": data["reference"],
                "B": data["ship_code"],
                "E": datetime.now().strftime("%Y%m%d"),
                "I": data["phone"],
                "K": data["postal"],
                "L": address["L"],
                "M": address["M"],
                "N": address["N"],
                "O": address["O"] or company_value,
                "P": data["recipient"],
                "R": "様",
                "T": data["sender_phone"] or "050-1724-5220",
                "V": "590-0533",
                "W": "大阪府泉南市中小路2-780",
                "Y": "祺商倉庫発送",
                "AB": data["shelf"] if source_type == "一件代发表格" else data["sku"],
                "AD": item1 or "*1",
                "AF": item2,
                "AJ": "0",
                "AL": "1",
                "AM": "1",
                "AN": "08025537182",
                "AP": "01",
            }

            for col_letter, value in values.items():
                out_ws[f"{col_letter}{row_no}"] = str(value)

            # Core Intelligence marking in the final file.
            if address_was_split:
                if source_type == "一件代发表格":
                    for col_letter in ("L", "M", "N", "O"):
                        if not address[col_letter]:
                            continue
                        fill = MARK_MISSING_REQUIRED if col_letter == "O" and address["overflow"] else MARK_ADDRESS_SPLIT
                        out_ws[f"{col_letter}{row_no}"].fill = fill
                    out_ws[f"M{row_no}"].comment = None
                else:
                    out_ws[f"L{row_no}"].fill = MARK_ADDRESS_SPLIT
                    out_ws[f"M{row_no}"].fill = MARK_ADDRESS_SPLIT
                    out_ws[f"M{row_no}"].comment = None

            if item_was_split:
                out_ws[f"AD{row_no}"].fill = MARK_ITEM_SPLIT
                out_ws[f"AF{row_no}"].fill = MARK_ITEM_SPLIT

            missing_required = []
            if not data["phone"]:
                missing_required.append("I")
            if not data["postal"]:
                missing_required.append("K")
            if not address["L"]:
                missing_required.append("L")
            if not data["recipient"]:
                missing_required.append("P")
            if missing_required:
                missing_count += 1
                for col_letter in missing_required:
                    out_ws[f"{col_letter}{row_no}"].fill = MARK_MISSING_REQUIRED

            row_no += 1

        for row in out_ws.iter_rows():
            for cell in row:
                cell.number_format = "@"

        for col in range(1, len(OUTPUT_HEADERS) + 1):
            letter = get_column_letter(col)
            width = min(max(len(str(out_ws.cell(1, col).value or "")) + 2, 10), 36)
            out_ws.column_dimensions[letter].width = width

        out_ws.freeze_panes = "A2"

        output_path = output_dir / f"黑猫上传表_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        out_wb.save(output_path)

        if open_after:
            os.startfile(output_path)

        return {
            "output_path": str(output_path),
            "row_count": row_no - 2,
            "split_count": split_count,
            "item_split_count": item_split_count,
            "missing_count": missing_count,
            "source_type": source_type,
        }

    def read_one_piece_row(self, row, header_map):
        return {
            "reference": read(row, header_map, "参考单号"),
            "ship_code": ship_code(read(row, header_map, "运输方式")),
            "phone": read(row, header_map, "收件电话"),
            "postal": read(row, header_map, "收件邮编"),
            "prefecture": read(row, header_map, "州"),
            "city": read(row, header_map, "城市"),
            "street": read(row, header_map, "地址"),
            "apartment": read(row, header_map, "地址2"),
            "company": read(row, header_map, "收件公司"),
            "recipient": read(row, header_map, "收件人"),
            "sender_phone": "",
            "shelf": read(row, header_map, "货架") or read(row, header_map, "货位"),
            "sku": read(row, header_map, "SKU"),
            "item_name": "*1",
        }

    def read_new_blackcat_row(self, row, header_map):
        full_address = read(row, header_map, "收件地址")
        prefecture, city, street = split_pref_city_from_full_address(full_address)

        remark = read(row, header_map, "备注")
        derived_ship_code = "A" if "投函" in remark else ("0" if "宅急便" in remark else "")

        return {
            "reference": read(row, header_map, "单号"),
            "ship_code": derived_ship_code,
            "phone": read(row, header_map, "收件人电话"),
            "postal": read(row, header_map, "收件邮编"),
            "prefecture": prefecture,
            "city": city,
            "street": street,
            "apartment": read(row, header_map, "详细地址"),
            "company": "",
            "recipient": read(row, header_map, "收件姓名"),
            "sender_phone": read(row, header_map, "发件人电话"),
            "shelf": "",
            "sku": read(row, header_map, "sku"),
            "item_name": read(row, header_map, "明细"),
        }
