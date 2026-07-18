import unittest

from core.update_notification import UpdateInstallWorker


class RecordingInstaller:
    def prepare_update(self, update_info, progress_callback=None):
        progress_callback({
            "stage": "downloading",
            "message": "正在下载更新包...",
            "downloaded_bytes": 512,
            "total_bytes": 1024,
        })
        return {"ok": True, "message": "更新包已准备完成。"}


class UpdateInstallWorkerTests(unittest.TestCase):
    def test_forwards_progress_before_final_result(self):
        worker = UpdateInstallWorker(RecordingInstaller(), {"latest_version": "5.0.1"})
        events = []
        worker.progress.connect(lambda event: events.append(("progress", event)))
        worker.install_finished.connect(lambda result: events.append(("finished", result)))

        worker.run()

        self.assertEqual([kind for kind, _ in events], ["progress", "finished"])
        self.assertEqual(events[0][1]["stage"], "downloading")
        self.assertTrue(events[1][1]["ok"])


if __name__ == "__main__":
    unittest.main()
