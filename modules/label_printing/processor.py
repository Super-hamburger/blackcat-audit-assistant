from dataclasses import dataclass
from datetime import datetime
import csv
import os
from pathlib import Path
import re
import subprocess
import sys
from uuid import uuid4

import fitz

from modules.file_paste.converter import (
    MARKER_MAX_LENGTH,
    report_progress,
    shelf_sort_key,
)


MARKER_PATTERN = re.compile(r"LP\[([^\[\]/]*)/([^\[\]/]*)\]")


class LabelPrintingError(Exception):
    """Raised when a label page cannot be processed."""


def parse_pdf_label_marker(text, page_number):
    raw_text = str(text or "")
    matches = MARKER_PATTERN.findall(raw_text)
    if len(matches) != raw_text.count("LP["):
        raise LabelPrintingError(f"第{page_number}页标记格式错误")
    unique = set()
    for shelf, customer_id in matches:
        shelf, customer_id = shelf.strip(), customer_id.strip()
        marker = f"LP[{shelf}/{customer_id}]"
        invalid_component = (
            not shelf
            or not customer_id
            or any(ch in f"{shelf}{customer_id}" for ch in "[]/")
            or not customer_id.isdigit()
        )
        if invalid_component or len(marker) > MARKER_MAX_LENGTH:
            raise LabelPrintingError(f"第{page_number}页标记格式错误")
        unique.add((shelf, customer_id))
    if len(unique) > 1:
        raise LabelPrintingError(f"第{page_number}页存在多个不同 LP 标记")
    return next(iter(unique), None)


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


def detect_label_type(text):
    normalized = str(text or "")
    return "投函" if "投函" in normalized or "TOUKAN" in normalized.upper() else "宅急便"


def extract_label_id(text):
    match = re.search(
        r"a(\d{4}(?:[\-－]?\d{4}){2})a", str(text or ""), re.IGNORECASE
    )
    if match:
        return normalize_digits(match.group(1))
    match = re.search(
        r"(?<!\d)(\d{4}(?:[\-－]?\d{4}){2})(?!\d)", str(text or "")
    )
    return normalize_digits(match.group(1)) if match else ""


def open_directory(path):
    target = str(path)
    if sys.platform == "win32":
        os.startfile(target)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", target])
    else:
        subprocess.Popen(["xdg-open", target])


def page_sort_key(page):
    return (*shelf_sort_key(page.order.shelf, page.input_order), page.input_order)


def build_output_groups(pages, scope, split_types):
    pages = [page for page in pages if page.order.sku_kind == "SKU×1"]
    if scope == "all":
        owners = [("全部客户", pages)]
    elif scope == "by_customer":
        grouped = {}
        for page in pages:
            grouped.setdefault(page.order.customer_id, []).append(page)
        owners = [(f"客户{customer_id}", owner_pages) for customer_id, owner_pages in sorted(
            grouped.items(), key=lambda item: shelf_sort_key(item[0], 0)
        )]
    else:
        raise LabelPrintingError(f"不支持的打印范围: {scope}")

    label_types = ("投函", "宅急便") if split_types else ("合并",)
    groups = []
    for owner, owner_pages in owners:
        for label_type in label_types:
            selected = (
                owner_pages if label_type == "合并"
                else [page for page in owner_pages if page.label_type == label_type]
            )
            if selected:
                groups.append((
                    f"{owner}_{label_type}_货架排序.pdf",
                    sorted(selected, key=page_sort_key),
                ))
    return groups


def _task_output_dir(output_dir):
    task_dir = Path(output_dir) / f"面单打印_{datetime.now():%Y%m%d_%H%M%S}_{uuid4().hex[:6]}"
    task_dir.mkdir(parents=True, exist_ok=False)
    return task_dir


def _write_exception_report(task_dir, rows):
    report_path = task_dir / "异常报告.csv"
    with report_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=("页码", "原因", "面单号"))
        writer.writeheader()
        writer.writerows(rows)
    return report_path


def _remove_created_files(paths):
    for path in paths:
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            continue


class PdfOnlyLabelPrintProcessor:
    def __init__(
        self, pdf_paths, output_dir, scope="all", split_types=False, open_after=True,
    ):
        self.pdf_paths = [Path(path) for path in pdf_paths]
        self.output_dir = Path(output_dir)
        self.scope = scope
        self.split_types = bool(split_types)
        self.open_after = bool(open_after)

    @staticmethod
    def _problem(pdf_path, page_index, reason, label_id=""):
        return {
            "页码": page_index + 1 if pdf_path else "",
            "原因": reason,
            "面单号": label_id,
        }

    def _read_and_validate_pages(self, documents, progress_callback):
        pages = []
        problems = []
        label_pages = {}
        excluded_pages = 0
        total_pages = sum(document.page_count for document in documents.values())
        input_order = 0

        for pdf_path, document in documents.items():
            for page_index, pdf_page in enumerate(document):
                text = pdf_page.get_text()
                try:
                    marker = parse_pdf_label_marker(text, input_order + 1)
                except LabelPrintingError as error:
                    problems.append(self._problem(pdf_path, page_index, str(error)))
                else:
                    if marker is None:
                        excluded_pages += 1
                    else:
                        shelf, customer_id = marker
                        label_id = extract_label_id(text)
                        page = LabelPage(
                            pdf_path=pdf_path,
                            page_index=page_index,
                            input_order=input_order,
                            label_type=detect_label_type(text),
                            label_id=label_id,
                            order=PrintOrder(
                                reference="",
                                customer_id=customer_id,
                                shelf=shelf,
                                sku="",
                                quantity="",
                                sku_kind="SKU×1",
                                recipient_name="",
                                recipient_phone="",
                                recipient_postal="",
                                recipient_address="",
                            ),
                        )
                        pages.append(page)
                        if label_id:
                            duplicate = label_pages.get(label_id)
                            if duplicate is not None:
                                problems.append(self._problem(
                                    pdf_path,
                                    page_index,
                                    f"重复面单: {label_id}",
                                    label_id,
                                ))
                            else:
                                label_pages[label_id] = page
                input_order += 1
                report_progress(
                    progress_callback,
                    "matching",
                    f"正在读取 PDF 标记（{input_order}/{total_pages}）",
                    input_order,
                    total_pages,
                )
        return pages, problems, total_pages, excluded_pages

    def _open_documents(self):
        documents = {}
        for pdf_path in self.pdf_paths:
            if pdf_path in documents:
                continue
            try:
                documents[pdf_path] = fitz.open(pdf_path)
            except Exception as error:
                for document in documents.values():
                    document.close()
                raise LabelPrintingError(f"无法打开 PDF: {pdf_path.name}") from error
        return documents

    def run(self, progress_callback=None):
        task_dir = _task_output_dir(self.output_dir)
        documents = {}
        created_paths = []
        try:
            report_progress(
                progress_callback, "opening", "正在读取面单 PDF...", indeterminate=True
            )
            try:
                documents = self._open_documents()
            except LabelPrintingError as error:
                _write_exception_report(task_dir, [{
                    "页码": "",
                    "原因": str(error),
                    "面单号": "",
                }])
                raise

            pages, problems, total_pages, excluded_pages = self._read_and_validate_pages(
                documents, progress_callback
            )
            if problems:
                _write_exception_report(task_dir, problems)
                raise LabelPrintingError(problems[0]["原因"])

            groups = build_output_groups(pages, self.scope, self.split_types)
            report_progress(
                progress_callback, "writing", "正在按货架生成打印文件...", 0, len(groups)
            )
            for group_index, (name, group_pages) in enumerate(groups, start=1):
                output_path = task_dir / name
                output_document = fitz.open()
                try:
                    for page in group_pages:
                        output_document.insert_pdf(
                            documents[page.pdf_path],
                            from_page=page.page_index,
                            to_page=page.page_index,
                        )
                    created_paths.append(output_path)
                    output_document.save(output_path)
                finally:
                    output_document.close()
                report_progress(
                    progress_callback,
                    "writing",
                    f"正在生成打印文件（{group_index}/{len(groups)}）",
                    group_index,
                    len(groups),
                )

            customer_page_counts = {}
            type_counts = {"投函": 0, "宅急便": 0}
            for page in pages:
                customer_id = page.order.customer_id
                customer_page_counts[customer_id] = (
                    customer_page_counts.get(customer_id, 0) + 1
                )
                type_counts[page.label_type] += 1

            if self.open_after:
                try:
                    open_directory(task_dir)
                except OSError:
                    pass

            report_progress(progress_callback, "completed", "面单打印文件生成完成", 1, 1)
            return {
                "output_dir": str(task_dir),
                "output_paths": [str(path) for path in created_paths],
                "total_pages": total_pages,
                "matched_pages": len(pages),
                "printed_pages": sum(len(group_pages) for _, group_pages in groups),
                "customer_count": len(customer_page_counts),
                "type_counts": type_counts,
                "customer_page_counts": customer_page_counts,
                "excluded_pages": excluded_pages,
            }
        except Exception:
            _remove_created_files(created_paths)
            raise
        finally:
            for document in documents.values():
                document.close()
