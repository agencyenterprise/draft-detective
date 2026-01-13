import logging
import sys


def setup_logger():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )

    # Suppress noisy OpenTelemetry errors for trace export failures
    # These don't affect the actual workflow execution, they're just telemetry issues
    logging.getLogger("opentelemetry.sdk._shared_internal").setLevel(logging.CRITICAL)
    logging.getLogger("opentelemetry.exporter.otlp").setLevel(logging.CRITICAL)
    logging.getLogger("opentelemetry.exporter.otlp.proto.http").setLevel(
        logging.CRITICAL
    )

    # Suppress noisy langchain text splitter warnings
    logging.getLogger("langchain_text_splitters.base").setLevel(logging.ERROR)

    # Suppress noisy logs from sqlalchemy
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
