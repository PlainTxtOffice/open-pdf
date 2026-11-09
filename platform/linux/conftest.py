"""Keep GUI tests and all desktop state inside disposable test storage."""

import os
import tempfile
from pathlib import Path

import pytest

_state = tempfile.TemporaryDirectory(prefix="open-pdf-linux-tests-")
for _name in ("CONFIG", "CACHE", "STATE"):
    os.environ[f"XDG_{_name}_HOME"] = str(Path(_state.name) / _name.lower())
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def isolated_keyring(monkeypatch, request):
    """Regression tests never access the developer's desktop credentials."""
    if request.node.get_closest_marker("secret_service"):
        return
    from open_pdf.adapters.persistence import passwords

    entries = {}

    class TestKeyring:
        priority = 1

        def set_password(self, service, key, password):
            entries[service, key] = password

        def get_password(self, service, key):
            return entries.get((service, key))

        def delete_password(self, service, key):
            entries.pop((service, key), None)

    monkeypatch.setattr(passwords, "Keyring", TestKeyring)
