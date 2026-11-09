"""Shared layout metrics for the scrollable document page surface."""

from __future__ import annotations

#: Total horizontal/vertical pixels a page label adds around its rendered
#: pixmap (1px border + 4px padding per side from the page border stylesheet).
#: Page sizing, fit-zoom math, and the text-overlay inset must all agree on
#: this value, so it lives in one place.
PAGE_CONTENT_CHROME = 10
