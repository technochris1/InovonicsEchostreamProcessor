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

def test_aggregate_stream_emits_children_in_order_with_separate_rf():
    from inovonics_echostream_processor.events import AggregateMessageEvent

    frame = bytes.fromhex("72 1B 01 9D 10 BE 00 FA D0 2C 00 00 02 01 0B B2 43 E3 D7 3E 20 02 20 43 41 2E 2E 0C")
    for entry_length in (10, 11):
        body = bytearray(frame[:-1])
        body[14] = entry_length
        packet = _with_checksum(bytes(body))
        core = EchoStreamProcessorCore()
        emitted = []
        core.add_event_handler(emitted.append)
        assert core.feed(packet[:8]).events == []
        batch = core.feed(packet[8:])
        assert batch.frames == [packet]
        envelope, child = batch.events
        assert emitted == batch.events
        assert isinstance(envelope, AggregateMessageEvent)
        assert envelope.children == (child,)
        assert (envelope.signal_level, envelope.signal_margin) == (46, 46)
        assert isinstance(child, SecurityMessageEvent)
        assert child.device_uid_hex == "B243E3D7"
        assert child.first_hop_hex == "019D10BE"
        assert child.trace_uids_hex == ["00FAD02C"]
        assert child.delivery_mode == "aggregated"
        assert (child.signal_level, child.signal_margin) == (67, 65)


def test_bad_aggregate_cannot_emit_partial_children():
    from inovonics_echostream_processor.events import UnknownMessageEvent

    route = bytes.fromhex("01 9D 10 BE 00 FA D0 2C 00 00 02")
    first = bytes.fromhex("0B B2 43 E3 D7 3E 20 02 20 43 41")
    second = bytes.fromhex("0A B2 43 E3 D8 3E 20 02 43 41")  # STAT0 missing.
    body = route + bytes((2,)) + first + second + bytes((46, 46))
    packet = _with_checksum(bytes((0x72, len(body) + 2)) + body)
    core = EchoStreamProcessorCore()
    event, = core.feed(packet).events
    assert isinstance(event, UnknownMessageEvent)
    assert "aggregate" in event.reason
    assert core.feed(packet[:-1] + bytes((packet[-1] ^ 1,))).events == []


def test_directed_and_broadcast_repeater_status_and_reset():
    directed = bytes.fromhex("72 20 01 9D 10 BE 00 FA D0 2C 00 00 41 01 00 04 00 0A 00 00 00 00 00 00 00 00 00 01 C1 20 2E 2C 80")
    broadcast = _with_checksum(bytes.fromhex("72 12 01 9D 10 BE 00 FA D0 2C 00 00 41 00 C1 20 2E 2C"))
    for mode, packet in enumerate((broadcast, directed)):
        event = EchoStreamProtocol.parse_message(packet)
        assert event.mode == mode
        assert event.stat0_flags[5]
        assert (event.signal_level, event.signal_margin) == (46, 44)
    reset = bytes.fromhex("72 10 01 9D 10 BE 00 FA D0 2C 00 00 00 02 2A 28 38")
    event = EchoStreamProtocol.parse_message(reset)
    assert event.network_id == 2
    assert (event.signal_level, event.signal_margin) == (42, 40)


def test_report_cannot_read_checksum_as_network_id():
    from inovonics_echostream_processor.events import UnknownMessageEvent

    core = EchoStreamProcessorCore()
    event, = core.feed(bytes.fromhex("35 03 82 BA")).events
    assert isinstance(event, UnknownMessageEvent)
    assert core.coordinator_network_id is None


def test_configuration_and_serial_data_are_typed_events():
    from inovonics_echostream_processor.events import ConfigurationReportEvent, SerialDataEvent

    report = _with_checksum(bytes.fromhex("31 13 07 02 30 01 00 1E 00 00 00 00 00 B2 C0 A0 FF FF 00"))
    completion = _with_checksum(bytes.fromhex("7C 03 01"))
    report_event, completion_event = EchoStreamProcessorCore().feed(report + completion).events
    assert isinstance(report_event, ConfigurationReportEvent)
    assert report_event.acceptable_mids == [0xB2, 0xC0, 0xA0]
    assert completion_event.status == 1
    serial_data = _with_checksum(bytes.fromhex("72 10 B2 01 02 03 00 FA D0 2C 00 01 18 AA 3C 32"))
    event = EchoStreamProtocol.parse_message(serial_data)
    assert isinstance(event, SerialDataEvent)
    assert event.payload == b"\xAA"


def test_icn3000_decode_all_patterns_and_reset_precedence():
    from inovonics_echostream_processor import decode_icn3000_7

    for pattern, alarm in enumerate((None, 1, 2, 4, 3, 5, 6, 7)):
        stat1 = EchoStreamProtocol.flags_lsb_first(pattern & 3)
        stat0 = EchoStreamProtocol.flags_lsb_first(0x20 if pattern & 4 else 0)
        assert decode_icn3000_7(stat1, stat0) == alarm
    assert decode_icn3000_7((True, True), EchoStreamProtocol.flags_lsb_first(0x28)) == 0
