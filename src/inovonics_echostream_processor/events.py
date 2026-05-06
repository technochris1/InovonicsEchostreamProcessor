from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, ClassVar


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class ProcessorEvent:
    raw_message: bytes
    occurred_at: datetime = field(default_factory=utc_now, kw_only=True)

    event_type: ClassVar[str] = "processor_event"

    @property
    def raw_hex(self) -> str:
        return self.raw_message.hex().upper()


@dataclass(slots=True)
class AckEvent(ProcessorEvent):
    event_type: ClassVar[str] = "ack"


@dataclass(slots=True)
class NakEvent(ProcessorEvent):
    error_code: int

    event_type: ClassVar[str] = "nak"


@dataclass(slots=True)
class CoordinatorStatusEvent(ProcessorEvent):
    unacknowledged_count: int
    stat1_byte: int
    stat0_byte: int
    jammed: bool
    case_tamper: bool
    idle: bool
    reset: bool
    link_failure: bool

    event_type: ClassVar[str] = "coordinator_status"


@dataclass(slots=True)
class CoordinatorSerialNumberEvent(ProcessorEvent):
    serial_number: int

    event_type: ClassVar[str] = "coordinator_serial_number"


@dataclass(slots=True)
class CoordinatorNetworkIdEvent(ProcessorEvent):
    network_id: int

    event_type: ClassVar[str] = "coordinator_network_id"


@dataclass(slots=True)
class RepeaterResetEvent(ProcessorEvent):
    device_uid_hex: str
    first_hop_hex: str
    trace_count: int
    hop_count: int

    event_type: ClassVar[str] = "repeater_reset"


@dataclass(slots=True)
class SecurityMessageEvent(ProcessorEvent):
    device_uid_hex: str
    device_serial_number: int
    first_hop_hex: str
    trace_count: int
    hop_count: int
    mid: int
    pti: int
    device_category: str
    device_model: str
    signal_level: int
    signal_margin: int
    stat1_flags: tuple[bool, ...]
    stat0_flags: tuple[bool, ...]

    event_type: ClassVar[str] = "security_message"


@dataclass(slots=True)
class NetworkStatusEvent(ProcessorEvent):
    device_uid_hex: str
    device_serial_number: int
    mode: int
    signal_level: int
    signal_margin: int

    event_type: ClassVar[str] = "network_status"


@dataclass(slots=True)
class UnknownMessageEvent(ProcessorEvent):
    header: int
    reason: str

    event_type: ClassVar[str] = "unknown_message"


EventHandler = Callable[[ProcessorEvent], None]
