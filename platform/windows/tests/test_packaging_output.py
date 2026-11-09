"""Check native output rendering and exit codes without invoking Nuitka."""

import json
import subprocess
import sys

import pytest

from packaging_support import POWERSHELL, PROJECT

pytestmark = pytest.mark.skipif(not POWERSHELL, reason="PowerShell 7 is required")

HARNESS = r"""param($BuildScript, $Python, $OutputDirectory, [int]$NativeExit)
$ErrorActionPreference = 'Stop'
$tokens = $null
$parseErrors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile(
    $BuildScript, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw 'Build script did not parse.' }
$definition = $ast.Find({ param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
    $node.Name -eq 'Invoke-Nuitka'
}, $true)
Invoke-Expression $definition.Extent.Text

# Observe what reaches the host, before PowerShell chooses an error color.
function Out-Host {
    param([Parameter(ValueFromPipeline)]$InputObject)
    process {
        @{ type = $InputObject.GetType().FullName; text = $InputObject.ToString() } |
            ConvertTo-Json -Compress | Write-Output
    }
}
$configuration = [pscustomobject]@{
    Python = $Python; Output = $OutputDirectory; Variant = 'probe'
}
$code = 'import sys; print("ordinary output", flush=True); print("ordinary diagnostic", file=sys.stderr, flush=True); sys.exit(int(sys.argv[1]))'
Invoke-Nuitka $configuration @('-c', $code, "$NativeExit") $OutputDirectory
"""


@pytest.mark.parametrize("script", ["onefile.ps1", "standalone.ps1"])
@pytest.mark.parametrize("exit_code", [0, 12])
def test_native_output_is_text(tmp_path, script, exit_code):
    harness = tmp_path / "output-probe.ps1"
    harness.write_text(HARNESS, encoding="utf-8")
    output = tmp_path / "output"
    result = subprocess.run(
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-File", str(harness),
         "-BuildScript", str(PROJECT / "scripts" / "nuitka" / script),
         "-Python", sys.executable, "-OutputDirectory", str(output),
         "-NativeExit", str(exit_code)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=20, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    records = [json.loads(line) for line in result.stdout.splitlines()
               if line.startswith("{")]
    assert {item["text"] for item in records} == {
        "ordinary output", "ordinary diagnostic",
    }
    assert all(item["type"] == "System.String" for item in records)
    log = (output / "nuitka-probe-build.log").read_text(encoding="utf-8")
    assert "ordinary output" in log
    assert "ordinary diagnostic" in log
    if exit_code:
        assert result.returncode != 0
        assert "Nuitka failed with exit code 12" in result.stderr
    else:
        assert result.returncode == 0, result.stdout + result.stderr
