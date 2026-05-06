from inovonics_echostream_processor.compat import is_cpython, is_micropython

__all__ = [
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
