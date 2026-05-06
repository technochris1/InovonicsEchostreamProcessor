from inovonics_echostream_processor.compat import is_micropython
from inovonics_echostream_processor.core import EchoStreamProcessorCore, ProcessBatch


class MicroPythonUartProcessorConfig(object):
    def __init__(
        self,
        uart_id,
        baudrate,
        tx=None,
        rx=None,
        timeout=100,
    ):
        self.uart_id = uart_id
        self.baudrate = baudrate
        self.tx = tx
        self.rx = rx
        self.timeout = timeout


class MicroPythonUartProcessor(object):
    def __init__(self, config, core=None, uart=None):
        if not is_micropython():
            raise RuntimeError("MicroPython UART transport can only run on MicroPython.")

        self.config = config
        self.core = core or EchoStreamProcessorCore()
        self._uart = uart or self._build_uart()

    def add_event_handler(self, handler):
        self.core.add_event_handler(handler)

    def poll_once(self):
        data = self._uart.read()
        if not data:
            return ProcessBatch()

        batch = self.core.feed(data)
        for command in batch.outbound_commands:
            self.send_command(command)
        return batch

    def send_command(self, command):
        self._uart.write(command)

    def _build_uart(self):
        import machine

        kwargs = {
            "baudrate": self.config.baudrate,
            "timeout": self.config.timeout,
        }
        if self.config.tx is not None:
            kwargs["tx"] = self.config.tx
        if self.config.rx is not None:
            kwargs["rx"] = self.config.rx
        return machine.UART(self.config.uart_id, **kwargs)
