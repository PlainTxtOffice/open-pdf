#requires -Version 7.3
# Report runtime data, private inputs, or keys inside a standalone .dist
# folder before Advanced Installer packages it. Never changes any file.
[CmdletBinding()]
param(
    [string]$DistPath = 'build/standalone/main.dist',
    [string]$PythonExecutable = '.venv/Scripts/python.exe'
)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
function Resolve-ProjectPath {
    param([string]$ProjectRoot, [string]$Path)
    if ([IO.Path]::IsPathRooted($Path)) { return [IO.Path]::GetFullPath($Path) }
    return [IO.Path]::GetFullPath((Join-Path $ProjectRoot $Path))
}
$validate = @'
"""Inspect installer inputs without changing the distribution."""

import json
import sys
from pathlib import Path


def validate(dist: Path, project: Path) -> list[str]:
    """Reject runtime data, portable markers, and private build inputs.

    - Folder names come from the application's own path module, so a renamed
      storage folder stays covered.
    - The traceback-encryption key decrypts crash output; it must stay with
      the developer and never ship.
    """
    sys.path.insert(0, str(project))
    from open_pdf.config import path_handler as paths  # noqa: PLC0415

    if not dist.is_dir():
        return [f"Distribution folder does not exist: {dist}"]
    # Runtime folders land at the bundle root; dependencies may ship their
    # own nested data/ or logs/ folders, so only the top level is checked.
    top_level = {
        name.casefold()
        for name in (
            paths.PORTABLE_DATA_DIR_NAME,
            paths.DATA_DIR.name,
            paths.LOGS_DIR.name,
        )
    }
    problems = [
        f"Runtime data or private input: {path.relative_to(dist)}"
        for path in dist.rglob("*")
        if (path.parent == dist and path.name.casefold() in top_level)
        or path.name.casefold() == paths.PORTABLE_MARKER_NAME
        or (path.name.casefold() == "tests"
            and path.parent in (dist, dist / "open_pdf"))
        # A bare .env file has no suffix, so match the name's ending.
        or path.name.casefold().endswith((".env", ".key"))
    ]
    if not any(dist.glob("*.exe")):
        problems.append("Distribution contains no executable.")
    return problems


if __name__ == "__main__":
    sys.stdout.write(json.dumps(validate(Path(sys.argv[1]), Path(sys.argv[2]))))
'@
$distPath = Resolve-ProjectPath $projectRoot $DistPath
$pythonPath = Resolve-ProjectPath $projectRoot $PythonExecutable
try {
    $problems = & $pythonPath -X utf8 -c $validate $distPath $projectRoot
    if ($LASTEXITCODE -ne 0) { throw "Unable to inspect $distPath." }
    $problems = @($problems | ConvertFrom-Json)
    if ($problems.Count) {
        foreach ($problem in $problems) { Write-Host $problem }
        exit 1
    }
    Write-Host "Clean distribution: $distPath"
    exit 0
} catch {
    Write-Host $_.Exception.Message
    exit 1
}
