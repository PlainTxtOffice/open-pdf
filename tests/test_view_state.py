from src.domains.document.pages.view_state import (
    MAX_ZOOM,
    MIN_ZOOM,
    PdfViewState,
)


def test_page_navigation_stays_in_bounds() -> None:
    state = PdfViewState(page_count=3)

    state.set_page(10)
    assert state.current_page_index == 2

    state.next_page()
    assert state.current_page_index == 2

    state.previous_page()
    assert state.current_page_index == 1

    state.set_page(-1)
    assert state.current_page_index == 0


def test_zoom_stays_within_limits() -> None:
    state = PdfViewState()

    state.set_zoom(99)
    assert state.zoom == MAX_ZOOM

    state.set_zoom(0.01)
    assert state.zoom == MIN_ZOOM
