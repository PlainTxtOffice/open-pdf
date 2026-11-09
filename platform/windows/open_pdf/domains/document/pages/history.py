"""Position-aware navigation history for the active PDF document."""

from __future__ import annotations

from dataclasses import dataclass

# Firefox-style cap: deep enough to be useful, bounded for memory.
HISTORY_LIMIT = 50


@dataclass(frozen=True)
class ScrollState:
    """One visited spot, in zoom- and rotation-independent PDF units.

    - `x_pdf` and `y_pdf` are per-axis: None means "this axis was not
      recorded", which callers restore by leaving that scrollbar alone.
    """

    page_index: int
    x_pdf: float | None = None
    y_pdf: float | None = None


class PageHistory:
    """Track visited scroll states with back/forward navigation."""

    def __init__(self) -> None:
        """Initialize an empty history."""
        self._entries: list[ScrollState] = []
        self._position = -1

    def reset(self) -> None:
        """Drop all recorded history entries."""
        self._entries = []
        self._position = -1

    def push(self, state: ScrollState) -> None:
        """Record a visit to `state`.

        - Truncates any forward entries past the current position.
        - Skips recording when the new entry matches the current entry.
        """
        if 0 <= self._position < len(self._entries):
            if self._entries[self._position] == state:
                return
            self._entries = self._entries[: self._position + 1]

        self._entries.append(state)
        if len(self._entries) > HISTORY_LIMIT:
            self._entries = self._entries[-HISTORY_LIMIT:]
        self._position = len(self._entries) - 1

    def rewrite_current(self, state: ScrollState) -> None:
        """Replace the current slot with where the reader actually is.

        - Call this before navigating so that leaving a spot and coming
          back returns to it, rather than to where the slot was recorded.
        """
        if 0 <= self._position < len(self._entries):
            self._entries[self._position] = state

    def can_go_back(self) -> bool:
        """Return whether a back-history entry is available."""
        return self._position > 0

    def can_go_forward(self) -> bool:
        """Return whether a forward-history entry is available."""
        return 0 <= self._position < len(self._entries) - 1

    def go_back(self) -> ScrollState | None:
        """Return the previous scroll state, or None when unavailable."""
        if not self.can_go_back():
            return None

        self._position -= 1
        return self._entries[self._position]

    def go_forward(self) -> ScrollState | None:
        """Return the next scroll state, or None when unavailable."""
        if not self.can_go_forward():
            return None

        self._position += 1
        return self._entries[self._position]
