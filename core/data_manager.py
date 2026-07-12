import json
import time
from pathlib import Path
from core.path_manager import PathManager


class DataManager:
    def __init__(self, data_dir):
        self.data_dir = PathManager.data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.records_path = self.data_dir / "records.json"
        self.templates_path = self.data_dir / "templates.json"

    def _read_json(self, path, default):
        if not path.exists():
            self._write_json(path, default)
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def _write_json(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_records(self):
        return self._read_json(self.records_path, [])

    def add_record(self, record):
        records = self.get_records()
        item = {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "type": record.get("type", ""),
            "source": record.get("source", ""),
            "output": record.get("output", ""),
            "total": int(record.get("total", 0) or 0),
            "success": int(record.get("success", 0) or 0),
            "failed": int(record.get("failed", 0) or 0),
            "elapsed": float(record.get("elapsed", 0) or 0),
            "note": record.get("note", ""),
        }
        records.insert(0, item)
        records = records[:500]
        self._write_json(self.records_path, records)
        return item

    def clear_records(self):
        self._write_json(self.records_path, [])

    def get_templates(self):
        return self._read_json(self.templates_path, [])

    def add_template(self, template):
        templates = self.get_templates()
        item = {
            "name": template.get("name", "未命名模板"),
            "type": template.get("type", "通用"),
            "output_dir": template.get("output_dir", ""),
            "batch_size": int(template.get("batch_size", 90) or 90),
            "auto_zip": bool(template.get("auto_zip", True)),
            "open_output": bool(template.get("open_output", True)),
            "sound_enabled": bool(template.get("sound_enabled", True)),
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        templates.insert(0, item)
        self._write_json(self.templates_path, templates)
        return item

    def add_file_template(self, name, template_type, file_path):
        templates = self.get_templates()
        item = {
            "name": name,
            "type": template_type,
            "file_path": str(file_path),
            "output_dir": "",
            "batch_size": 90,
            "auto_zip": True,
            "open_output": True,
            "sound_enabled": True,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        templates.insert(0, item)
        self._write_json(self.templates_path, templates)
        return item

    def export_templates(self, output_path):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_json(output_path, self.get_templates())

    def import_templates_json(self, source_path):
        source_path = Path(source_path)
        imported = self._read_json(source_path, [])
        if not isinstance(imported, list):
            raise ValueError("Invalid template file.")
        templates = imported + self.get_templates()
        self._write_json(self.templates_path, templates)
        return len(imported)

    def delete_template(self, index):
        templates = self.get_templates()
        if 0 <= index < len(templates):
            templates.pop(index)
            self._write_json(self.templates_path, templates)

    def get_stats(self):
        records = self.get_records()
        today = time.strftime("%Y-%m-%d")
        month = time.strftime("%Y-%m")
        today_records = [r for r in records if str(r.get("time", "")).startswith(today)]
        month_records = [r for r in records if str(r.get("time", "")).startswith(month)]

        def summarize(items):
            total_tasks = len(items)
            total_units = sum(int(r.get("total", 0) or 0) for r in items)
            success = sum(int(r.get("success", 0) or 0) for r in items)
            failed = sum(int(r.get("failed", 0) or 0) for r in items)
            elapsed = sum(float(r.get("elapsed", 0) or 0) for r in items)
            speed = total_units / elapsed if elapsed > 0 else 0
            return {
                "tasks": total_tasks,
                "total": total_units,
                "success": success,
                "failed": failed,
                "elapsed": elapsed,
                "speed": speed,
            }

        all_stats = summarize(records)
        today_stats = summarize(today_records)
        month_stats = summarize(month_records)

        fastest = 0
        for r in records:
            elapsed = float(r.get("elapsed", 0) or 0)
            total = int(r.get("total", 0) or 0)
            if elapsed > 0:
                fastest = max(fastest, total / elapsed)

        return {
            "all": all_stats,
            "today": today_stats,
            "month": month_stats,
            "fastest": fastest,
            "records_count": len(records),
            "templates_count": len(self.get_templates()),
        }
