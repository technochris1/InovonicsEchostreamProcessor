# Inovonics EchoStream Processor

`InovonicsEchostreamProcessor` is the reusable EchoStream protocol package for
new applications. The core is transport-free so it can run on standard Python
and MicroPython, while runtime-specific adapters live in separate modules.

## Architecture

- Core:
  - frame synchronization
  - checksum validation
  - EchoStream message parsing
  - device type mapping
  - normalized event emission
  - coordinator metadata state and suggested outbound commands
  - optional per-device, per-bit state coalescing for downstream apps
- Flat transport adapters in `transports/`:
  - `cpython_socket.py`
  - `cpython_uart.py`
  - `micropython_uart.py`
  - `micropython_socket.py`

The core never imports `socket`, `threading`, `queue`, `serial`, or `machine`.

The optional bit coalescer keeps only one pending record per
`(device_uid_hex, stat_group, bit)` and automatically evicts idle entries, so
apps can buffer chatty state transitions without unbounded memory growth.

### Security status capabilities

The processor includes the security end-device capability matrix from the
Inovonics Security End Device Developer Guide, Revision I, pages 24-26. Use
`security_event_to_supported_bit_state_updates(event)` when a downstream app
should receive only the status bits documented for that product model. Use
`security_event_to_bit_state_updates(event)` when a diagnostic view needs all
raw status bits, including reserved positions.

The filtered helper is conservative: a product model not present in the guide
is treated as unknown and all raw bits are retained. Existing consumers keep
the historical one-based `BitStateUpdate.bit` field; `protocol_bit` exposes the
actual zero-based wire bit from the EchoStream message.

For the CPython UART adapter, install the optional dependency set:

```bash
pip install .[cpython_uart]
```

## Runtime Detection

The package exposes small runtime helpers:

- `detect_runtime()`
- `is_cpython()`
- `is_micropython()`

Transport exports are conditional. Standard Python can import the CPython
adapters, while MicroPython can import the MicroPython adapters without dragging
in the wrong runtime dependencies.

## Core Example

```python
from inovonics_echostream_processor import EchoStreamProcessorCore


core = EchoStreamProcessorCore()
batch = core.feed(b"...binary bytes...")
for event in batch.events:
    print(event.event_type, event.raw_hex)
for command in batch.outbound_commands:
    print("send command", command.hex())
```

## Aggregate, repeater, and control frames

The processor validates both observed aggregate entry-length conventions and
emits an AggregateMessageEvent followed by its children in wire order.
ProcessBatch.frames contains the original wire frames. ProcessBatch.events
and event handlers receive both the envelope and the children. When calling
EchoStreamProtocol.parse_message directly, read children from the envelope.
The envelope's signal and margin belong to the upstream link. Each child
keeps its own readings and lists the aggregator as its first hop.

Repeater status supports broadcast and directed layouts. Repeater reset
reports include the repeater's NID and RF readings. Existing raw signal values
are preserved and signal_valid indicates whether both fall within 0-99.
Malformed frames cannot supply data from the checksum byte. Receiver and
coordinator configuration reports and inbound serial data are typed events.

Use decode_icn3000_7 with a transmitter explicitly configured for seven-code
ICN 3000 mode. It returns an alarm number, 0 for RESET, or None for a
zero-input report. Consumers own call state and should clear it on RESET.

## CPython Socket Example

```python
from inovonics_echostream_processor.transports.cpython_socket import (
    SocketProcessorConfig,
    SocketProcessorService,
)


service = SocketProcessorService(
    SocketProcessorConfig(host="192.168.1.60", port=10001),
)
service.add_event_handler(lambda event: print(event.event_type))
service.start()
```

## CPython UART Example

```python
from inovonics_echostream_processor.transports.cpython_uart import (
    CpythonUartProcessorConfig,
    CpythonUartProcessorService,
)


service = CpythonUartProcessorService(
    CpythonUartProcessorConfig(port="COM5", baudrate=9600),
)
service.add_event_handler(lambda event: print(event.event_type))
service.start()
```

## MicroPython UART Example

```python
from inovonics_echostream_processor.transports.micropython_uart import (
    MicroPythonUartProcessor,
    MicroPythonUartProcessorConfig,
)


processor = MicroPythonUartProcessor(
    MicroPythonUartProcessorConfig(uart_id=0, baudrate=9600),
)
while True:
    processor.poll_once()
```

## MicroPython Socket Example

```python
from inovonics_echostream_processor.transports.micropython_socket import (
    MicroPythonSocketProcessor,
    MicroPythonSocketProcessorConfig,
)


processor = MicroPythonSocketProcessor(
    MicroPythonSocketProcessorConfig(host="192.168.1.60", port=10001),
)
while True:
    processor.poll_once()
```

<!-- CODEX-REPO-MAP START -->
# InovonicsEchostreamProcessor

This repository contains the `InovonicsEchostreamProcessor` project.

Primary languages and file types: Python.

## Root files

| Item | Role |
| --- | --- |
| `.gitignore` | Supporting file. |
| `pyproject.toml` | Python project metadata. |

## App folders

| Folder | Summary |
| --- | --- |
| `src/inovonics_echostream_processor` | Code folder for `inovonics_echostream_processor`; contains `bit_coalescer.py`, `client.py`, `compat.py`, `core.py`, `device_types.py`. |
| `src/inovonics_echostream_processor/transports` | Code folder for `transports`; contains `cpython_socket.py`, `cpython_uart.py`, `micropython_socket.py`, `micropython_uart.py`, `__init__.py`. |
| `tests` | Code folder for `tests`; contains `test_bit_coalescer.py`, `test_protocol.py`, `test_runtime.py`. |

## Folder docs

| Path | Role |
| --- | --- |
| `src/inovonics_echostream_processor/README.md` | Folder-level summary for the code in that directory. |
| `src/inovonics_echostream_processor/transports/README.md` | Folder-level summary for the code in that directory. |
| `tests/README.md` | Folder-level summary for the code in that directory. |

<!-- CODEX-REPO-MAP END -->
