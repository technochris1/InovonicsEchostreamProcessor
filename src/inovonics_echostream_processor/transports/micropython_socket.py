from inovonics_echostream_processor.compat import is_micropython
from inovonics_echostream_processor.core import EchoStreamProcessorCore, ProcessBatch


class MicroPythonSocketProcessorConfig(object):
    def __init__(self, host, port, timeout_seconds=0.1):
        self.host = host
        self.port = port
        self.timeout_seconds = timeout_seconds


class MicroPythonSocketProcessor(object):
    def __init__(self, config, core=None, sock=None):
        if not is_micropython():
            raise RuntimeError("MicroPython socket transport can only run on MicroPython.")

        self.config = config
        self.core = core or EchoStreamProcessorCore()
        self._socket = sock or self._build_socket()

    def add_event_handler(self, handler):
        self.core.add_event_handler(handler)

    def poll_once(self):
        try:
            data = self._socket.recv(1024)
        except OSError:
            return ProcessBatch()

        if not data:
            return ProcessBatch()

        batch = self.core.feed(data)
        for command in batch.outbound_commands:
            self.send_command(command)
        return batch

    def send_command(self, command):
        self._socket.send(command)

    def close(self):
        self._socket.close()

    def _build_socket(self):
        socket_module = self._socket_module()
        sock = socket_module.socket()
        sock.settimeout(self.config.timeout_seconds)
        sock.connect((self.config.host, self.config.port))
        return sock

    def _socket_module(self):
        try:
            import usocket as socket_module
        except ImportError:
            import socket as socket_module
        return socket_module
