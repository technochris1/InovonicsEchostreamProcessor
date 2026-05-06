from __future__ import annotations

import argparse
import json
import logging
import time
from dataclasses import asdict, is_dataclass

from inovonics_echostream_processor.client import (
    EchoStreamProcessor,
    EchoStreamProcessorConfig,
)
from inovonics_echostream_processor.events import ProcessorEvent


def _event_to_dict(event: ProcessorEvent) -> dict[str, object]:
    payload = asdict(event) if is_dataclass(event) else {}
    payload["event_type"] = event.event_type
    payload["raw_hex"] = event.raw_hex
    return payload


def main() -> int:
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

    processor = EchoStreamProcessor(
        EchoStreamProcessorConfig(host=args.host, port=args.port),
    )
    processor.add_event_handler(
        lambda event: print(json.dumps(_event_to_dict(event), default=str))
    )
    processor.start()

    try:
        while processor.is_running:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Interrupted by user.")
    finally:
        processor.stop()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
