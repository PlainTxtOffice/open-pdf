"""Protect viewport boundaries and distinct render/retention margins."""

from types import SimpleNamespace

import pytest

from open_pdf.gui.views.rendering.page_geometry import PageGeometryMixin
from open_pdf.gui.views.rendering.page_render_cache import PageRenderCacheMixin


class _Viewport(PageGeometryMixin, PageRenderCacheMixin):
    def __init__(self, pages, top=0, height=100):
        self._visible_page_indexes = pages
        self._page_labels = [object() for _ in pages]
        self._page_top_offsets = [index * 110 for index in range(len(pages))]
        self._page_bottom_offsets = [top + 100 for top in self._page_top_offsets]
        self._document_scroll_area = SimpleNamespace(
            verticalScrollBar=lambda: SimpleNamespace(value=lambda: top),
            viewport=lambda: SimpleNamespace(height=lambda: height),
        )


@pytest.mark.parametrize(
    "top,height,labels,pages",
    [
        (0, 100, (0, 0), (2, 2)),
        (100, 10, (0, 1), (2, 5)),
        (101, 8, (1, 1), (5, 5)),
        (110, 100, (1, 1), (5, 5)),
        (220, 100, (2, 2), (9, 9)),
        (500, 100, (2, 2), (9, 9)),
    ],
)
def test_visible_ranges_map_labels_to_pages(top, height, labels, pages):
    viewport = _Viewport([2, 5, 9], top, height)
    assert viewport._visible_label_range() == labels
    assert viewport._visible_page_range() == pages


@pytest.mark.parametrize("pages", [[], [7]])
def test_unavailable_geometry_returns_zero_ranges(pages):
    viewport = _Viewport(pages)
    viewport._page_top_offsets = []
    assert viewport._visible_label_range() == (0, 0)
    assert viewport._visible_page_range() == (0, 0)


@pytest.mark.parametrize(
    "pages,top,rendered,retained",
    [
        ([], 0, (), ()),
        ([7], 0, (7,), (7,)),
        (list(range(10, 20)), 440, (13, 14, 15), tuple(range(11, 18))),
        (list(range(10, 20)), 0, (10, 11), (10, 11, 12, 13)),
        (list(range(10, 20)), 990, (18, 19), (16, 17, 18, 19)),
    ],
)
def test_render_and_retention_keep_distinct_margins(pages, top, rendered, retained):
    viewport = _Viewport(pages, top)
    assert viewport._pages_to_render() == rendered
    assert viewport._pages_to_keep_cached() == retained
