"""Tests for rectangle redaction."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from open_pdf.application.document import redaction


class _FakeDocument:
    """Minimal stand-in exposing only what redact_rectangles reads."""

    def __init__(self, page_count: int) -> None:
        self.page_count = page_count


class _RecordingApplier:
    """Record whether the redaction operation was reached."""

    def __init__(self) -> None:
        self.called = False

    def __call__(
        self,
        document: object,
        page_index: int,
        rectangles: Sequence[tuple[float, float, float, float]],
    ) -> bool:
        self.called = True
        return True


def test_out_of_range_page_index_raises() -> None:
    with pytest.raises(ValueError, match="out of range"):
        redaction.redact_rectangles(
            _FakeDocument(2),
            5,
            [(0, 0, 1, 1)],
            apply_redactions=_RecordingApplier(),
        )


def test_empty_rectangles_returns_false_without_invoking_adapter() -> None:
    applier = _RecordingApplier()

    result = redaction.redact_rectangles(
        _FakeDocument(2),
        0,
        [],
        apply_redactions=applier,
    )

    assert result is False
    assert applier.called is False


def test_non_empty_rectangles_delegate_to_the_applier() -> None:
    applier = _RecordingApplier()

    result = redaction.redact_rectangles(
        _FakeDocument(2),
        0,
        [(0, 0, 1, 1)],
        apply_redactions=applier,
    )

    assert result is True
    assert applier.called is True
