from inovonics_echostream_processor.events import (
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
    def __init__(self, auto_request_coordinator_metadata=True):
        self.auto_request_coordinator_metadata = auto_request_coordinator_metadata
        self._buffer = b""
        self._handlers = []
        self.coordinator_serial_number = None
        self.coordinator_network_id = None

    def add_event_handler(self, handler):
        self._handlers.append(handler)

    def feed(self, data):
        if not data:
            return ProcessBatch()

        self._buffer += data
        frames, self._buffer = EchoStreamProtocol.extract_frames(self._buffer)

        events = []
        outbound_commands = []
        for frame in frames:
            event, commands = self.process_frame(frame)
            events.append(event)
            outbound_commands.extend(commands)

        return ProcessBatch(
            frames=frames,
            events=events,
            outbound_commands=outbound_commands,
        )

    def process_frame(self, frame):
        event = EchoStreamProtocol.parse_message(frame)
        commands = self._update_state(event)
        self._emit(event)
        return event, commands

    def _update_state(self, event):
        if isinstance(event, CoordinatorSerialNumberEvent):
            self.coordinator_serial_number = event.serial_number
            return []

        if isinstance(event, CoordinatorNetworkIdEvent):
            self.coordinator_network_id = event.network_id
            return []

        if (
            isinstance(event, CoordinatorStatusEvent)
            and self.auto_request_coordinator_metadata
        ):
            if self.coordinator_serial_number is None:
                return [EchoStreamProtocol.REQUEST_COORDINATOR_SERIAL_NUMBER]
            if self.coordinator_network_id is None:
                return [EchoStreamProtocol.REQUEST_COORDINATOR_NETWORK_ID]

        return []

    def _emit(self, event):
        for handler in list(self._handlers):
            handler(event)
