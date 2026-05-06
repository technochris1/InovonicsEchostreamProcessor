from inovonics_echostream_processor import detect_runtime, is_cpython, is_micropython
from inovonics_echostream_processor.transports.cpython_uart import (
    CpythonUartProcessorConfig,
)
from inovonics_echostream_processor.transports.micropython_socket import (
    MicroPythonSocketProcessorConfig,
)


def test_runtime_detection_returns_a_name() -> None:
    runtime = detect_runtime()

    assert isinstance(runtime, str)
    assert runtime
    assert is_cpython() is True
    assert is_micropython() is False
    assert CpythonUartProcessorConfig(port="COM1", baudrate=9600).port == "COM1"
    assert MicroPythonSocketProcessorConfig(host="127.0.0.1", port=10001).port == 10001
