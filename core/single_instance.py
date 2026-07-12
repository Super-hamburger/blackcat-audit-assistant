class CallbackSignal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self):
        for callback in list(self._callbacks):
            callback()


def _default_socket_factory():
    from PySide6.QtNetwork import QLocalSocket

    return QLocalSocket()


def _default_server_factory():
    from PySide6.QtNetwork import QLocalServer

    return QLocalServer()


def _default_remove_server(server_name):
    from PySide6.QtNetwork import QLocalServer

    return QLocalServer.removeServer(server_name)


class SingleInstanceController:

    ACTIVATE_MESSAGE = b"activate\n"

    def __init__(
        self,
        server_name,
        timeout_ms=250,
        socket_factory=_default_socket_factory,
        server_factory=_default_server_factory,
        remove_server=_default_remove_server,
    ):
        self.server_name = server_name
        self.timeout_ms = timeout_ms
        self.activation_requested = CallbackSignal()
        self._socket_factory = socket_factory
        self._server_factory = server_factory
        self._remove_server = remove_server
        self._server = None
        self._clients = []
        self._is_primary = not self._notify_existing_instance()
        if self._is_primary:
            self._start_listener()

    @property
    def is_primary(self):
        return self._is_primary

    @property
    def is_duplicate(self):
        return not self._is_primary

    def _notify_existing_instance(self):
        socket = self._socket_factory()
        socket.connectToServer(self.server_name)
        if not socket.waitForConnected(self.timeout_ms):
            return False

        socket.write(self.ACTIVATE_MESSAGE)
        socket.flush()
        socket.waitForBytesWritten(self.timeout_ms)
        socket.disconnectFromServer()
        return True

    def _start_listener(self):
        self._remove_server(self.server_name)
        self._server = self._server_factory()
        if not self._server.listen(self.server_name):
            raise RuntimeError(f"Cannot start single-instance listener: {self.server_name}")
        self._server.newConnection.connect(self._handle_new_connection)

    def _handle_new_connection(self):
        while self._server and self._server.hasPendingConnections():
            client = self._server.nextPendingConnection()
            self._clients.append(client)
            client.readyRead.connect(lambda client=client: self._read_client(client))
            client.disconnected.connect(lambda client=client: self._release_client(client))
            if client.bytesAvailable():
                self._read_client(client)

    def _read_client(self, client):
        message = bytes(client.readAll()).strip()
        if message == self.ACTIVATE_MESSAGE.strip():
            self.activation_requested.emit()
        client.disconnectFromServer()

    def _release_client(self, client):
        if client in self._clients:
            self._clients.remove(client)
        client.deleteLater()
