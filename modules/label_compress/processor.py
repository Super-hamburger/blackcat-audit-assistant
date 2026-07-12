from pathlib import Path
import csv
import os
import time

from modules.label_compress.pdf_engine import PdfEngine
from modules.label_compress.recognizer import TrackingRecognizer
from modules.label_compress.zip_engine import ZipEngine
from core.task_state import TaskCancelled
from core.file_safe import ensure_writable_dir


class DuplicateLabelError(Exception):
    def __init__(self, number, first_location, current_location):
        super().__init__(f"重复单号：{number}")
        self.number = number
        self.first_location = first_location
        self.current_location = current_location


class RecognitionConfidenceError(Exception):
    def __init__(self, message, result, location):
        super().__init__(message)
        self.result = result
        self.location = location


class LabelProcessor:
    def __init__(self, pdf_path, output_dir, batch_size=90, auto_zip=True, open_output=True, cancel_token=None, min_run_seconds=2.0):
        if isinstance(pdf_path, (list, tuple)):
            self.pdf_paths = [Path(item) for item in pdf_path]
        else:
            text = str(pdf_path)
            self.pdf_paths = [Path(item) for item in text.split("|") if item]

        self.base_output_dir = ensure_writable_dir(output_dir, 'output')
        self.batch_size = int(batch_size)
        self.auto_zip = bool(auto_zip)
        self.open_output = bool(open_output)
        self.cancel_token = cancel_token
        self.min_run_seconds = float(min_run_seconds)
        self.recognizer = TrackingRecognizer()
        self.zip_engine = ZipEngine()

    def check_cancelled(self):
        if self.cancel_token:
            self.cancel_token.throw_if_cancelled()

    def create_run_dir(self):
        run_dir = self.base_output_dir / time.strftime("BlackCat_%Y%m%d_%H%M%S")
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def get_total_pages(self):
        total = 0
        for pdf_path in self.pdf_paths:
            total += PdfEngine(pdf_path).get_page_count()
        return total

    def run(self, on_progress=None, on_log=None, on_stats=None):
        def log(level, message):
            if on_log:
                on_log(level, message)

        def progress(percent, text):
            if on_progress:
                on_progress(percent, text)

        def stats(data):
            if on_stats:
                on_stats(data)

        start_time = time.time()
        run_dir = self.create_run_dir()

        total_pages = 0
        processed_pages = 0
        saved_count = 0
        failed = []
        seen = {}
        duplicate_info = None
        recognition_rows = []

        try:
            log("INFO", "任务开始")
            log("INFO", f"PDF文件数: {len(self.pdf_paths)}")
            for pdf in self.pdf_paths:
                log("INFO", f"输入PDF: {pdf}")
            log("INFO", f"输出目录: {run_dir}")

            total_pages = self.get_total_pages()
            log("INFO", f"总页数: {total_pages}")

            for pdf_index, pdf_path in enumerate(self.pdf_paths, start=1):
                self.check_cancelled()
                pdf_engine = PdfEngine(pdf_path)
                page_count = pdf_engine.get_page_count()
                log("INFO", f"正在处理第 {pdf_index} 个PDF：{pdf_path.name}，页数：{page_count}")

                for page_index in range(page_count):
                    self.check_cancelled()

                    processed_pages += 1
                    elapsed = max(time.time() - start_time, 0.001)
                    speed = processed_pages / elapsed
                    percent = processed_pages * 100 / max(total_pages, 1)

                    progress(percent, f"正在处理 {processed_pages} / {total_pages} 页")
                    stats({
                        "total": total_pages,
                        "current": processed_pages,
                        "success": saved_count,
                        "failed": len(failed),
                        "speed": speed,
                        "elapsed": elapsed,
                    })

                    current_location = f"{pdf_path.name} 第 {page_index + 1} 页"
                    text = pdf_engine.extract_text(page_index)
                    page_data = pdf_engine.extract_words(page_index)
                    recognition = self.recognizer.recognize(
                        text,
                        words=page_data.get("words", []),
                        page_rect=page_data.get("page_rect", {}),
                    )
                    recognition_rows.append(self.recognition_row(current_location, recognition))

                    if not recognition.ok:
                        message = (
                            f"{current_location}：单号识别置信度不足，任务已停止。\n"
                            f"识别方式：{recognition.method}\n"
                            f"置信度：{recognition.confidence}\n"
                            f"原因：{recognition.reason}\n"
                            "请检查待确认页面后再继续处理。"
                        )
                        failed.append(message)
                        log("ERROR", message)
                        self.save_unrecognized_page(pdf_engine, page_index, run_dir, pdf_path.name)
                        raise RecognitionConfidenceError(message, recognition, current_location)

                    number = recognition.number

                    if number in seen:
                        first_location = seen[number]
                        duplicate_info = {
                            "number": number,
                            "first_location": first_location,
                            "current_location": current_location,
                        }
                        message = (
                            f"发现重复单号：{number}\n"
                            f"首次出现：{first_location}\n"
                            f"重复出现：{current_location}\n"
                            "任务已停止，未继续生成后续 ZIP。"
                        )
                        failed.append(message)
                        log("ERROR", message)
                        raise DuplicateLabelError(number, first_location, current_location)

                    seen[number] = current_location

                    folder = run_dir / f"batch_{((processed_pages - 1) // self.batch_size) + 1:03d}"
                    folder.mkdir(parents=True, exist_ok=True)
                    output_pdf = folder / f"{number}.pdf"
                    pdf_engine.save_single_page(page_index, output_pdf)
                    saved_count += 1
                    log("SUCCESS", f"[{processed_pages}/{total_pages}] {output_pdf.name} ({recognition.method}, confidence {recognition.confidence})")

            if failed:
                report = run_dir / "error_report.txt"
                report.write_text("\n".join(failed), encoding="utf-8")
                self.write_recognition_report(run_dir, recognition_rows)
                log("ERROR", f"任务停止，错误报告: {report}")
                return self.result(False, False, total_pages, saved_count, failed, run_dir, start_time, duplicate_info, recognition_rows)

            if self.auto_zip:
                zip_dir = run_dir / "zip"
                zip_dir.mkdir(parents=True, exist_ok=True)
                for folder in sorted([p for p in run_dir.glob("batch_*") if p.is_dir()]):
                    self.check_cancelled()
                    zip_path = zip_dir / f"{folder.name}.zip"
                    self.zip_engine.zip_folder(folder, zip_path)
                    log("INFO", f"已生成ZIP: {zip_path.name}")

            elapsed = time.time() - start_time
            if elapsed < self.min_run_seconds:
                time.sleep(self.min_run_seconds - elapsed)

            elapsed = time.time() - start_time
            self.write_report(run_dir, total_pages, saved_count, failed, elapsed, duplicate_info)
            self.write_recognition_report(run_dir, recognition_rows)

            if self.open_output:
                os.startfile(run_dir)

            progress(100, "完成")
            stats({
                "total": total_pages,
                "current": total_pages,
                "success": saved_count,
                "failed": len(failed),
                "speed": total_pages / max(elapsed, 0.001),
                "elapsed": elapsed,
            })
            log("INFO", f"任务完成。耗时: {elapsed:.2f} 秒")

            return self.result(True, False, total_pages, saved_count, failed, run_dir, start_time, duplicate_info, recognition_rows)

        except DuplicateLabelError:
            elapsed = time.time() - start_time
            self.write_report(run_dir, total_pages, saved_count, failed, elapsed, duplicate_info)
            self.write_recognition_report(run_dir, recognition_rows)
            return self.result(False, False, total_pages, saved_count, failed, run_dir, start_time, duplicate_info, recognition_rows)

        except RecognitionConfidenceError:
            elapsed = time.time() - start_time
            self.write_report(run_dir, total_pages, saved_count, failed, elapsed, duplicate_info)
            self.write_recognition_report(run_dir, recognition_rows)
            return self.result(False, False, total_pages, saved_count, failed, run_dir, start_time, duplicate_info, recognition_rows)

        except TaskCancelled:
            log("WARNING", "任务已取消。")
            self.write_recognition_report(run_dir, recognition_rows)
            return self.result(False, True, total_pages, saved_count, failed, run_dir, start_time, duplicate_info, recognition_rows)

    def result(self, success, cancelled, page_count, saved_count, failed, run_dir, start_time, duplicate_info=None, recognition_rows=None):
        return {
            "success": success,
            "cancelled": cancelled,
            "page_count": page_count,
            "saved_count": saved_count,
            "failed": failed,
            "output_dir": str(run_dir),
            "elapsed": time.time() - start_time,
            "duplicate_info": duplicate_info,
            "recognition_report": str(run_dir / "recognition_report.csv"),
            "recognition_rows": recognition_rows or [],
        }

    def recognition_row(self, location, recognition):
        candidates = recognition.candidates[:5]
        return {
            "location": location,
            "number": recognition.number or "",
            "confidence": recognition.confidence,
            "method": recognition.method,
            "reason": recognition.reason,
            "candidate_count": len(recognition.candidates),
            "top_candidates": " | ".join([f"{item.number}:{item.score}:{item.method}" for item in candidates]),
        }

    def save_unrecognized_page(self, pdf_engine, page_index, run_dir, source_name):
        folder = run_dir / "unrecognized_pages"
        folder.mkdir(parents=True, exist_ok=True)
        safe_source = Path(source_name).stem.replace(" ", "_")
        output_path = folder / f"{safe_source}_page_{page_index + 1:04d}.pdf"
        pdf_engine.save_single_page(page_index, output_path)
        return output_path

    def write_recognition_report(self, run_dir, rows):
        report = run_dir / "recognition_report.csv"
        fieldnames = ["location", "number", "confidence", "method", "reason", "candidate_count", "top_candidates"]
        with report.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    def write_report(self, run_dir, page_count, saved_count, failed, elapsed, duplicate_info=None):
        report = run_dir / "task_report.txt"
        lines = [
            "黑猫审单助手 - 任务报告",
            "======================",
            "状态: 完成" if not failed else "状态: 发现错误",
            f"PDF文件数: {len(self.pdf_paths)}",
            f"总页数: {page_count}",
            f"成功: {saved_count}",
            f"失败: {len(failed)}",
            f"耗时: {elapsed:.2f} 秒",
            f"平均速度: {page_count / max(elapsed, 0.001):.2f} 页/秒",
        ]
        if duplicate_info:
            lines.extend([
                "",
                "重复单号重点提示:",
                f"重复单号: {duplicate_info.get('number')}",
                f"首次出现: {duplicate_info.get('first_location')}",
                f"重复出现: {duplicate_info.get('current_location')}",
            ])
        lines.extend(["", "失败详情:"])
        lines.extend(failed if failed else ["无"])
        report.write_text("\n".join(lines), encoding="utf-8")
