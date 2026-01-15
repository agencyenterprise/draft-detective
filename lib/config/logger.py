import logging
import sys


class _MaxLevelFilter(logging.Filter):
    """Filter that only allows records below a certain level."""

    def __init__(self, max_level: int):
        super().__init__()
        self.max_level = max_level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno < self.max_level


def setup_logger():
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # INFO and below to stdout
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG)
    stdout_handler.addFilter(_MaxLevelFilter(logging.WARNING))
    stdout_handler.setFormatter(formatter)

    # WARNING and above to stderr
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(formatter)

    root_logger.addHandler(stdout_handler)
    root_logger.addHandler(stderr_handler)

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
