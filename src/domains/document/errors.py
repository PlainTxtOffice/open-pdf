"""Shared error classes raised by PDF load, render, and save operations."""

from __future__ import annotations

import pymupdf


class PasswordRequiredError(RuntimeError):
    """Raised when a PDF requires password before its contents are readable."""


class IncorrectPasswordError(PasswordRequiredError):
    """Raised when a provided PDF password does not unlock the document."""


#: Exceptions raised when a PDF cannot be opened, parsed, rendered, or written.
#: Caught uniformly so every PDF I/O site reports the same failure surface.
PDF_IO_ERRORS = (
    RuntimeError,
    ValueError,
    OSError,
    pymupdf.FileDataError,
    PasswordRequiredError,
)
