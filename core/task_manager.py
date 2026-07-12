from PySide6.QtCore import QObject, QThread, Signal
from core.modules.module_registry import ModuleRegistry
from core.task_state import CancellationToken

class Worker(QObject):
    progress = Signal(float, str)
    log = Signal(str, str)
    stats = Signal(dict)
    done = Signal(dict)
    error = Signal(str)

    def __init__(self, config, cancel_token):
        super().__init__()
        self.config = config
        self.cancel_token = cancel_token

    def run(self):
        try:
            module_result = ModuleRegistry().run("label_compress", {
                "pdf_path": self.config["pdf"],
                "output_dir": self.config["output"],
                "batch_size": self.config["batch_size"],
                "auto_zip": self.config["auto_zip"],
                "open_output": self.config["open_output"],
                "cancel_token": self.cancel_token,
                "on_progress": lambda percent, text: self.progress.emit(percent, text),
                "on_log": lambda level, message: self.log.emit(level, message),
                "on_stats": lambda data: self.stats.emit(data),
            })
            if not module_result.data:
                raise RuntimeError(module_result.message)
            self.done.emit(module_result.data)
        except Exception as e:
            self.error.emit(str(e))

class TaskManager(QObject):
    progress = Signal(float, str)
    log = Signal(str, str)
    stats = Signal(dict)
    done = Signal(dict)
    error = Signal(str)

    def __init__(self):
        super().__init__()
        self.thread = None
        self.worker = None
        self.cancel_token = None
        self.running = False

    def start(self, config):
        if self.running:
            return False
        self.running = True
        self.cancel_token = CancellationToken()
        self.thread = QThread()
        self.worker = Worker(config, self.cancel_token)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.progress)
        self.worker.log.connect(self.log)
        self.worker.stats.connect(self.stats)
        self.worker.done.connect(self._done)
        self.worker.error.connect(self._error)
        self.worker.done.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()
        return True

    def cancel(self):
        if self.cancel_token:
            self.cancel_token.cancel()

    def _done(self, result):
        self.running = False
        self.done.emit(result)

    def _error(self, message):
        self.running = False
        self.error.emit(message)
