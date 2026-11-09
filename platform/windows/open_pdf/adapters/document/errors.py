"""Collect exceptions raised at PDF integration boundaries."""

import pymupdf

from open_pdf.domains.document.errors import PasswordRequiredError

#: Exceptions raised when a PDF cannot be opened, parsed, rendered, or written.
#: Caught uniformly so every PDF I/O site reports the same failure surface.
PDF_IO_ERRORS = (
    RuntimeError,
    ValueError,
    OSError,
    pymupdf.FileDataError,
    PasswordRequiredError,
)
