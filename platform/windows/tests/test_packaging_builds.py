"""Check build variants, preflights, and privacy at the compiler boundary."""

import pytest

from packaging_support import POWERSHELL, arguments, make_project, run_script

pytestmark = pytest.mark.skipif(not POWERSHELL, reason="PowerShell 7 is required")


@pytest.mark.parametrize("variant", ["onefile", "standalone", "standalone-debug"])
@pytest.mark.parametrize("commercial", ["", "yes"])
def test_build_variant_flags(tmp_path, variant, commercial):
    project, shim = make_project(tmp_path)
    result = run_script(project, shim, variant + ".ps1", "-Compiler", "msvc",
                        TEST_COMMERCIAL=commercial)
    assert result.returncode == 0, result.stdout + result.stderr
    args = arguments(project)
    debug = variant == "standalone-debug"
    portable = variant == "onefile"
    assert ("--onefile" in args) == portable
    assert ("--standalone" in args) == (not portable)
    assert [a for a in args if a.startswith("--windows-console-mode=")] == [
        "--windows-console-mode=" + ("force" if debug else "disable")]
    assert any("portable.marker=" in a for a in args) == portable
    assert "--output-filename=Open PDF.exe" in args
    assert "--output-dir=" + str(project / "build" / variant) in args
    assert ("--enable-plugin=data-hiding" in args) == bool(commercial)
    assert ("--enable-plugin=anti-debugger" in args) == bool(commercial and not debug)
    assert ("--enable-plugin=signtool" in args) == bool(commercial and not debug)
    assert not any("traceback-encryption" in a or "--embed-data" in a for a in args)
    assert any(a.startswith("--report=") for a in args)
    assert result.stdout.count("Building Open PDF:") == 1
    assert result.stdout.count("Output directory:") == 1


@pytest.mark.parametrize("compression", ["stdlib", "package", "none"])
def test_onefile_compression_preflight(tmp_path, compression):
    project, shim = make_project(tmp_path)
    result = run_script(project, shim, "onefile.ps1", "-Compiler", "msvc",
                        TEST_COMPRESSION=compression)
    if compression == "none":
        assert result.returncode != 0
        assert "pip install zstandard" in result.stderr
        assert not (project / "build-arguments.json").exists()
    else:
        assert result.returncode == 0, result.stdout + result.stderr


def test_debug_forwards_output_overrides(tmp_path):
    project, shim = make_project(tmp_path)
    result = run_script(project, shim, "standalone-debug.ps1", "-Compiler", "msvc",
                        "-OutputDirectory", "build/custom", "-OutputFilename", "Reader.exe")
    assert result.returncode == 0, result.stdout + result.stderr
    args = arguments(project)
    assert "--output-dir=" + str(project / "build" / "custom") in args
    assert "--output-filename=Reader.exe" in args


@pytest.mark.parametrize("failure", ["TEST_PLUGIN_ERROR", "TEST_BUILD_ERROR", "TEST_DIRTY"])
def test_build_and_validation_failures_propagate(tmp_path, failure):
    project, shim = make_project(tmp_path)
    result = run_script(project, shim, "standalone.ps1", "-Compiler", "msvc",
                        **{failure: "yes"})
    assert result.returncode != 0
    if failure == "TEST_PLUGIN_ERROR":
        assert not (project / "build-arguments.json").exists()
    if failure == "TEST_DIRTY":
        assert "Runtime data or private input: .env" in result.stdout
        assert (project / "build" / "standalone" / "main.dist" / ".env").exists()


def test_privacy_scan_encodings_and_chunk_boundary(tmp_path):
    project, shim = make_project(tmp_path)
    result = run_script(project, shim, "standalone.ps1", "-Compiler", "msvc", TEST_PRIVATE="yes")
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.count("Privacy scan found 'test-private-user'") == 2
    assert "notes.txt" in result.stdout
    assert "settings.json" in result.stdout
    assert "image.png" not in result.stdout


def test_persisted_data_is_preserved_by_default(tmp_path):
    project, shim = make_project(tmp_path)
    data = project / "local-appdata" / "open-pdf"
    data.mkdir(parents=True)
    settings = data / "settings.json"
    settings.write_text("private preferences", encoding="utf-8")
    result = run_script(project, shim, "standalone.ps1", "-Compiler", "msvc")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Persisted data at" in result.stdout
    assert settings.read_text("utf-8") == "private preferences"
