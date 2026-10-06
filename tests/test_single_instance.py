"""Focused tests for framed single-instance launch messages."""

from pathlib import Path

from src.adapters.runtime.single_instance import (
    SingleInstanceCoordinator,
    _encode_launch_message,
)


class _ReadResult:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def data(self) -> bytes:
        return self._payload


class _ChunkSocket:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = iter(chunks)
        self.aborted = False

    def readAll(self) -> _ReadResult:  # noqa: N802
        return _ReadResult(next(self._chunks))

    def abort(self) -> None:
        self.aborted = True


class _Window:
    def __init__(self) -> None:
        self.presented = False
        self.opened_path: Path | None = None

    def present(self) -> None:
        self.presented = True

    def open_document_in_tab(self, path: Path) -> None:
        self.opened_path = path


def test_coordinator_buffers_a_split_message() -> None:
    payload = _encode_launch_message(Path("split.pdf"))
    frame = len(payload).to_bytes(4, "big") + payload
    socket = _ChunkSocket([frame[:7], frame[7:]])
    window = _Window()
    coordinator = SingleInstanceCoordinator("split-message-test")
    coordinator._window = window
    coordinator._buffers[socket] = bytearray()

    coordinator._consume_connection(socket)
    assert window.presented is False

    coordinator._consume_connection(socket)
    assert window.presented is True
    assert window.opened_path == Path("split.pdf")
    assert socket.aborted is False
