"""IPC names isolate Linux users and graphical sessions."""

from open_pdf.adapters.runtime import desktop_session as session


def test_session_names_are_stable_and_isolated(monkeypatch):
    monkeypatch.setattr(session.os, "getuid", lambda: 1000, raising=False)
    monkeypatch.setenv("DISPLAY", ":0")
    name = session.instance_server_name()
    assert session.instance_server_name() == name
    monkeypatch.setenv("DISPLAY", ":1")
    assert session.instance_server_name() != name
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setattr(session.os, "getuid", lambda: 1001)
    assert session.instance_server_name() != name
