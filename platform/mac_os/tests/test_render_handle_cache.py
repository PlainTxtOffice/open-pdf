import threading

from pathlib import Path

import pymupdf

from open_pdf.gui.views.rendering.render_handle_cache import _RenderHandleCache


def _create_sample_pdf(path: Path) -> None:
    document = pymupdf.open()
    try:
        document.new_page()
        document.save(path)
    finally:
        document.close()


def test_acquire_reopens_same_path_when_render_revision_changes(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "cache.pdf"
    _create_sample_pdf(pdf_path)
    cache = _RenderHandleCache()

    first_handle = cache.acquire(pdf_path, 1)
    second_handle = cache.acquire(pdf_path, 1)
    third_handle = cache.acquire(pdf_path, 2)

    assert second_handle is first_handle
    assert third_handle is not first_handle

    cache.invalidate()


def test_close_all_closes_handle_and_forces_reopen_on_same_thread(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "close-all.pdf"
    _create_sample_pdf(pdf_path)
    cache = _RenderHandleCache()

    first_handle = cache.acquire(pdf_path, 1)

    cache.close_all()

    assert first_handle.is_closed

    second_handle = cache.acquire(pdf_path, 1)

    assert second_handle is not first_handle
    assert second_handle.is_closed is False
    assert second_handle.page_count == 1

    cache.invalidate()


def test_close_all_closes_handles_held_by_other_threads(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "close-all-threads.pdf"
    _create_sample_pdf(pdf_path)
    cache = _RenderHandleCache()
    worker_handles: dict[str, pymupdf.Document] = {}

    def _acquire_in_worker() -> None:
        worker_handles["handle"] = cache.acquire(pdf_path, 1)

    worker = threading.Thread(target=_acquire_in_worker)
    worker.start()
    worker.join()

    cache.close_all()

    assert worker_handles["handle"].is_closed
