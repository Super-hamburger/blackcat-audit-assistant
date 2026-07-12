import unittest

from core.config_manager import DEFAULT_SETTINGS
from core.update_manager import UpdateManager
from core.update_notification import UpdateNotificationState


class FailingRemoteUpdateManager(UpdateManager):
    def load_local_manifest(self):
        return {
            "latest_version": "4.3.1",
            "manifest_url": "https://updates.example.test/update_manifest.json",
        }

    def load_remote_manifest(self, url):
        raise OSError("offline")


class UpdateNotificationStateTest(unittest.TestCase):
    def test_new_version_notifies_only_once_per_session(self):
        state = UpdateNotificationState()
        update_result = {
            "has_update": True,
            "current_version": "4.3.1",
            "latest_version": "4.4.0",
        }

        first = state.apply(update_result)
        second = state.apply(update_result)

        self.assertEqual(first["status"], "update_available")
        self.assertTrue(first["should_notify"])
        self.assertFalse(second["should_notify"])

    def test_network_error_does_not_request_notification(self):
        state = UpdateNotificationState()

        outcome = state.apply({"has_update": False, "remote_error": "offline"})

        self.assertEqual(outcome["status"], "check_failed")
        self.assertFalse(outcome["should_notify"])

    def test_default_settings_enable_automatic_update_checks(self):
        self.assertTrue(DEFAULT_SETTINGS["auto_update_check"])

    def test_update_manager_returns_remote_error_for_background_status(self):
        result = FailingRemoteUpdateManager("4.3.1").check_update()

        self.assertEqual(result["remote_error"], "offline")


if __name__ == "__main__":
    unittest.main()
