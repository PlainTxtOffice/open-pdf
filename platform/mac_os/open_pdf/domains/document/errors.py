"""Describe document password failures without engine dependencies."""

from __future__ import annotations


class PasswordRequiredError(RuntimeError):
    """Raised when a PDF requires password before its contents are readable."""


class IncorrectPasswordError(PasswordRequiredError):
    """Raised when a provided PDF password does not unlock the document."""
