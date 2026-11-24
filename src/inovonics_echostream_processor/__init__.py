from inovonics_echostream_processor.compat import (
    detect_runtime,
    is_cpython,
    is_micropython,
)
from inovonics_echostream_processor.bit_coalescer import (
    BitStateCoalescer,
    BitStateCoalescerConfig,
    BitStateUpdate,
    security_event_to_bit_state_updates,
    security_event_to_supported_bit_state_updates,
)
from inovonics_echostream_processor.core import (
    EchoStreamProcessorCore,
    ProcessBatch,
)
from inovonics_echostream_processor.device_types import (
    security_status_bit_definition,
    security_status_capabilities,
    decode_icn3000_7,
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
    ProcessorEvent,
    RepeaterResetEvent,
    SecurityMessageEvent,
    SerialDataEvent,
    UnknownMessageEvent,
)
from inovonics_echostream_processor.protocol import EchoStreamProtocol
from inovonics_echostream_processor.version import __version__

__all__ = [
    "__version__",
    "AckEvent",
    "AggregateMessageEvent",
    "ConfigurationReportEvent",
    "BitStateCoalescer",
    "BitStateCoalescerConfig",
    "BitStateUpdate",
    "CoordinatorNetworkIdEvent",
    "CoordinatorSerialNumberEvent",
    "CoordinatorStatusEvent",
    "EchoStreamProcessorCore",
    "EchoStreamProtocol",
    "NakEvent",
    "NetworkStatusEvent",
    "ProcessBatch",
    "ProcessorEvent",
    "RepeaterResetEvent",
    "SecurityMessageEvent",
    "SerialDataEvent",
    "UnknownMessageEvent",
    "decode_icn3000_7",
    "detect_runtime",
    "device_category_label",
    "device_model_label",
    "is_cpython",
    "is_micropython",
    "security_event_to_bit_state_updates",
    "security_event_to_supported_bit_state_updates",
    "security_status_bit_definition",
    "security_status_capabilities",
]

if is_cpython():
    from inovonics_echostream_processor.transports.cpython_socket import (
        ProcessorMetrics,
        SocketProcessorConfig,
        SocketProcessorService,
    )
    from inovonics_echostream_processor.transports.cpython_uart import (
        CpythonUartProcessorConfig,
        CpythonUartProcessorService,
    )

    __all__.extend(
        [
            "CpythonUartProcessorConfig",
            "CpythonUartProcessorService",
            "ProcessorMetrics",
            "SocketProcessorConfig",
            "SocketProcessorService",
        ]
    )

if is_micropython():
    from inovonics_echostream_processor.transports.micropython_socket import (
        MicroPythonSocketProcessor,
        MicroPythonSocketProcessorConfig,
    )
    from inovonics_echostream_processor.transports.micropython_uart import (
        MicroPythonUartProcessor,
        MicroPythonUartProcessorConfig,
    )

    __all__.extend(
        [
            "MicroPythonSocketProcessor",
            "MicroPythonSocketProcessorConfig",
            "MicroPythonUartProcessor",
            "MicroPythonUartProcessorConfig",
        ]
    )
