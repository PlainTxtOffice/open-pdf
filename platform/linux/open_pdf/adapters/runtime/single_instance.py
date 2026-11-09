"""Local-socket coordination for a single desktop application instance."""

from __future__ import annotations

import contextlib
import json
import logging
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from PySide6.QtCore import QObject
from PySide6.QtNetwork import QLocalServer, QLocalSocket

if TYPE_CHECKING:
    from collections.abc import Mapping


logger = logging.getLogger(__name__)
_HEADER_SIZE = 4
_MAX_MESSAGE_SIZE = 1024 * 1024


class SingleInstanceServerStartError(RuntimeError):
    """Raised when the primary-instance local server cannot be started."""

    def __init__(self, server_error: str) -> None:
        """Store the local-server startup failure details."""
        super().__init__(
            f"Could not start the single-instance server: {server_error}",
        )


class InstanceWindow(Protocol):
    """Window operations used by forwarded launch requests."""

    def present(self) -> None: ...  # noqa: D102

    def open_document_in_tab(self, path: Path) -> None: ...  # noqa: D102


class SingleInstanceCoordinator(QObject):
    """Own the primary endpoint and forward launches from later processes."""

    def __init__(self, server_name: str) -> None:
        """Initialize the coordinator for a specific local server name."""
        super().__init__()
        self._server_name = server_name
        self._server: QLocalServer | None = None
        self._window: InstanceWindow | None = None
        self._connections: set[QLocalSocket] = set()
        self._buffers: dict[QLocalSocket, bytearray] = {}

    def notify_existing_instance(self, pdf_path: Path | None) -> bool:
        """Forward a length-delimited launch request when a primary exists."""
        socket = QLocalSocket(self)
        socket.connectToServer(self._server_name)
        if not socket.waitForConnected(200):
            socket.abort()
            return False

        payload = _encode_launch_message(pdf_path)
        frame = len(payload).to_bytes(_HEADER_SIZE, "big") + payload
        socket.write(frame)
        socket.flush()
        socket.waitForBytesWritten(200)
        socket.disconnectFromServer()
        socket.waitForDisconnected(200)
        socket.close()
        return True

    def start_listening(self, window: InstanceWindow) -> None:
        """Claim the endpoint for the primary process."""
        server = QLocalServer(self)
        server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        if not server.listen(self._server_name):
            QLocalServer.removeServer(self._server_name)
            if not server.listen(self._server_name):
                raise SingleInstanceServerStartError(server.errorString())

        self._server = server
        self._window = window
        server.newConnection.connect(self._handle_new_connection)

    def close(self) -> None:
        """Release the endpoint on shutdown."""
        if self._server is not None:
            self._server.close()
            QLocalServer.removeServer(self._server_name)
            self._server = None

    def _handle_new_connection(self) -> None:
        server = self._server
        if server is None:
            return

        while server.hasPendingConnections():
            socket = server.nextPendingConnection()
            if socket is None:
                return
            self._connections.add(socket)
            self._buffers[socket] = bytearray()
            socket.readyRead.connect(partial(self._consume_connection, socket))
            socket.disconnected.connect(
                partial(self._finalize_connection, socket),
            )

    def _consume_connection(self, socket: QLocalSocket) -> None:
        buffer = self._buffers.get(socket)
        if buffer is None:
            return
        buffer.extend(bytes(socket.readAll().data()))

        while len(buffer) >= _HEADER_SIZE:
            payload_size = int.from_bytes(buffer[:_HEADER_SIZE], "big")
            if payload_size > _MAX_MESSAGE_SIZE:
                logger.error("Discarded oversized launch message")
                socket.abort()
                return
            frame_size = _HEADER_SIZE + payload_size
            if len(buffer) < frame_size:
                return
            payload = bytes(buffer[_HEADER_SIZE:frame_size])
            del buffer[:frame_size]
            self._handle_launch_message(payload)

    def _finalize_connection(self, socket: QLocalSocket) -> None:
        self._connections.discard(socket)
        self._buffers.pop(socket, None)
        with contextlib.suppress(RuntimeError):
            socket.close()

    def _handle_launch_message(self, payload: bytes) -> None:
        window = self._window
        if window is None:
            return

        message = _decode_launch_message(payload)
        if message is None:
            return
        window.present()
        raw_path = message.get("pdf_path")
        if isinstance(raw_path, str) and raw_path:
            window.open_document_in_tab(Path(raw_path))


def _encode_launch_message(pdf_path: Path | None) -> bytes:
    return json.dumps(
        {"pdf_path": str(pdf_path.resolve()) if pdf_path is not None else None},
    ).encode("utf-8")


def _decode_launch_message(payload: bytes) -> Mapping[str, object] | None:
    try:
        message = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        logger.exception("Discarded malformed launch message")
        return None
    return message if isinstance(message, dict) else None
