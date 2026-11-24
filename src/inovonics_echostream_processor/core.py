import logging

from inovonics_echostream_processor.events import (
    AggregateMessageEvent,
    CoordinatorNetworkIdEvent,
    CoordinatorSerialNumberEvent,
    CoordinatorStatusEvent,
)
from inovonics_echostream_processor.protocol import EchoStreamProtocol


class ProcessBatch(object):
    def __init__(self, frames=None, events=None, outbound_commands=None):
        self.frames = frames or []
        self.events = events or []
        self.outbound_commands = outbound_commands or []


class EchoStreamProcessorCore(object):
    def __init__(self, auto_request_coordinator_metadata=True, logger=None):
        self.auto_request_coordinator_metadata = auto_request_coordinator_metadata
        self._logger = logger or logging.getLogger(self.__class__.__name__)
        self._buffer = b""
        self._handlers = []
        self.coordinator_serial_number = None
        self.coordinator_network_id = None

    def add_event_handler(self, handler):
        self._handlers.append(handler)

    def feed(self, data):
        if not data:
            self._logger.debug("Ignoring empty EchoStream data chunk.")
            return ProcessBatch()

        self._logger.debug(
            "Received %d bytes of EchoStream data; buffer before append=%d.",
            len(data),
            len(self._buffer),
        )
        self._buffer += data
        frames, self._buffer = EchoStreamProtocol.extract_frames(self._buffer)
        self._logger.debug(
            "Extracted %d frame(s); %d buffered byte(s) remain.",
            len(frames),
            len(self._buffer),
        )

        events = []
        outbound_commands = []
        for frame in frames:
            self._logger.debug("Processing frame: %s", frame.hex().upper())
            event, commands = self.process_frame(frame)
            events.append(event)
            if isinstance(event, AggregateMessageEvent):
                events.extend(event.children)
            outbound_commands.extend(commands)

        self._logger.debug(
            "Feed completed with %d event(s) and %d outbound command(s).",
            len(events),
            len(outbound_commands),
        )
        return ProcessBatch(
            frames=frames,
            events=events,
            outbound_commands=outbound_commands,
        )

    def process_frame(self, frame):
        event = EchoStreamProtocol.parse_message(frame)
        commands = self._update_state(event)
        self._emit(event)
        if isinstance(event, AggregateMessageEvent):
            for child in event.children:
                self._emit(child)
        self._logger.debug(
            "Parsed frame into %s; queued %d outbound command(s).",
            event.event_type,
            len(commands),
        )
        return event, commands

    def _update_state(self, event):
        if isinstance(event, CoordinatorSerialNumberEvent):
            self.coordinator_serial_number = event.serial_number
            self._logger.debug(
                "Updated coordinator serial number to %s.",
                event.serial_number,
            )
            return []

        if isinstance(event, CoordinatorNetworkIdEvent):
            self.coordinator_network_id = event.network_id
            self._logger.debug(
                "Updated coordinator network id to %s.",
                event.network_id,
            )
            return []

        if (
            isinstance(event, CoordinatorStatusEvent)
            and self.auto_request_coordinator_metadata
        ):
            if self.coordinator_serial_number is None:
                self._logger.debug(
                    "Coordinator status received without serial number; requesting metadata."
                )
                return [EchoStreamProtocol.REQUEST_COORDINATOR_SERIAL_NUMBER]
            if self.coordinator_network_id is None:
                self._logger.debug(
                    "Coordinator status received without network id; requesting metadata."
                )
                return [EchoStreamProtocol.REQUEST_COORDINATOR_NETWORK_ID]

        return []

    def _emit(self, event):
        self._logger.debug(
            "Emitting %s to %d handler(s).",
            event.event_type,
            len(self._handlers),
        )
        for handler in list(self._handlers):
            handler(event)
