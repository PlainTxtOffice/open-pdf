"""Keep native GUI diagnostics visible when the smoke subprocess fails."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def smoke_module():
    script = Path(__file__).resolve().parents[1] / "scripts/smoke_test.py"
    spec = importlib.util.spec_from_file_location("linux_smoke", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_failure_prints_child_diagnostics(smoke_module, capsys):
    command = [sys.executable, "-c", (
        "import sys; print('startup output', flush=True); "
        "print('native GUI failure', file=sys.stderr); sys.exit(7)"
    )]
    with pytest.raises(subprocess.CalledProcessError) as caught:
        smoke_module.smoke_test(command)
    assert caught.value.returncode == 7
    output = capsys.readouterr().out
    assert "startup output" in output
    assert "native GUI failure" in output


def test_success_requires_render_confirmation(smoke_module, capsys):
    smoke_module.smoke_test([
        sys.executable, "-c", "print('OPEN_PDF_SMOKE_OK')",
    ])
    assert "OPEN_PDF_SMOKE_OK" in capsys.readouterr().out


def test_zero_exit_without_render_fails(smoke_module, capsys):
    with pytest.raises(RuntimeError, match="did not confirm rendering"):
        smoke_module.smoke_test([
            sys.executable, "-c", "print('exited before rendering')",
        ])
    assert "exited before rendering" in capsys.readouterr().out


def test_timeout_prints_partial_output(smoke_module, monkeypatch, capsys):
    def timeout(command, **kwargs):
        raise subprocess.TimeoutExpired(command, 60, output=b"GUI stalled\n")

    monkeypatch.setattr(smoke_module.subprocess, "run", timeout)
    with pytest.raises(subprocess.TimeoutExpired):
        smoke_module.smoke_test(["unused"])
    assert "GUI stalled" in capsys.readouterr().out
