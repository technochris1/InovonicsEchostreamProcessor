from inovonics_echostream_processor.compat import (
    detect_runtime,
    is_cpython,
    is_micropython,
)
from inovonics_echostream_processor.core import (
    EchoStreamProcessorCore,
    ProcessBatch,
)
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
    ProcessorEvent,
    RepeaterResetEvent,
    SecurityMessageEvent,
    UnknownMessageEvent,
)
from inovonics_echostream_processor.protocol import EchoStreamProtocol
from inovonics_echostream_processor.version import __version__

__all__ = [
    "__version__",
    "AckEvent",
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
    "UnknownMessageEvent",
    "detect_runtime",
    "device_category_label",
    "device_model_label",
    "is_cpython",
    "is_micropython",
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
