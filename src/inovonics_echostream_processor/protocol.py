import logging

from inovonics_echostream_processor.device_types import (
    device_category_label,
    device_model_label,
)
from inovonics_echostream_processor.events import (
    AckEvent,
    AggregateMessageEvent,
    ConfigurationReportEvent,
    CoordinatorNetworkIdEvent,
    CoordinatorSerialNumberEvent,
    CoordinatorStatusEvent,
    NakEvent,
    NetworkStatusEvent,
    RepeaterResetEvent,
    SecurityMessageEvent,
    SerialDataEvent,
    UnknownMessageEvent,
)


class EchoStreamProtocol:
    START_BYTES = {0x06, 0x15, 0x1C, 0x31, 0x35, 0x72, 0x7C}
    MAX_AGGREGATE_MESSAGES = 64
    MAX_AGGREGATE_ENTRY_PAYLOAD = 85
    MAX_AGGREGATE_TRACE_UIDS = 10
    REQUEST_COORDINATOR_SERIAL_NUMBER = b"\x34\x03\x90\xC7"
    REQUEST_COORDINATOR_NETWORK_ID = b"\x34\x03\x82\xB9"
    _logger = logging.getLogger(__name__)

    @staticmethod
    def checksum(data: bytes) -> int:
        return sum(data) & 0xFF

    @staticmethod
    def flags_lsb_first(byte_value):
        return tuple(bool(byte_value & (1 << bit)) for bit in range(8))

    @classmethod
    def extract_frames(cls, buffer):
        frames = []

        while buffer:
            if buffer[0] not in cls.START_BYTES:
                cls._logger.debug(
                    "Discarding %d byte(s) before start byte 0x%02X.",
                    1,
                    buffer[0],
                )
                buffer = buffer[1:]
                continue

            if len(buffer) < 2:
                cls._logger.debug("Waiting for more data to read frame length.")
                break

            total_length = buffer[1] + 1
            if total_length < 3:
                cls._logger.debug(
                    "Discarding short candidate frame with declared length %d.",
                    total_length,
                )
                buffer = buffer[1:]
                continue

            if len(buffer) < total_length:
                cls._logger.debug(
                    "Waiting for %d more byte(s) to complete frame.",
                    total_length - len(buffer),
                )
                break

            candidate = buffer[:total_length]
            buffer = buffer[total_length:]

            if cls.checksum(candidate[:-1]) != candidate[-1]:
                cls._logger.debug(
                    "Dropping frame with invalid checksum: %s",
                    candidate.hex().upper(),
                )
                continue

            cls._logger.debug("Accepted frame: %s", candidate.hex().upper())
            frames.append(candidate)

        return frames, buffer

    @staticmethod
    def _unknown(message, reason):
        return UnknownMessageEvent(raw_message=message, header=message[0] if message else None, reason=reason)

    @classmethod
    def parse_message(cls, message):
        message = bytes(message)
        if len(message) < 3 or message[1] + 1 != len(message):
            return cls._unknown(message, "Malformed frame length")
        if cls.checksum(message[:-1]) != message[-1]:
            return cls._unknown(message, "Invalid checksum")

        header = message[0]
        payload = message[2:-1]  # Exclude the checksum from all field reads.
        if header == 0x06 and not payload:
            return AckEvent(raw_message=message)
        if header == 0x15 and len(payload) == 1:
            return NakEvent(raw_message=message, error_code=payload[0])
        if header == 0x1C and len(payload) == 3:
            unacknowledged_count, stat1, stat0 = payload
            return CoordinatorStatusEvent(
                raw_message=message, unacknowledged_count=unacknowledged_count,
                stat1_byte=stat1, stat0_byte=stat0,
                jammed=bool(stat0 & 0x80), case_tamper=bool(stat0 & 0x20),
                idle=bool(stat0 & 0x10), reset=bool(stat0 & 0x08),
                link_failure=bool(stat0 & 0x01),
            )
        if header == 0x35 and payload:
            return cls._parse_coordinator_report(message, payload)
        if header == 0x31 and len(payload) == 17 and payload[0] == 0x07:
            return ConfigurationReportEvent(
                raw_message=message, event_type="serial_receiver_configuration",
                network_id=payload[1], output_type=payload[2], configuration=payload[3],
                serial_checkin_seconds=int.from_bytes(payload[4:6], "big"),
                acceptable_mids=[mid for mid in payload[11:16] if mid != 0xFF],
            )
        if header == 0x7C and len(payload) == 1:
            status = payload[0]
            return ConfigurationReportEvent(
                raw_message=message, event_type="nid_configuration_complete",
                status=status, status_label={0: "failed", 1: "completed successfully"}.get(status, "unknown result"),
            )
        if header == 0x72:
            return cls._parse_inbound(message, payload)
        reason = "Malformed message" if header in cls.START_BYTES else "Unsupported header"
        return cls._unknown(message, reason)

    @classmethod
    def _parse_coordinator_report(cls, message, payload):
        report_code = payload[0]
        data = payload[1:]
        if report_code == 0x82 and len(data) == 1 and data[0] <= 31:
            return CoordinatorNetworkIdEvent(raw_message=message, network_id=data[0])
        if report_code == 0x90 and len(data) == 3:
            return CoordinatorSerialNumberEvent(raw_message=message, serial_number=int.from_bytes(data, "big"))

        if report_code == 0x81 and len(data) == 2:
            event_type = "coordinator_inbound_format_report"
            fields = {"output_type": data[0], "configuration": data[1]}
        elif report_code == 0x83 and len(data) == 5:
            event_type = "coordinator_acceptable_mids_report"
            fields = {"acceptable_mids": [mid for mid in data if mid != 0xFF]}
        elif report_code in (0x85, 0x86) and len(data) == 3:
            seconds = int.from_bytes(data[:2], "big")
            if report_code == 0x85:
                event_type = "coordinator_checkin_setting_report"
                fields = {"serial_checkin_seconds": seconds, "configuration": data[2]}
            else:
                event_type = "coordinator_outbound_status_report"
                fields = {"rf_checkin_seconds": seconds, "configuration": data[2]}
        elif report_code == 0x87 and len(data) == 2:
            event_type = "coordinator_link_supervision_report"
            fields = {"link_supervision_seconds": int.from_bytes(data, "big")}
        else:
            if report_code in (0x81, 0x82, 0x83, 0x85, 0x86, 0x87, 0x90):
                return cls._unknown(message, "Malformed coordinator report")
            return cls._unknown(message, f"Unsupported report code 0x{report_code:02X}")
        return ConfigurationReportEvent(raw_message=message, event_type=event_type, report_code=report_code, **fields)

    @classmethod
    def _parse_inbound(cls, message, payload):
        if len(payload) < 11:
            return cls._unknown(message, "Malformed inbound route")
        trace_count = payload[8]
        hop_index = 9 + trace_count * 4
        if hop_index + 1 >= len(payload):
            return cls._unknown(message, "Malformed inbound route")

        uid = payload[:4]
        first_hop = payload[4:8]
        fields = dict(
            device_uid_hex=uid.hex().upper(),
            device_serial_number=int.from_bytes(uid[1:], "big"),
            first_hop_hex=first_hop.hex().upper(),
            trace_count=trace_count,
            trace_uids_hex=[payload[i:i + 4].hex().upper() for i in range(9, hop_index, 4)],
            hop_count=payload[hop_index],
            delivery_mode="direct",
        )
        data = payload[hop_index + 1:]
        if data[0] == 0x02:
            return cls._parse_aggregate(message, uid, payload[4:hop_index], data[1:], fields)
        return cls._parse_device_payload(message, uid[0], data, fields)

    @classmethod
    def _parse_device_payload(cls, message, mid, data, fields):
        message_class = data[0]
        if message_class == 0x3E and len(data) == 6:
            pti, stat1, stat0, level, margin = data[1:]
            return SecurityMessageEvent(
                raw_message=message, mid=mid, pti=pti, device_category=device_category_label(mid),
                device_model=device_model_label(mid, pti), stat1_flags=cls.flags_lsb_first(stat1),
                stat0_flags=cls.flags_lsb_first(stat0), **cls._signal_fields(level, margin), **fields,
            )
        if message_class == 0x41 and len(data) >= 2:
            product_type = data[1]
            if (product_type, len(data)) in ((0, 6), (1, 20)):
                stat1, stat0, level, margin = data[-4:]
                return NetworkStatusEvent(
                    raw_message=message, mode=product_type, product_type=product_type,
                    device_model=device_model_label(mid, product_type),
                    stat1_flags=cls.flags_lsb_first(stat1), stat0_flags=cls.flags_lsb_first(stat0),
                    **cls._signal_fields(level, margin), **fields,
                )
        if message_class == 0x00 and len(data) == 4 and data[1] <= 31:
            return RepeaterResetEvent(
                raw_message=message, network_id=data[1], **cls._signal_fields(data[2], data[3]), **fields,
            )
        if message_class == 0x18 and len(data) >= 4:
            return SerialDataEvent(
                raw_message=message, payload=data[1:-2], payload_length=len(data) - 3,
                **cls._signal_fields(data[-2], data[-1]), **fields,
            )
        if message_class in (0x00, 0x18, 0x3E, 0x41):
            return cls._unknown(message, "Malformed device payload")
        return cls._unknown(message, f"Unsupported message class 0x{message_class:02X}")

    @staticmethod
    def _signal_fields(level, margin):
        return dict(signal_level=level, signal_margin=margin, signal_valid=level <= 99 and margin <= 99)

    @classmethod
    def _parse_aggregate(cls, message, aggregator_uid, upstream_route, data, fields):
        if (len(data) < 3 or not 1 <= data[0] <= cls.MAX_AGGREGATE_MESSAGES
                or fields["trace_count"] > cls.MAX_AGGREGATE_TRACE_UIDS):
            return cls._unknown(message, "Malformed aggregate")

        # Firmware differs on whether an entry counts its own length byte.
        for includes_length in (True, False):
            entries = cls._aggregate_entries(data[1:-2], data[0], includes_length)
            if entries is not None:
                break
        else:
            return cls._unknown(message, "Malformed aggregate entries")

        # The original first hop and trace are upstream of the aggregator.
        # The embedded RF values describe child reception at the aggregator.
        route_uids = [upstream_route[:4]]
        route_uids.extend(upstream_route[i:i + 4] for i in range(5, len(upstream_route), 4))
        trace = [uid for uid in route_uids if uid != aggregator_uid]
        trace_hex = [uid.hex().upper() for uid in trace]
        shared_fields = dict(
            first_hop_hex=fields["device_uid_hex"], trace_count=len(trace),
            trace_uids_hex=trace_hex, hop_count=fields["hop_count"], delivery_mode="aggregated",
            aggregated=True, aggregate_repeater_uid_hex=fields["device_uid_hex"],
        )
        # Reconstruct the canonical child frame for consumers of raw_message.
        route = aggregator_uid + bytes((len(trace),)) + b"".join(trace) + bytes((fields["hop_count"],))
        children = []
        for entry in entries:
            uid, payload = entry[:4], entry[4:]
            body = uid + route + payload
            frame_without_checksum = bytes((0x72, len(body) + 2)) + body
            child_frame = frame_without_checksum + bytes((cls.checksum(frame_without_checksum),))
            child = cls._parse_device_payload(
                child_frame, uid[0], payload,
                dict(shared_fields, device_uid_hex=uid.hex().upper(),
                     device_serial_number=int.from_bytes(uid[1:], "big")),
            )
            if isinstance(child, UnknownMessageEvent) and child.reason == "Malformed device payload":
                return cls._unknown(message, "Malformed aggregate child payload")
            children.append(child)

        fields["delivery_mode"] = "aggregated"
        return AggregateMessageEvent(
            raw_message=message, children=tuple(children), **cls._signal_fields(data[-2], data[-1]), **fields,
        )

    @classmethod
    def _aggregate_entries(cls, body, count, includes_length):
        entries = []
        cursor = 0
        for _ in range(count):
            if cursor >= len(body):
                return None
            end = cursor + body[cursor] + (0 if includes_length else 1)
            payload_length = end - cursor - 7
            if end > len(body) or not 1 <= payload_length <= cls.MAX_AGGREGATE_ENTRY_PAYLOAD:
                return None
            entries.append(body[cursor + 1:end])
            cursor = end
        return entries if cursor == len(body) else None
