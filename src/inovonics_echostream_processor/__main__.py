import argparse
import json
import logging
import time

from inovonics_echostream_processor.compat import is_cpython


def main():
    if not is_cpython():
        raise SystemExit("The bundled CLI is only available on standard Python.")

    from inovonics_echostream_processor.transports.cpython_socket import (
        SocketProcessorConfig,
        SocketProcessorService,
    )

    parser = argparse.ArgumentParser(description="Dump normalized EchoStream events.")
    parser.add_argument("--host", required=True, help="EchoStream TCP host")
    parser.add_argument("--port", type=int, required=True, help="EchoStream TCP port")
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Python logging level",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    service = SocketProcessorService(
        SocketProcessorConfig(host=args.host, port=args.port),
    )
    service.add_event_handler(
        lambda event: print(json.dumps(event.to_dict(), default=str))
    )
    service.start()

    try:
        while service.is_running:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Interrupted by user.")
    finally:
        service.stop()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
