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
