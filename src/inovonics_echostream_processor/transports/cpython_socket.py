import logging
import socket
import threading

try:
    from queue import Empty, Queue
except ImportError:  # pragma: no cover
    from Queue import Empty, Queue

from inovonics_echostream_processor.core import EchoStreamProcessorCore


class SocketProcessorConfig(object):
    def __init__(
        self,
        host,
        port,
        reconnect_initial_delay_seconds=1.0,
        reconnect_max_delay_seconds=60.0,
        socket_timeout_seconds=5.0,
        queue_timeout_seconds=1.0,
    ):
        self.host = host
        self.port = port
        self.reconnect_initial_delay_seconds = reconnect_initial_delay_seconds
        self.reconnect_max_delay_seconds = reconnect_max_delay_seconds
        self.socket_timeout_seconds = socket_timeout_seconds
        self.queue_timeout_seconds = queue_timeout_seconds


class ProcessorMetrics(object):
    def __init__(self):
        self.total_frames = 0
        self.processed_events = 0
        self.failed_frames = 0
        self.reconnects = 0


class SocketProcessorService(object):
    def __init__(self, config, core=None, logger=None):
        self.config = config
        self._logger = logger or logging.getLogger(self.__class__.__name__)
        self.core = core or EchoStreamProcessorCore(logger=self._logger.getChild("core"))

        self._socket = None
        self._socket_connected = False
        self._running = False
        self._stop_event = threading.Event()
        self._send_lock = threading.Lock()
        self._connect_lock = threading.Lock()
        self._connect_thread = None
        self._receive_thread = None
        self._processor_thread = None
        self._data_queue = Queue()
        self.metrics = ProcessorMetrics()

    @property
    def is_running(self):
        return self._running

    @property
    def is_connected(self):
        return self._socket_connected

    def add_event_handler(self, handler):
        self.core.add_event_handler(handler)

    def start(self):
        if self._running:
            return

        self._running = True
        self._stop_event.clear()
        self._processor_thread = threading.Thread(
            target=self._process_data_queue,
            daemon=True,
            name="echostream-cpython-processor",
        )
        self._processor_thread.start()
        self._schedule_connect()

    def stop(self):
        if not self._running:
            return

        self._running = False
        self._stop_event.set()
        self._close_socket()

        if self._processor_thread is not None:
            self._processor_thread.join(timeout=3)
        if self._receive_thread is not None:
            self._receive_thread.join(timeout=3)
        if self._connect_thread is not None:
            self._connect_thread.join(timeout=3)

    def send_command(self, command):
        with self._send_lock:
            if not self._socket_connected or self._socket is None:
                raise RuntimeError("EchoStream socket is not connected")
            self._logger.debug("Sending outbound command: %s", command.hex().upper())
            self._socket.sendall(command)

    def _schedule_connect(self):
        with self._connect_lock:
            if self._connect_thread is not None and self._connect_thread.is_alive():
                return

            self._connect_thread = threading.Thread(
                target=self._connect_loop,
                daemon=True,
                name="echostream-cpython-connect",
            )
            self._connect_thread.start()

    def _connect_loop(self):
        backoff = self.config.reconnect_initial_delay_seconds

        try:
            while self._running and not self._socket_connected:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(self.config.socket_timeout_seconds)
                    sock.connect((self.config.host, self.config.port))
                    self._socket = sock
                    self._socket_connected = True
                    self._logger.info(
                        "Connected to EchoStream source %s:%s",
                        self.config.host,
                        self.config.port,
                    )
                    self._receive_thread = threading.Thread(
                        target=self._receive_loop,
                        daemon=True,
                        name="echostream-cpython-receive",
                    )
                    self._receive_thread.start()
                    return
                except OSError as exc:
                    self.metrics.reconnects += 1
                    self._logger.warning(
                        "EchoStream connection failed: %s. Retrying in %.1f seconds.",
                        exc,
                        backoff,
                    )
                    if self._stop_event.wait(backoff):
                        return
                    backoff = min(backoff * 2, self.config.reconnect_max_delay_seconds)
        finally:
            with self._connect_lock:
                if self._connect_thread is threading.current_thread():
                    self._connect_thread = None

    def _receive_loop(self):
        try:
            while self._running and self._socket_connected and self._socket is not None:
                try:
                    data = self._socket.recv(1024)
                except socket.timeout:
                    continue

                if not data:
                    self._logger.warning("EchoStream socket closed by peer.")
                    break

                self._logger.debug("Received %d byte(s) from EchoStream socket.", len(data))
                self._data_queue.put(data)
        except OSError as exc:
            if self._running:
                self._logger.warning("EchoStream receive error: %s", exc)
        finally:
            self._close_socket()
            if self._running:
                self._schedule_connect()

    def _process_data_queue(self):
        while not self._stop_event.is_set():
            try:
                data = self._data_queue.get(timeout=self.config.queue_timeout_seconds)
            except Empty:
                continue

            try:
                batch = self.core.feed(data)
                self.metrics.total_frames += len(batch.frames)
                self.metrics.processed_events += len(batch.events)
                self._logger.debug(
                    "Processed chunk into %d frame(s), %d event(s), %d command(s).",
                    len(batch.frames),
                    len(batch.events),
                    len(batch.outbound_commands),
                )
                for command in batch.outbound_commands:
                    self.send_command(command)
            except Exception:
                self.metrics.failed_frames += 1
                self._logger.exception("Failed to process EchoStream data chunk.")
            finally:
                self._data_queue.task_done()

    def _close_socket(self):
        sock = self._socket
        self._socket = None
        self._socket_connected = False

        if sock is None:
            return

        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

        try:
            sock.close()
        except OSError:
            pass
