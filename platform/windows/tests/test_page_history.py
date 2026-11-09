"""Tests for position-aware navigation history."""

from __future__ import annotations

from open_pdf.domains.document.pages.history import (
    HISTORY_LIMIT,
    PageHistory,
    ScrollState,
)


def test_go_back_restores_the_position_not_just_the_page() -> None:
    history = PageHistory()
    history.push(ScrollState(page_index=0, x_pdf=12.0, y_pdf=340.0))
    history.push(ScrollState(page_index=4, x_pdf=0.0, y_pdf=0.0))

    assert history.go_back() == ScrollState(
        page_index=0,
        x_pdf=12.0,
        y_pdf=340.0,
    )


def test_pushing_the_same_state_twice_records_one_entry() -> None:
    history = PageHistory()
    state = ScrollState(page_index=2, x_pdf=0.0, y_pdf=100.0)
    history.push(state)
    history.push(state)

    assert history.can_go_back() is False


def test_rewriting_the_current_slot_returns_you_where_you_scrolled_to() -> None:
    history = PageHistory()
    history.push(ScrollState(page_index=0, x_pdf=0.0, y_pdf=0.0))
    history.push(ScrollState(page_index=7, x_pdf=0.0, y_pdf=0.0))

    # The reader scrolled down page 7 before navigating away.
    history.rewrite_current(ScrollState(page_index=7, x_pdf=0.0, y_pdf=500.0))
    history.go_back()

    assert history.go_forward() == ScrollState(
        page_index=7,
        x_pdf=0.0,
        y_pdf=500.0,
    )


def test_history_is_capped_and_drops_the_oldest_entry() -> None:
    history = PageHistory()
    for page_index in range(HISTORY_LIMIT + 10):
        history.push(ScrollState(page_index=page_index))

    while history.can_go_back():
        oldest = history.go_back()

    assert oldest == ScrollState(page_index=10)


def test_pushing_after_going_back_drops_the_forward_entries() -> None:
    history = PageHistory()
    history.push(ScrollState(page_index=0))
    history.push(ScrollState(page_index=1))
    history.push(ScrollState(page_index=2))
    history.go_back()

    history.push(ScrollState(page_index=9))

    assert history.can_go_forward() is False
