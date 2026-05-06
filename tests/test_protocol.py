from inovonics_echostream_processor.events import (
    CoordinatorStatusEvent,
    SecurityMessageEvent,
)
from inovonics_echostream_processor.core import EchoStreamProcessorCore
from inovonics_echostream_processor.protocol import EchoStreamProtocol


def _with_checksum(frame_without_checksum: bytes) -> bytes:
    return frame_without_checksum + bytes([EchoStreamProtocol.checksum(frame_without_checksum)])


def test_extract_frames_skips_noise_and_keeps_partial_frame() -> None:
    good_frame = _with_checksum(bytes([0x06, 0x02]))
    partial_frame = bytes([0x1C, 0x05, 0x00])

    frames, remainder = EchoStreamProtocol.extract_frames(b"\x00\xFF" + good_frame + partial_frame)

    assert frames == [good_frame]
    assert remainder == partial_frame


def test_parse_coordinator_status_event() -> None:
    frame = _with_checksum(bytes([0x1C, 0x05, 0x02, 0x00, 0xB9]))

    event = EchoStreamProtocol.parse_message(frame)

    assert isinstance(event, CoordinatorStatusEvent)
    assert event.unacknowledged_count == 2
    assert event.jammed is True
    assert event.case_tamper is True
    assert event.idle is True
    assert event.reset is True
    assert event.link_failure is True


def test_parse_security_message_event() -> None:
    frame = _with_checksum(
        bytes(
            [
                0x72,
                0x12,
                0xB2,
                0x01,
                0x02,
                0x03,
                0x11,
                0x22,
                0x33,
                0x44,
                0x00,
                0x01,
                0x3E,
                0x04,
                0x01,
                0x40,
                0x64,
                0x32,
            ]
        )
    )

    event = EchoStreamProtocol.parse_message(frame)

    assert isinstance(event, SecurityMessageEvent)
    assert event.device_uid_hex == "B2010203"
    assert event.device_serial_number == 66051
    assert event.device_model == "EN1210SK"
    assert event.signal_level == 100
    assert event.signal_margin == 50
    assert event.stat1_flags[0] is True
    assert event.stat0_flags[6] is True


def test_core_requests_coordinator_metadata() -> None:
    core = EchoStreamProcessorCore(auto_request_coordinator_metadata=True)
    frame = _with_checksum(bytes([0x1C, 0x05, 0x02, 0x00, 0xB9]))

    batch = core.feed(frame)

    assert len(batch.events) == 1
    assert batch.outbound_commands == [EchoStreamProtocol.REQUEST_COORDINATOR_SERIAL_NUMBER]
