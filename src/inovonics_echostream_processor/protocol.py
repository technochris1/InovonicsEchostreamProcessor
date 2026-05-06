from inovonics_echostream_processor.device_types import (
    device_category_label,
    device_model_label,
)
from inovonics_echostream_processor.events import (
    AckEvent,
    CoordinatorNetworkIdEvent,
    CoordinatorSerialNumberEvent,
    CoordinatorStatusEvent,
    NakEvent,
    NetworkStatusEvent,
    RepeaterResetEvent,
    SecurityMessageEvent,
    UnknownMessageEvent,
)


class EchoStreamProtocol:
    START_BYTES = {0x06, 0x15, 0x1C, 0x35, 0x72}
    REQUEST_COORDINATOR_SERIAL_NUMBER = b"\x34\x03\x90\xC7"
    REQUEST_COORDINATOR_NETWORK_ID = b"\x34\x03\x82\xB9"

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
                buffer = buffer[1:]
                continue

            if len(buffer) < 2:
                break

            total_length = buffer[1] + 1
            if total_length < 3:
                buffer = buffer[1:]
                continue

            if len(buffer) < total_length:
                break

            candidate = buffer[:total_length]
            buffer = buffer[total_length:]

            if cls.checksum(candidate[:-1]) != candidate[-1]:
                continue

            frames.append(candidate)

        return frames, buffer

    @classmethod
    def parse_message(cls, message):
        header = message[0]

        try:
            if header == 0x06:
                return AckEvent(raw_message=message)

            if header == 0x15:
                return NakEvent(raw_message=message, error_code=message[2])

            if header == 0x1C:
                stat0_byte = message[4]
                return CoordinatorStatusEvent(
                    raw_message=message,
                    unacknowledged_count=message[2],
                    stat1_byte=message[3],
                    stat0_byte=stat0_byte,
                    jammed=bool(stat0_byte & 0x80),
                    case_tamper=bool(stat0_byte & 0x20),
                    idle=bool(stat0_byte & 0x10),
                    reset=bool(stat0_byte & 0x08),
                    link_failure=bool(stat0_byte & 0x01),
                )

            if header == 0x35:
                report_code = message[2]
                if report_code == 0x82:
                    return CoordinatorNetworkIdEvent(
                        raw_message=message,
                        network_id=message[3],
                    )
                if report_code == 0x90:
                    return CoordinatorSerialNumberEvent(
                        raw_message=message,
                        serial_number=int.from_bytes(message[3:6], byteorder="big"),
                    )
                return UnknownMessageEvent(
                    raw_message=message,
                    header=header,
                    reason=f"Unsupported report code 0x{report_code:02X}",
                )

            if header == 0x72:
                trace_count = message[10]
                hop_count_index = 11 + (trace_count * 4)
                message_class_index = 12 + (trace_count * 4)
                message_class = message[message_class_index]
                device_uid_hex = message[2:6].hex().upper()
                device_serial_number = int.from_bytes(message[3:6], byteorder="big")
                first_hop_hex = message[6:10].hex().upper()
                hop_count = message[hop_count_index]

                if message_class == 0x00:
                    return RepeaterResetEvent(
                        raw_message=message,
                        device_uid_hex=device_uid_hex,
                        first_hop_hex=first_hop_hex,
                        trace_count=trace_count,
                        hop_count=hop_count,
                    )

                if message_class == 0x3E:
                    pti = message[message_class_index + 1]
                    stat1_flags = cls.flags_lsb_first(message[message_class_index + 2])
                    stat0_flags = cls.flags_lsb_first(message[message_class_index + 3])
                    return SecurityMessageEvent(
                        raw_message=message,
                        device_uid_hex=device_uid_hex,
                        device_serial_number=device_serial_number,
                        first_hop_hex=first_hop_hex,
                        trace_count=trace_count,
                        hop_count=hop_count,
                        mid=message[2],
                        pti=pti,
                        device_category=device_category_label(message[2]),
                        device_model=device_model_label(message[2], pti),
                        signal_level=message[message_class_index + 4],
                        signal_margin=message[message_class_index + 5],
                        stat1_flags=stat1_flags,
                        stat0_flags=stat0_flags,
                    )

                if message_class == 0x41:
                    return NetworkStatusEvent(
                        raw_message=message,
                        device_uid_hex=device_uid_hex,
                        device_serial_number=device_serial_number,
                        mode=message[message_class_index + 1],
                        signal_level=message[message_class_index + 4],
                        signal_margin=message[message_class_index + 5],
                    )

                return UnknownMessageEvent(
                    raw_message=message,
                    header=header,
                    reason=f"Unsupported message class 0x{message_class:02X}",
                )

            return UnknownMessageEvent(
                raw_message=message,
                header=header,
                reason="Unsupported header",
            )
        except IndexError:
            return UnknownMessageEvent(
                raw_message=message,
                header=header,
                reason="Malformed message",
            )
