import unittest

from core.single_instance import SingleInstanceController


class FakeSignal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)


class FakeSocket:
    def __init__(self, can_connect):
        self.can_connect = can_connect
        self.server_name = None
        self.written = b""
        self.disconnected = False

    def connectToServer(self, server_name):
        self.server_name = server_name

    def waitForConnected(self, timeout_ms):
        return self.can_connect

    def write(self, data):
        self.written += bytes(data)

    def flush(self):
        return True

    def waitForBytesWritten(self, timeout_ms):
        return True

    def disconnectFromServer(self):
        self.disconnected = True


class FakeServer:
    def __init__(self, listen_result=True):
        self.listen_result = listen_result
        self.listened_name = None
        self.newConnection = FakeSignal()

    def listen(self, server_name):
        self.listened_name = server_name
        return self.listen_result


class SingleInstanceControllerTest(unittest.TestCase):
    def test_duplicate_instance_sends_activation_and_does_not_listen(self):
        socket = FakeSocket(can_connect=True)
        server = FakeServer()
        removed = []

        controller = SingleInstanceController(
            "blackcat-test",
            socket_factory=lambda: socket,
            server_factory=lambda: server,
            remove_server=removed.append,
        )

        self.assertFalse(controller.is_primary)
        self.assertEqual(socket.server_name, "blackcat-test")
        self.assertEqual(socket.written, b"activate\n")
        self.assertTrue(socket.disconnected)
        self.assertIsNone(server.listened_name)
        self.assertEqual(removed, [])

    def test_primary_instance_removes_stale_server_and_starts_listener(self):
        socket = FakeSocket(can_connect=False)
        server = FakeServer()
        removed = []

        controller = SingleInstanceController(
            "blackcat-test",
            socket_factory=lambda: socket,
            server_factory=lambda: server,
            remove_server=removed.append,
        )

        self.assertTrue(controller.is_primary)
        self.assertEqual(removed, ["blackcat-test"])
        self.assertEqual(server.listened_name, "blackcat-test")
        self.assertEqual(len(server.newConnection.callbacks), 1)


if __name__ == "__main__":
    unittest.main()
