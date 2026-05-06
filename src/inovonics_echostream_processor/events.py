class ProcessorEvent(object):
    event_type = "processor_event"

    def __init__(self, raw_message, **fields):
        self.raw_message = raw_message
        for key, value in fields.items():
            setattr(self, key, value)

    @property
    def raw_hex(self):
        return self.raw_message.hex().upper()

    def to_dict(self):
        data = {"event_type": self.event_type, "raw_message": self.raw_message, "raw_hex": self.raw_hex}
        data.update(self.__dict__)
        return data


class AckEvent(ProcessorEvent):
    event_type = "ack"


class NakEvent(ProcessorEvent):
    event_type = "nak"


class CoordinatorStatusEvent(ProcessorEvent):
    event_type = "coordinator_status"


class CoordinatorSerialNumberEvent(ProcessorEvent):
    event_type = "coordinator_serial_number"


class CoordinatorNetworkIdEvent(ProcessorEvent):
    event_type = "coordinator_network_id"


class RepeaterResetEvent(ProcessorEvent):
    event_type = "repeater_reset"


class SecurityMessageEvent(ProcessorEvent):
    event_type = "security_message"


class NetworkStatusEvent(ProcessorEvent):
    event_type = "network_status"


class UnknownMessageEvent(ProcessorEvent):
    event_type = "unknown_message"
