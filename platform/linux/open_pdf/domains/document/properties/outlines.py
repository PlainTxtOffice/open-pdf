"""Pure outline normalization helpers for PDF-domain data."""


def normalize_outline_page_index(
    *,
    page_value: object,
    destination: object,
) -> int | None:
    """Normalize an outline target into a zero-based page index."""
    if isinstance(page_value, int) and page_value > 0:
        return page_value - 1

    if isinstance(destination, dict):
        target_page = destination.get("page")
        if isinstance(target_page, int) and target_page >= 0:
            return target_page

    return None


def validate_bookmark_title(title: str) -> str:
    """Return the stripped bookmark title.

    Raises:
        ValueError: The title is empty or whitespace only.

    """
    bookmark_title = title.strip()
    if not bookmark_title:
        msg = "Bookmark titles cannot be empty."
        raise ValueError(msg)

    return bookmark_title


def validate_outline_index(toc_index: int, *, entry_count: int) -> int:
    """Return the outline index after bounds checking.

    Raises:
        ValueError: The index is outside the outline.

    """
    if not 0 <= toc_index < entry_count:
        msg = f"Bookmark index {toc_index} is out of range."
        raise ValueError(msg)

    return toc_index
