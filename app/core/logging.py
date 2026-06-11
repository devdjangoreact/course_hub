import logging
import sys

from loguru import logger

_SECRET_KEYS = ("token", "password", "secret", "api_key")


class InterceptHandler(logging.Handler):
    """Route standard-library logging (uvicorn, sqlalchemy) through Loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame.f_back is not None and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def redact(value: str) -> str:
    """Mask a value that may carry a secret, keeping only a short suffix."""
    if not value:
        return ""
    return f"***{value[-4:]}" if len(value) > 4 else "***"


def setup_logging(level: str = "INFO") -> None:
    logger.remove()
    logger.add(
        sys.stdout,
        level=level.upper(),
        backtrace=False,
        diagnose=False,
        enqueue=True,
    )
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(name).handlers = [InterceptHandler()]
