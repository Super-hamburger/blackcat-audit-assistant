from dataclasses import dataclass
from pathlib import Path
import re

from openpyxl import load_workbook

from modules.file_paste.converter import resolve_sku_quantities, split_skus


RAW_REQUIRED_HEADERS = ("客户编号", "参考单号", "SKU", "数量", "货架")
FINISHED_REQUIRED_HEADERS = (
    "单号", "收件人电话", "收件邮编", "收件地址", "详细地址", "收件姓名",
)


class LabelPrintingError(Exception):
    """Raised when a label page cannot be mapped to one unique order."""


@dataclass(frozen=True)
class PrintOrder:
    reference: str
    customer_id: str
    shelf: str
    sku: str
    quantity: str
    sku_kind: str
    recipient_name: str
    recipient_phone: str
    recipient_postal: str
    recipient_address: str


@dataclass(frozen=True)
class LabelPage:
    pdf_path: Path
    page_index: int
    input_order: int
    label_type: str
    label_id: str
    order: PrintOrder


def normalize_digits(value):
    return "".join(re.findall(r"\d+", str(value or "")))


def normalize_text(value):
    return re.sub(r"[\s\u3000\-－]", "", str(value or "")).casefold()


def classify_sku(sku, quantity):
    item_text, issue = resolve_sku_quantities(sku, quantity)
    if issue is None and len(split_skus(sku)) == 1 and item_text.endswith("*1"):
        return "SKU×1"
    return "SKU×N和多SKU"


def detect_label_type(text):
    return "投函" if "投函" in str(text or "") else "宅急便"


class LabelPrintProcessor:
    def __init__(
        self, source_path, finished_path, pdf_paths, output_dir,
        scope="all", split_types=False, open_after=True,
    ):
        self.source_path = Path(source_path)
        self.finished_path = Path(finished_path)
        self.pdf_paths = [Path(path) for path in pdf_paths]
        self.output_dir = Path(output_dir)
        self.scope = scope
        self.split_types = bool(split_types)
        self.open_after = bool(open_after)
        self._orders = None

    @staticmethod
    def _header_map(sheet, required_headers, workbook_name):
        headers = {
            str(cell.value or "").strip(): cell.column - 1
            for cell in sheet[1]
            if str(cell.value or "").strip()
        }
        missing = [header for header in required_headers if header not in headers]
        if missing:
            raise LabelPrintingError(
                f"{workbook_name}缺少必要列: {', '.join(missing)}"
            )
        return headers

    @classmethod
    def _read_rows(cls, path, required_headers, workbook_name):
        workbook = load_workbook(path, data_only=True, read_only=True)
        try:
            sheet = workbook.worksheets[0]
            headers = cls._header_map(sheet, required_headers, workbook_name)
            rows = []
            for values in sheet.iter_rows(min_row=2, values_only=True):
                rows.append({
                    header: "" if values[index] is None else str(values[index]).strip()
                    for header, index in headers.items()
                })
            return rows
        finally:
            workbook.close()

    def load_orders(self):
        source_rows = self._read_rows(
            self.source_path, RAW_REQUIRED_HEADERS, "原始一件代发表"
        )
        source_by_reference = {}
        for row in source_rows:
            reference = row["参考单号"]
            if not reference:
                continue
            if reference in source_by_reference:
                raise LabelPrintingError(f"原始一件代发表参考单号重复: {reference}")
            source_by_reference[reference] = row

        finished_rows = self._read_rows(
            self.finished_path, FINISHED_REQUIRED_HEADERS, "完整成品表"
        )
        orders = {}
        for row in finished_rows:
            reference = row["单号"]
            if not reference:
                continue
            if reference in orders:
                raise LabelPrintingError(f"完整成品表参考单号重复: {reference}")
            source = source_by_reference.get(reference)
            if source is None:
                raise LabelPrintingError(f"完整成品表参考单号未在原始表找到: {reference}")
            orders[reference] = PrintOrder(
                reference=reference,
                customer_id=source["客户编号"],
                shelf=source["货架"],
                sku=source["SKU"],
                quantity=source["数量"],
                sku_kind=classify_sku(source["SKU"], source["数量"]),
                recipient_name=row["收件姓名"],
                recipient_phone=row["收件人电话"],
                recipient_postal=row["收件邮编"],
                recipient_address=" ".join(
                    value for value in (row["收件地址"], row["详细地址"]) if value
                ),
            )
        self._orders = orders
        return orders

    @staticmethod
    def _matches_postal_and_name(text, order):
        normalized = normalize_text(text)
        postal = normalize_digits(order.recipient_postal)
        name = normalize_text(order.recipient_name)
        return bool(postal and name and postal in normalize_digits(text) and name in normalized)

    @staticmethod
    def _match_error(page_order, candidates):
        references = ", ".join(order.reference for order in candidates) or "无"
        return LabelPrintingError(
            f"第{page_order + 1}页无法唯一匹配，候选参考单号: {references}"
        )

    def match_page(self, text, page_order):
        orders = self._orders if self._orders is not None else self.load_orders()
        label_type = detect_label_type(text)
        values = list(orders.values())

        if label_type == "投函":
            candidates = [
                order for order in values if self._matches_postal_and_name(text, order)
            ]
        else:
            page_digits = normalize_digits(text)
            candidates = [
                order
                for order in values
                if (phone := normalize_digits(order.recipient_phone)) and phone in page_digits
            ]
            if len(candidates) > 1:
                candidates = [
                    order for order in candidates
                    if self._matches_postal_and_name(text, order)
                ]

        if len(candidates) != 1:
            raise self._match_error(page_order, candidates)
        return LabelPage(
            pdf_path=Path(),
            page_index=page_order,
            input_order=page_order,
            label_type=label_type,
            label_id="",
            order=candidates[0],
        )
