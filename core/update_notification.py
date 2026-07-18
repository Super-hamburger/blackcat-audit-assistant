from PySide6.QtCore import QObject, Signal, Slot


class UpdateNotificationState:
    def __init__(self):
        self.notified_versions = set()

    def apply(self, result):
        latest_version = str(result.get("latest_version", "")).strip()
        if result.get("has_update") and latest_version:
            should_notify = latest_version not in self.notified_versions
            self.notified_versions.add(latest_version)
            return {
                "status": "update_available",
                "should_notify": should_notify,
            }
        if result.get("remote_error"):
            return {
                "status": "check_failed",
                "should_notify": False,
            }
        return {
            "status": "up_to_date",
            "should_notify": False,
        }


class UpdateCheckWorker(QObject):
    check_finished = Signal(dict)

    def __init__(self, update_manager):
        super().__init__()
        self.update_manager = update_manager

    @Slot()
    def run(self):
        try:
            result = self.update_manager.check_update()
        except Exception as error:
            result = {
                "has_update": False,
                "current_version": self.update_manager.current_version,
                "message": "远程更新源读取失败。",
                "remote_error": str(error),
            }
        self.check_finished.emit(result)


class UpdateInstallWorker(QObject):
    progress = Signal(dict)
    install_finished = Signal(dict)

    def __init__(self, installer, update_info):
        super().__init__()
        self.installer = installer
        self.update_info = dict(update_info)

    @Slot()
    def run(self):
        try:
            result = self.installer.prepare_update(self.update_info, self.progress.emit)
        except Exception as error:
            result = {"ok": False, "message": f"准备更新失败：{error}"}
        self.install_finished.emit(result)
