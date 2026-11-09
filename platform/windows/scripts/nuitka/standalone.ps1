#requires -Version 7.3
# Build Open PDF; paths resolve from platform/windows, not the caller.
[CmdletBinding()]
param(
    [string]$PythonExecutable = '.venv/Scripts/python.exe',
    [string]$OutputDirectory,
    [string]$OutputFilename,
    [switch]$UseCurrentDefaultPaths,
    [switch]$ResetRuntimeDefaults,
    [switch]$Console,
    [ValidateSet('msvc', 'clang', 'mingw64')]
    [string]$Compiler = 'clang',
    [string]$MsvcVersion = 'latest',
    [ValidateRange(1, 64)]
    [int]$Jobs = 4,
    [ValidateSet('yes', 'no', 'auto')]
    [string]$Lto = 'no',
    [switch]$LowMemory,
    [switch]$ShowBackendCommands
)

function Resolve-ProjectPath {
    param([string]$ProjectRoot, [string]$Path)
    if ([IO.Path]::IsPathRooted($Path)) { return [IO.Path]::GetFullPath($Path) }
    return [IO.Path]::GetFullPath((Join-Path $ProjectRoot $Path))
}

function Get-BuildConfiguration {
    param([string]$ProjectRoot, [string]$PythonExecutable, [string]$OutputDirectory,
          [string]$OutputFilename, [string]$Variant)
    $pythonPath = Resolve-ProjectPath $ProjectRoot $PythonExecutable
    if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
        throw "Build interpreter does not exist: $pythonPath. Pass -PythonExecutable to use another interpreter."
    }
    $pyprojectPath = Join-Path $ProjectRoot 'pyproject.toml'
    $metadata = & $pythonPath -X utf8 -c 'import json,sys,tomllib; print(json.dumps(tomllib.load(open(sys.argv[1], "rb"))))' $pyprojectPath
    if ($LASTEXITCODE -ne 0) { throw "Cannot read project metadata from $pyprojectPath." }
    $metadata = $metadata | ConvertFrom-Json
    $product = $metadata.tool.'open-pdf'.packaging
    foreach ($key in @('title', 'company-name', 'copyright')) {
        if (-not $product.$key) { throw "Set $key under [tool.open-pdf.packaging] in $pyprojectPath." }
    }
    $version = $metadata.project.version
    $description = ($metadata.project.description -split '\s+') -join ' '
    if ($version -notmatch '^\d+(\.\d+){1,3}$') {
        throw "Project version '$version' is not valid Windows version metadata."
    }
    # The version resource ships to users, so template placeholders must not.
    foreach ($value in @($version, $description, $product.title, $product.'company-name', $product.copyright)) {
        if ($value -match 'replace-me') { throw "Project metadata '$value' is still a placeholder." }
    }
    if (-not $OutputFilename) { $OutputFilename = "$($product.title).exe" }
    if ([IO.Path]::GetFileName($OutputFilename) -ne $OutputFilename -or
        [IO.Path]::GetExtension($OutputFilename) -ne '.exe') {
        throw 'OutputFilename must be a filename ending in .exe, without directories.'
    }
    if (-not $OutputDirectory) { $OutputDirectory = "build/$Variant" }
    $icon = Join-Path $ProjectRoot 'assets/open_pdf.ico'
    if (-not (Test-Path -LiteralPath $icon -PathType Leaf)) {
        throw "Missing icon: $icon. Generate it from assets/icons/open_pdf.svg at the repository root."
    }
    # The DejaVu fonts are git-ignored downloads; bundle them only when present.
    $fonts = @(Get-ChildItem -LiteralPath (Join-Path $ProjectRoot 'assets/fonts') -Filter '*.ttf' -File -ErrorAction SilentlyContinue)
    [PSCustomObject]@{
        Python = $pythonPath; Output = Resolve-ProjectPath $ProjectRoot $OutputDirectory
        Filename = $OutputFilename; Variant = $Variant
        Title = $product.title; Version = $version; Description = $description
        Company = $product.'company-name'; Copyright = $product.copyright
        AppDataName = $metadata.tool.'open-pdf'.'app-data-dir'; Icon = $icon; Fonts = $fonts
        RepositoryRoot = [IO.Path]::GetFullPath((Join-Path $ProjectRoot '../..'))
    }
}

function Test-ClangCompiler {
    if (Get-Command 'clang-cl.exe' -ErrorAction SilentlyContinue) { return $true }
    $vswhere = Join-Path ([Environment]::GetFolderPath('ProgramFilesX86')) 'Microsoft Visual Studio\Installer\vswhere.exe'
    if (-not (Test-Path -LiteralPath $vswhere)) { return $false }
    foreach ($installPath in @(& $vswhere -products * -property installationPath)) {
        if (Test-Path -LiteralPath (Join-Path $installPath 'VC\Tools\Llvm\x64\bin\clang-cl.exe')) { return $true }
    }
    return $false
}

function Get-CompilerArguments {
    param($Configuration, [string]$Compiler, [string]$MsvcVersion)
    switch ($Compiler) {
        'msvc' { return @("--msvc=$MsvcVersion") }
        'clang' {
            if (-not (Test-ClangCompiler)) {
                throw "Visual Studio clang-cl was not found. Install Visual Studio's clang component or pass -Compiler msvc."
            }
            return @('--clang')
        }
        'mingw64' {
            $pythonVersion = & $Configuration.Python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'
            if ([version]$pythonVersion -ge [version]'3.13') {
                throw "Nuitka cannot use MinGW64 with Python $pythonVersion. Pass -Compiler msvc or -Compiler clang."
            }
            return @('--mingw64')
        }
    }
}

function Get-NuitkaArguments {
    param($Configuration, [string]$ConsoleMode, [string[]]$CompilerArguments, [int]$Jobs,
          [string]$Lto, [switch]$LowMemory, [switch]$ShowBackendCommands, [switch]$Commercial, [switch]$DebugBuild)
    $arguments = @(
        '-m', 'nuitka', '--enable-plugin=pyside6', "--windows-console-mode=$ConsoleMode",
        '--assume-yes-for-downloads', "--jobs=$Jobs", "--lto=$Lto",
        "--output-filename=$($Configuration.Filename)", "--output-dir=$($Configuration.Output)",
        "--report=$(Join-Path $Configuration.Output 'compilation-report.xml')",
        "--windows-icon-from-ico=$($Configuration.Icon)",
        "--product-name=$($Configuration.Title)", "--file-version=$($Configuration.Version)",
        "--product-version=$($Configuration.Version)", "--file-description=$($Configuration.Description)",
        "--company-name=$($Configuration.Company)", "--copyright=$($Configuration.Copyright)",
        # Bundle data files one by one so screenshots and local state never ship.
        "--include-data-files=$($Configuration.Icon)=assets/open_pdf.ico"
    )
    foreach ($font in $Configuration.Fonts) {
        $arguments += "--include-data-files=$($font.FullName)=assets/fonts/$($font.Name)"
    }
    $arguments += $CompilerArguments
    if ($LowMemory) { $arguments += '--low-memory' }
    if ($ShowBackendCommands) { $arguments += '--show-scons' }
    if ($Commercial) {
        $arguments += @(
            '--enable-plugin=data-hiding'
        )
    }
    if ($Commercial -and -not $DebugBuild) {
        $arguments += '--enable-plugin=anti-debugger'
    }
    if (-not $DebugBuild) {
        $thumbprint = [Environment]::GetEnvironmentVariable('WINDOWS_CERTIFICATE_SHA1', 'User')
        if (-not $thumbprint) { $thumbprint = $env:WINDOWS_CERTIFICATE_SHA1 }
        if ($Commercial -and $thumbprint) {
            $arguments += '--enable-plugin=signtool', "--windows-certificate-sha1=$thumbprint"
        } else {
            Write-Warning 'Release executable is unsigned; configure WINDOWS_CERTIFICATE_SHA1 and Nuitka Commercial to sign it.'
        }
    }
    return $arguments
}

function Show-PersistedData {
    param($Configuration, [switch]$Portable, [switch]$ResetRuntimeDefaults)
    $localRoot = $env:LOCALAPPDATA
    if (-not $localRoot) { $localRoot = Join-Path ([Environment]::GetFolderPath('UserProfile')) 'AppData/Local' }
    $appDataName = $Configuration.AppDataName
    if ($appDataName -ne 'open-pdf') {
        throw "Unexpected application data folder '$appDataName'; review the reset targets before building."
    }
    $allowed = @($appDataName, "$appDataName-data")
    $paths = @(Join-Path $localRoot $appDataName)
    if ($Portable) { $paths += Join-Path $Configuration.Output "$appDataName-data" }
    foreach ($path in $paths) {
        $absolutePath = [IO.Path]::GetFullPath($path)
        if (-not (Test-Path -LiteralPath $absolutePath)) { continue }
        if (-not $ResetRuntimeDefaults) {
            Write-Warning "Persisted data at $absolutePath may affect smoke tests. Pass -ResetRuntimeDefaults to delete it."
            continue
        }
        $target = Get-Item -LiteralPath $absolutePath -Force
        $resolved = [IO.Path]::GetFullPath($target.FullName)
        if ($resolved -ne $absolutePath -or $target.Name -notin $allowed -or -not $target.PSIsContainer) {
            throw "Refusing unexpected reset target: $resolved"
        }
        $entries = @($target) + @(Get-ChildItem -LiteralPath $resolved -Recurse -Force)
        if ($entries | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }) {
            throw "Refusing to reset linked application data: $resolved"
        }
        try { Remove-Item -LiteralPath $resolved -Recurse -Force -ErrorAction Stop }
        catch { throw "Cannot reset $resolved. Close running instances of $($Configuration.Title) and retry. $_" }
    }
}

function Stop-RunningOutput {
    param([string]$ExecutablePath)
    $running = @(Get-Process -ErrorAction SilentlyContinue | Where-Object {
            try { $_.Path -eq $ExecutablePath } catch { $false }
        })
    if ($running.Count -eq 0) { return }
    $processIds = @($running | ForEach-Object { $_.Id })
    Stop-Process -Id $processIds -Force -ErrorAction Stop
    Wait-Process -Id $processIds -Timeout 10 -ErrorAction SilentlyContinue
}

function Invoke-Nuitka {
    param($Configuration, [string[]]$NuitkaArguments, [string]$ProjectRoot)
    $null = New-Item -ItemType Directory -Path $Configuration.Output -Force
    $logPath = Join-Path $Configuration.Output "nuitka-$($Configuration.Variant)-build.log"
    Write-Host "Output directory: $($Configuration.Output) (build log: $logPath)"
    Push-Location $ProjectRoot
    try {
        $pythonPath = $Configuration.Python
        # Native stderr becomes ErrorRecord objects; display their text normally.
        & $pythonPath @NuitkaArguments 2>&1 |
            ForEach-Object { $_.ToString() } |
            Tee-Object -FilePath $logPath | Out-Host
        if ($LASTEXITCODE -ne 0) { throw "Nuitka failed with exit code $LASTEXITCODE. See $logPath." }
    } finally { Pop-Location }
}

function Invoke-PrivacyScan {
    param($Configuration, [string]$ProjectRoot, [string]$DistPath)
    $scan = @'
"""Report developer identifiers in unpacked distribution files."""

import json
import os
import sys
import tomllib
from pathlib import Path

SCANNED_SUFFIXES = {".exe", ".json", ".toml", ".ini", ".cfg", ".txt", ".env"}


def scan(dist: Path, project: Path, repository: Path) -> list[dict[str, str]]:
    """Scan bounded chunks for UTF-8 and UTF-16LE identifiers."""
    if not dist.is_dir():
        message = f"Distribution folder does not exist: {dist}"
        raise ValueError(message)
    metadata = tomllib.loads(
        (project / "pyproject.toml").read_text(encoding="utf-8"),
    )
    terms = {os.environ.get("USERNAME", ""), str(project), str(repository)}
    terms.update(
        author.get("email", "")
        for author in metadata["project"].get("authors", [])
    )
    terms.update({project.as_posix(), repository.as_posix()})
    patterns = [
        (term, term.encode(encoding))
        for term in terms
        if term
        for encoding in ("utf-8", "utf-16le")
    ]
    overlap = max(len(pattern) for _, pattern in patterns) - 1
    hits: list[dict[str, str]] = []
    for path in dist.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SCANNED_SUFFIXES:
            continue
        found: set[str] = set()
        with path.open("rb") as stream:
            tail = b""
            while chunk := stream.read(1024 * 1024):
                block = tail + chunk
                found.update(
                    term for term, pattern in patterns if pattern in block
                )
                tail = block[-overlap:]
        hits.extend({"term": term, "file": str(path)} for term in sorted(found))
    return hits


if __name__ == "__main__":
    sys.stdout.write(
        json.dumps(scan(*(Path(arg).resolve() for arg in sys.argv[1:]))),
    )
'@
    $hits = & $Configuration.Python -X utf8 -c $scan $DistPath $ProjectRoot $Configuration.RepositoryRoot
    if ($LASTEXITCODE -ne 0) { throw "Privacy scan could not inspect $DistPath." }
    foreach ($hit in @($hits | ConvertFrom-Json)) {
        Write-Warning "Privacy scan found '$($hit.term)' in $($hit.file)"
    }
}

function Test-CommercialNuitka {
    param([string]$PythonPath)
    $plugins = & $PythonPath -m nuitka --plugin-list 2>&1
    if ($LASTEXITCODE -ne 0) { throw 'Cannot list Nuitka plugins. Install Nuitka in the selected interpreter.' }
    $commercial = [bool]($plugins -match '\bdata-hiding\b')
    if (-not $commercial) { Write-Warning 'Nuitka Commercial was not detected; program constants are not encrypted.' }
    return $commercial
}

$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
# The console variant gets its own default folder so it never overwrites
# the release folder that the installer packages.
$variant = if ($Console) { 'standalone-debug' } else { 'standalone' }
$config = Get-BuildConfiguration $projectRoot $PythonExecutable $OutputDirectory $OutputFilename $variant
Write-Host "Building $($config.Title): $variant"
if ($UseCurrentDefaultPaths) {
    throw 'Open PDF has no bundled defaults file, so -UseCurrentDefaultPaths is unsupported; live settings are never bundled.'
}
$Commercial = Test-CommercialNuitka $config.Python
Show-PersistedData $config -ResetRuntimeDefaults:$ResetRuntimeDefaults
$consoleMode = if ($Console) { 'force' } else { 'disable' }
$compilerArguments = Get-CompilerArguments $config $Compiler $MsvcVersion
$nuitkaArguments = @(Get-NuitkaArguments $config $consoleMode $compilerArguments $Jobs $Lto `
    -LowMemory:$LowMemory -ShowBackendCommands:$ShowBackendCommands -Commercial:$Commercial -DebugBuild:$Console)
$nuitkaArguments += @('--standalone', 'open_pdf/main.py')
Invoke-Nuitka $config $nuitkaArguments $projectRoot
$distPath = Join-Path $config.Output 'main.dist'
Invoke-PrivacyScan $config $projectRoot $distPath
$validateScript = Join-Path $PSScriptRoot 'validate_release.ps1'
& $validateScript -DistPath $distPath -PythonExecutable $config.Python
if ($LASTEXITCODE -ne 0) { throw "Release validation failed for $distPath." }
