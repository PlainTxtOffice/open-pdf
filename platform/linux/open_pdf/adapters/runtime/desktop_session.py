"""Name the IPC endpoint for the current user and graphical session."""

import hashlib
import os


def instance_server_name() -> str:
    """Keep separate users and X11/Wayland sessions from sharing a socket."""
    identity = "\0".join((
        str(os.getuid()),
        os.environ.get("XDG_SESSION_ID", ""),
        os.environ.get("WAYLAND_DISPLAY", ""),
        os.environ.get("DISPLAY", ""),
    ))
    suffix = hashlib.sha256(identity.encode()).hexdigest()[:24]
    return f"open-pdf-{suffix}"
