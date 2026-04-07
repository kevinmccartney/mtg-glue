"""One-time Loguru setup: human console (default) or JSON lines for structured logs."""

from __future__ import annotations

import os
import sys
from contextvars import ContextVar
from typing import TYPE_CHECKING, Final

from loguru import logger

if TYPE_CHECKING:
    from loguru import Record

_LOG_LEVELS: Final[frozenset[str]] = frozenset(
    ("TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL")
)

_workload_ctx: ContextVar[str | None] = ContextVar("workload", default=None)


def set_workload(name: str | None) -> None:
    """Set the current workload label for this task/context (thread-local).

    Injected into every log record as ``extra["workload"]`` (``null`` when unset).
    Console lines render as ``[{workload}] {message}`` when workload is set.
    """
    _workload_ctx.set(name)


def get_workload() -> str | None:
    """Return the workload label for the current context, if any."""
    return _workload_ctx.get()


def _workload_patcher(record: Record) -> None:
    record["extra"]["workload"] = _workload_ctx.get()


def _format_console(record: Record) -> str:
    w = record["extra"].get("workload")
    msg = record["message"]
    if w is None:
        body = msg
    elif msg == w:
        body = f"[{w}]"
    else:
        body = f"[{w}] {msg}"
    time_s = record["time"].strftime("%Y-%m-%d %H:%M:%S")
    level = f"{record['level'].name:<8}"
    return (
        f"<green>{time_s}</green> | "
        f"<level>{level}</level> | "
        f"<level>{body}</level>\n"
    )


# Mutable singleton: avoids ``global`` and pylint's too-few-public-methods on a class.
_CONFIGURED: list[bool] = [False]


def configure_logging() -> None:
    """Configure stderr logging once. Idempotent.

    Environment:
        LOG_FORMAT: ``console`` (default) or ``json`` (one JSON object per line).
        LOG_LEVEL: Loguru level name (default ``INFO``).
    """
    if _CONFIGURED[0]:
        return

    raw_level = os.environ.get("LOG_LEVEL", "INFO").strip().upper()
    level = raw_level if raw_level in _LOG_LEVELS else "INFO"
    fmt = os.environ.get("LOG_FORMAT", "console").strip().lower()

    logger.remove()
    logger.configure(patcher=_workload_patcher)

    if fmt == "json":
        logger.add(
            sys.stderr,
            level=level,
            serialize=True,
            backtrace=False,
            diagnose=False,
        )
    else:
        logger.add(
            sys.stderr,
            level=level,
            format=_format_console,
            colorize=True,
        )

    _CONFIGURED[0] = True
