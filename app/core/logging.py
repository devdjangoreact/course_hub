import logging
import os
import sys
from pathlib import Path

from loguru import logger

_SECRET_KEYS = ("token", "password", "secret", "api_key")
_REPO_ROOT = Path(__file__).resolve().parents[2]


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


def _log_dir() -> Path:
    if os.environ.get("VERCEL") == "1":
        return Path("/tmp/course_hub_logs")
    return _REPO_ROOT / "logs"


def setup_logging(level: str = "INFO") -> None:
    on_vercel = os.environ.get("VERCEL") == "1"
    logger.remove()
    if on_vercel:
        try:
            sys.stdout.reconfigure(line_buffering=True)
        except (AttributeError, OSError):
            pass
        # Vercel Observability only captures stdout/stderr, not /tmp files.
        logger.add(
            sys.stdout,
            level=level.upper(),
            backtrace=True,
            diagnose=False,
            enqueue=False,
        )
        _attach_stdlib()
        logger.info("vercel logging to stdout")
        return
    log_dir = _log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_dir / "app.log",
        level=level.upper(),
        backtrace=False,
        diagnose=False,
        enqueue=False,
        rotation="10 MB",
        retention=5,
        encoding="utf-8",
    )
    logger.add(
        log_dir / "error.log",
        level="ERROR",
        backtrace=True,
        diagnose=False,
        enqueue=False,
        rotation="10 MB",
        retention=10,
        encoding="utf-8",
    )
    _attach_stdlib()
    logger.info("file logging dir={}", log_dir)


def _attach_stdlib() -> None:
    intercept = InterceptHandler()
    logging.basicConfig(handlers=[intercept], level=0, force=True)
    for name in (
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "sqlalchemy.engine",
        "aiogram",
        "fastapi",
        "asyncio",
    ):
        std = logging.getLogger(name)
        std.handlers = [intercept]
        std.propagate = False
    sys.excepthook = _log_excepthook


def _log_excepthook(exc_type: type[BaseException], exc: BaseException, tb: object) -> None:
    logger.opt(exception=(exc_type, exc, tb)).error("unhandled exception")
