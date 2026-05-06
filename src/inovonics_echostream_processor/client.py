from __future__ import annotations

import logging
import socket
import threading
from dataclasses import dataclass
from queue import Empty, Queue
from typing import Optional

from inovonics_echostream_processor.events import (
    CoordinatorNetworkIdEvent,
    CoordinatorSerialNumberEvent,
    CoordinatorStatusEvent,
    EventHandler,
    ProcessorEvent,
)
from inovonics_echostream_processor.protocol import EchoStreamProtocol


@dataclass(slots=True)
class EchoStreamProcessorConfig:
    host: str
    port: int
    reconnect_initial_delay_seconds: float = 1.0
    reconnect_max_delay_seconds: float = 60.0
    socket_timeout_seconds: float = 5.0
    queue_timeout_seconds: float = 1.0
    auto_request_coordinator_metadata: bool = True


@dataclass(slots=True)
class ProcessorMetrics:
    total_frames: int = 0
    processed_events: int = 0
    failed_frames: int = 0
    reconnects: int = 0


class EchoStreamProcessor:
    def __init__(
        self,
        config: EchoStreamProcessorConfig,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.config = config
        self._logger = logger or logging.getLogger(self.__class__.__name__)

        self._socket: socket.socket | None = None
        self._socket_connected = False
        self._running = False
        self._stop_event = threading.Event()
        self._send_lock = threading.Lock()
        self._connect_lock = threading.Lock()
        self._connect_thread: threading.Thread | None = None
        self._receive_thread: threading.Thread | None = None
        self._processor_thread: threading.Thread | None = None
        self._message_queue: Queue[bytes] = Queue()
        self._handlers: list[EventHandler] = []

        self.coordinator_serial_number: int | None = None
        self.coordinator_network_id: int | None = None
        self.metrics = ProcessorMetrics()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_connected(self) -> bool:
        return self._socket_connected

    def add_event_handler(self, handler: EventHandler) -> None:
        self._handlers.append(handler)

    def start(self) -> None:
        if self._running:
            return

        self._running = True
        self._stop_event.clear()
        self._processor_thread = threading.Thread(
            target=self._process_message_queue,
            daemon=True,
            name="echostream-processor-queue",
        )
        self._processor_thread.start()
        self._schedule_connect()

    def stop(self) -> None:
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

    def send_command(self, command: bytes) -> None:
        with self._send_lock:
            if not self._socket_connected or self._socket is None:
                raise RuntimeError("EchoStream socket is not connected")
            self._socket.sendall(command)

    def request_coordinator_serial_number(self) -> None:
        self.send_command(EchoStreamProtocol.REQUEST_COORDINATOR_SERIAL_NUMBER)

    def request_coordinator_network_id(self) -> None:
        self.send_command(EchoStreamProtocol.REQUEST_COORDINATOR_NETWORK_ID)

    def _schedule_connect(self) -> None:
        with self._connect_lock:
            if self._connect_thread is not None and self._connect_thread.is_alive():
                return

            self._connect_thread = threading.Thread(
                target=self._connect_loop,
                daemon=True,
                name="echostream-processor-connect",
            )
            self._connect_thread.start()

    def _connect_loop(self) -> None:
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
                        name="echostream-processor-receive",
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

    def _receive_loop(self) -> None:
        buffer = b""

        try:
            while self._running and self._socket_connected and self._socket is not None:
                try:
                    data = self._socket.recv(1024)
                except socket.timeout:
                    continue

                if not data:
                    self._logger.warning("EchoStream socket closed by peer.")
                    break

                buffer += data
                frames, buffer = EchoStreamProtocol.extract_frames(buffer)
                for frame in frames:
                    self.metrics.total_frames += 1
                    self._message_queue.put(frame)
        except OSError as exc:
            if self._running:
                self._logger.warning("EchoStream receive error: %s", exc)
        finally:
            self._socket_connected = False
            self._close_socket()
            if self._running:
                self._schedule_connect()

    def _close_socket(self) -> None:
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

    def _process_message_queue(self) -> None:
        while not self._stop_event.is_set():
            try:
                frame = self._message_queue.get(timeout=self.config.queue_timeout_seconds)
            except Empty:
                continue

            try:
                event = EchoStreamProtocol.parse_message(frame)
                self._update_state(event)
                self._emit(event)
                self.metrics.processed_events += 1
            except Exception:
                self.metrics.failed_frames += 1
                self._logger.exception("Failed to process EchoStream frame.")
            finally:
                self._message_queue.task_done()

    def _update_state(self, event: ProcessorEvent) -> None:
        if isinstance(event, CoordinatorSerialNumberEvent):
            self.coordinator_serial_number = event.serial_number
            return

        if isinstance(event, CoordinatorNetworkIdEvent):
            self.coordinator_network_id = event.network_id
            return

        if (
            isinstance(event, CoordinatorStatusEvent)
            and self.config.auto_request_coordinator_metadata
        ):
            try:
                if self.coordinator_serial_number is None:
                    self.request_coordinator_serial_number()
                elif self.coordinator_network_id is None:
                    self.request_coordinator_network_id()
            except RuntimeError:
                self._logger.debug(
                    "Skipped coordinator metadata request because the socket is not connected."
                )

    def _emit(self, event: ProcessorEvent) -> None:
        for handler in list(self._handlers):
            try:
                handler(event)
            except Exception:
                self._logger.exception(
                    "Unhandled exception from EchoStream event handler %r.",
                    handler,
                )
