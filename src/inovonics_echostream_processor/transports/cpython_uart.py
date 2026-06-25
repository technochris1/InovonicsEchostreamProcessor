import logging
import threading

try:
    from queue import Empty, Queue
except ImportError:  # pragma: no cover
    from Queue import Empty, Queue

from inovonics_echostream_processor.core import EchoStreamProcessorCore


class CpythonUartProcessorConfig(object):
    def __init__(
        self,
        port,
        baudrate,
        reconnect_initial_delay_seconds=1.0,
        reconnect_max_delay_seconds=60.0,
        read_size=1024,
        timeout_seconds=1.0,
        write_timeout_seconds=1.0,
        queue_timeout_seconds=1.0,
        **serial_kwargs
    ):
        self.port = port
        self.baudrate = baudrate
        self.reconnect_initial_delay_seconds = reconnect_initial_delay_seconds
        self.reconnect_max_delay_seconds = reconnect_max_delay_seconds
        self.read_size = read_size
        self.timeout_seconds = timeout_seconds
        self.write_timeout_seconds = write_timeout_seconds
        self.queue_timeout_seconds = queue_timeout_seconds
        self.serial_kwargs = serial_kwargs


class CpythonUartProcessorService(object):
    def __init__(self, config, core=None, logger=None, serial_port=None):
        self.config = config
        self._logger = logger or logging.getLogger(self.__class__.__name__)
        self.core = core or EchoStreamProcessorCore(logger=self._logger.getChild("core"))

        self._serial = serial_port
        self._serial_connected = serial_port is not None
        self._running = False
        self._stop_event = threading.Event()
        self._send_lock = threading.Lock()
        self._connect_lock = threading.Lock()
        self._connect_thread = None
        self._receive_thread = None
        self._processor_thread = None
        self._data_queue = Queue()

    @property
    def is_running(self):
        return self._running

    @property
    def is_connected(self):
        return self._serial_connected

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
            name="echostream-cpython-uart-processor",
        )
        self._processor_thread.start()
        self._schedule_connect()

    def stop(self):
        if not self._running:
            return

        self._running = False
        self._stop_event.set()
        self._close_serial()

        if self._processor_thread is not None:
            self._processor_thread.join(timeout=3)
        if self._receive_thread is not None:
            self._receive_thread.join(timeout=3)
        if self._connect_thread is not None:
            self._connect_thread.join(timeout=3)

    def send_command(self, command):
        with self._send_lock:
            if not self._serial_connected or self._serial is None:
                raise RuntimeError("EchoStream UART is not connected")
            self._logger.debug("Sending outbound UART command: %s", command.hex().upper())
            self._serial.write(command)

    def _schedule_connect(self):
        with self._connect_lock:
            if self._connect_thread is not None and self._connect_thread.is_alive():
                return

            self._connect_thread = threading.Thread(
                target=self._connect_loop,
                daemon=True,
                name="echostream-cpython-uart-connect",
            )
            self._connect_thread.start()

    def _connect_loop(self):
        if self._serial_connected:
            self._start_receive_thread()
            return

        backoff = self.config.reconnect_initial_delay_seconds

        try:
            while self._running and not self._serial_connected:
                try:
                    self._serial = self._build_serial()
                    self._serial_connected = True
                    self._logger.info(
                        "Connected to EchoStream UART %s @ %s",
                        self.config.port,
                        self.config.baudrate,
                    )
                    self._start_receive_thread()
                    return
                except Exception as exc:
                    self._logger.warning(
                        "EchoStream UART connection failed: %s. Retrying in %.1f seconds.",
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

    def _start_receive_thread(self):
        self._receive_thread = threading.Thread(
            target=self._receive_loop,
            daemon=True,
            name="echostream-cpython-uart-receive",
        )
        self._receive_thread.start()

    def _build_serial(self):
        import serial

        kwargs = dict(self.config.serial_kwargs)
        kwargs.setdefault("timeout", self.config.timeout_seconds)
        kwargs.setdefault("write_timeout", self.config.write_timeout_seconds)
        return serial.Serial(self.config.port, self.config.baudrate, **kwargs)

    def _receive_loop(self):
        try:
            while self._running and self._serial_connected and self._serial is not None:
                data = self._serial.read(self.config.read_size)
                if not data:
                    continue
                self._logger.debug(
                    "Received %d byte(s) from EchoStream UART.",
                    len(data),
                )
                self._data_queue.put(data)
        except Exception as exc:
            if self._running:
                self._logger.warning("EchoStream UART receive error: %s", exc)
        finally:
            self._close_serial()
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
                self._logger.debug(
                    "Processed UART chunk into %d frame(s), %d event(s), %d command(s).",
                    len(batch.frames),
                    len(batch.events),
                    len(batch.outbound_commands),
                )
                for command in batch.outbound_commands:
                    self.send_command(command)
            except Exception:
                self._logger.exception("Failed to process EchoStream UART data chunk.")
            finally:
                self._data_queue.task_done()

    def _close_serial(self):
        serial_port = self._serial
        self._serial = None
        self._serial_connected = False

        if serial_port is None:
            return

        try:
            serial_port.close()
        except Exception:
            pass
