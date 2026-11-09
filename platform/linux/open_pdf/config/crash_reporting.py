"""Process-wide handling for otherwise unhandled exceptions."""

from __future__ import annotations

import logging
import sys
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path
    from types import TracebackType

logger = logging.getLogger(__name__)

type CrashNotifier = Callable[[str], None]

_PASS_THROUGH_ERRORS = (KeyboardInterrupt, SystemExit)

_original_excepthook = sys.excepthook
_original_thread_excepthook = threading.excepthook
_notify: CrashNotifier | None = None
_log_path: Path | None = None
_installed = False
_reporting = False


def crash_message(error: BaseException, log_path: Path | None) -> str:
    """Return the user-facing text describing one unhandled exception.

    - Names the error type so a bug report can be triaged without the log.
    - Points at the log file only when logging writes to a known path.
    """
    lines = [
        (
            "Open PDF hit an unexpected error and may now be in an "
            "inconsistent state."
        ),
        "",
        f"{type(error).__name__}: {error}",
        "",
        "Save your work to a new file, then restart the application.",
    ]
    if log_path is not None:
        lines.extend(["", f"Details were written to:\n{log_path}"])
    return "\n".join(lines)


def _report(error: BaseException) -> None:
    """Log one unhandled exception and notify the user about it.

    - Reentrant reports are logged but not shown, so a failing notifier
      cannot recurse into itself.
    - Notifier failures never escape; the log entry is the durable record.
    """
    global _reporting  # noqa: PLW0603

    logger.critical(
        "Unhandled exception",
        exc_info=(type(error), error, error.__traceback__),
    )
    if _notify is None or _reporting:
        return

    _reporting = True
    try:
        _notify(crash_message(error, _log_path))
    except Exception:
        logger.exception("Could not report an unhandled exception")
    finally:
        _reporting = False


def _handle_exception(
    error_type: type[BaseException],
    error: BaseException,
    traceback: TracebackType | None,
) -> None:
    """Route one unhandled main-thread exception to the crash report."""
    if issubclass(error_type, _PASS_THROUGH_ERRORS):
        _original_excepthook(error_type, error, traceback)
        return
    _report(error)


def _handle_thread_exception(
    args: threading.ExceptHookArgs,
) -> None:
    """Route one unhandled worker-thread exception to the crash report."""
    error = args.exc_value
    if error is None or issubclass(args.exc_type, _PASS_THROUGH_ERRORS):
        _original_thread_excepthook(args)
        return
    _report(error)


def install_crash_handlers(
    *,
    notify: CrashNotifier | None = None,
    log_path: Path | None = None,
) -> None:
    """Route unhandled exceptions on any thread to the log and the user.

    - Qt swallows exceptions raised inside slots and background runnables,
      so without this hook the application keeps running with no record of
      the failure and no console in a packaged build.
    - Safe to call more than once; later calls replace the notifier and log
      path while keeping the interpreter's original hooks for delegation.
    - `notify` is called from the thread that raised, so a GUI notifier is
      responsible for marshalling the message onto the GUI thread.
    - `KeyboardInterrupt` and `SystemExit` keep their default behavior.
    """
    global _installed, _log_path, _notify  # noqa: PLW0603

    _notify = notify
    _log_path = log_path
    if _installed:
        return

    sys.excepthook = _handle_exception
    threading.excepthook = _handle_thread_exception
    _installed = True
