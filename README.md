# Inovonics EchoStream Processor

`InovonicsEchostreamProcessor` is the reusable transport and protocol layer for
Inovonics EchoStream integrations. It owns socket connectivity, frame
reassembly, checksum validation, and normalized event emission so new apps can
consume EchoStream traffic without inheriting MQTT or Home Assistant concerns.

## Features

- TCP client with exponential reconnect backoff
- Frame synchronization and checksum validation
- Normalized events for coordinator, security, repeater reset, and network
  status messages
- Thread-safe event handler registration
- Small dependency surface suitable for reuse in multiple applications

## Install

```bash
pip install .
```

## Quick Start

```python
from inovonics_echostream_processor import EchoStreamProcessor, EchoStreamProcessorConfig


def handle_event(event):
    print(event.event_type, event.raw_hex)


processor = EchoStreamProcessor(
    EchoStreamProcessorConfig(host="192.168.1.60", port=10001),
)
processor.add_event_handler(handle_event)
processor.start()
```

## Event Model

The library emits dataclass-based events such as:

- `CoordinatorStatusEvent`
- `CoordinatorSerialNumberEvent`
- `CoordinatorNetworkIdEvent`
- `SecurityMessageEvent`
- `RepeaterResetEvent`
- `NetworkStatusEvent`
- `AckEvent`
- `NakEvent`
- `UnknownMessageEvent`

Each event carries the raw binary message alongside normalized fields for use by
application code.
