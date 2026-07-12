class TaskCancelled(Exception):
    pass

class CancellationToken:
    def __init__(self):
        self._cancelled = False
    def cancel(self):
        self._cancelled = True
    def throw_if_cancelled(self):
        if self._cancelled:
            raise TaskCancelled()
