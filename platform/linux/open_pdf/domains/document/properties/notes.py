"""Pure state for document notes."""


class NotesState:
    """Track current and saved document notes independently of storage."""

    def __init__(self) -> None:
        """Initialize with no stored notes."""
        self._notes_text = ""
        self._saved_notes_text = ""

    def text(self) -> str:
        """Return the current notes text."""
        return self._notes_text

    def update(self, text: str) -> bool:
        """Replace the notes text and report whether it changed."""
        if self._notes_text == text:
            return False

        self._notes_text = text
        return True

    def mark_saved(self) -> None:
        """Record the current text as the last text written to disk."""
        self._saved_notes_text = self._notes_text

    def load(self, text: str) -> None:
        """Adopt stored text as both current and saved notes."""
        self._notes_text = text
        self._saved_notes_text = text

    def is_saved(self) -> bool:
        """Return whether the current text matches the last saved text."""
        return self._notes_text == self._saved_notes_text
