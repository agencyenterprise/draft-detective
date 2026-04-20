"""Logging configuration for the application.

Provides centralized logging setup with support for rich console output
or simple stdout/stderr handlers based on environment configuration.
Always writes logs to daily rotating files under FILE_UPLOADS_MOUNT_PATH/logs.
"""

import logging
import logging.handlers
import sys
import warnings
from pathlib import Path

from rich.logging import RichHandler

from lib.config.env import config as env_config

logger = logging.getLogger(__name__)


class _MaxLevelFilter(logging.Filter):
    """Filter that only allows records below a certain level."""

    def __init__(self, max_level: int):
        super().__init__()
        self.max_level = max_level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno < self.max_level


def setup_logger() -> None:
    """Configure the root logger with appropriate handlers and filters.

    Sets up logging based on the LOG_RICH_HANDLER environment configuration:
    - If enabled, uses RichHandler for colorized console output with tracebacks
    - If disabled, uses simple stdout/stderr handlers with standard formatting

    Also suppresses noisy logs from OpenTelemetry, LangChain, and SQLAlchemy.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    if env_config.LOG_RICH_HANDLER:
        _attach_rich_handler(root_logger)
        logger.info("Using rich handler for logging")
    else:
        _attach_simple_stdout_stderr_handlers(root_logger)
        logger.info("Using simple stdout/stderr handlers for logging")

    _attach_file_handler(root_logger)
    logger.info(
        "File logging enabled, writing to %s/logs",
        env_config.FILE_UPLOADS_MOUNT_PATH,
    )

    # Suppress Pydantic serialization warnings for workflow_type enum mismatches
    # (old workflow types stored in DB that no longer match the current enum)
    warnings.filterwarnings("ignore", message="Pydantic serializer warnings")

    # Suppress noisy OpenTelemetry errors for trace export failures
    # These don't affect the actual workflow execution, they're just telemetry issues
    logging.getLogger("opentelemetry.sdk._shared_internal").setLevel(logging.CRITICAL)
    logging.getLogger("opentelemetry.exporter.otlp").setLevel(logging.CRITICAL)
    logging.getLogger("opentelemetry.exporter.otlp.proto.http").setLevel(
        logging.CRITICAL
    )

    # Debug fastmcp context to client logging
    logging.getLogger(name="fastmcp.server.context.to_client").setLevel(logging.DEBUG)

    # Suppress noisy langchain text splitter warnings
    logging.getLogger("langchain_text_splitters.base").setLevel(logging.ERROR)

    # Suppress noisy logs from sqlalchemy
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def _attach_rich_handler(logger: logging.Logger) -> None:
    """Attach a RichHandler to the logger for colorized console output.

    Args:
        logger: The logger instance to attach the handler to.
    """
    rich_handler = RichHandler(
        rich_tracebacks=True,
        show_time=True,
        show_path=True,
        log_time_format="%d/%m %H:%M:%S",
    )
    logger.addHandler(rich_handler)


def _attach_simple_stdout_stderr_handlers(logger: logging.Logger) -> None:
    """Attach stdout and stderr handlers to the logger.

    Configures logging to send INFO/DEBUG messages to stdout and
    WARNING/ERROR/CRITICAL messages to stderr.

    Args:
        logger: The logger instance to attach the handlers to.
    """
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG)
    stdout_handler.addFilter(_MaxLevelFilter(logging.WARNING))
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(formatter)
    logger.addHandler(stderr_handler)


def _attach_file_handler(logger: logging.Logger) -> None:
    """Attach a daily-rotating file handler to the logger.

    Creates a TimedRotatingFileHandler that rotates at midnight, keeping
    90 days of log files. The log directory is created if it does not exist.

    Args:
        logger: The logger instance to attach the handler to.
    """
    log_dir = Path(env_config.FILE_UPLOADS_MOUNT_PATH) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "app.log"
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=str(log_file),
        when="midnight",
        backupCount=90,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(file_handler)
