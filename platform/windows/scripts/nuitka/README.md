# Nuitka Builds

| Script | Executable | Output | Distribution |
| --- | --- | --- | --- |
| `onefile.ps1` | `Open PDF.exe` | `build/onefile/` | Portable download |
| `standalone.ps1` | `Open PDF.exe` | `build/standalone/main.dist/` | Installer payload |
| `standalone-debug.ps1` | `Open PDF.exe` | `build/standalone-debug/main.dist/` | Local troubleshooting |

Use PowerShell 7.3 or newer. Run from `platform/windows/`; scripts also resolve
their inputs correctly from other working directories. The build interpreter
defaults to `.venv/Scripts/python.exe` and must have Nuitka and the
application's dependencies installed. Pass `-PythonExecutable <path>` to select
another one. Onefile compression uses Python's `compression.zstd` when
available, or the `zstandard` package. If both are absent, install `zstandard`
in that interpreter.

```powershell
./scripts/nuitka/onefile.ps1
./scripts/nuitka/standalone.ps1
./scripts/nuitka/standalone-debug.ps1
```

The title, company, and copyright come from `[tool.open-pdf.packaging]` in
`pyproject.toml`. The application version and description come from `[project]`.
The title remains Open PDF. Each variant writes `compilation-report.xml` and
`nuitka-<variant>-build.log` in its output directory.

## Options and storage

- `-OutputDirectory` and `-OutputFilename` override the output location and
  executable name. Relative paths resolve from the Windows project root.
- `-Compiler msvc|clang|mingw64` selects the compiler; local builds retain the
  established Visual Studio clang default. `-MsvcVersion` applies to MSVC.
  Hosted builds explicitly select MSVC. MinGW64 is rejected on Python 3.13+.
- `-Jobs`, `-Lto`, `-LowMemory`, and `-ShowBackendCommands` pass through to
  Nuitka.
- `-ResetRuntimeDefaults` explicitly deletes existing `%LOCALAPPDATA%/open-pdf`
  data and, for onefile, the `open-pdf-data` folder in the output directory.
  Without this switch, existing user data is preserved and only a warning is
  printed. Linked folders are refused during a reset.
- Onefile stops a running copy of its exact output executable before rebuilding;
  `-NoStopRunningOutput` disables that behavior.
- `-UseCurrentDefaultPaths` is rejected: there is no bundled defaults file.

Both standalone variants share `%LOCALAPPDATA%/open-pdf`. Separate build folders
do not isolate application settings. Portable builds use `open-pdf-data` beside
the executable, falling back to `%LOCALAPPDATA%/open-pdf` when necessary.

The debug launcher opens a console alongside the GUI. It does not enable the
compiler's `--debug` option or change application logging levels. Run its
executable from a terminal when startup output must remain visible after exit.

## Commercial detection and signing

The scripts inspect the selected interpreter's Nuitka plugin list once. When
`data-hiding` is available, all variants protect constants. Release variants
also enable the anti-debugger; the debug variant omits it and signing. Free
Nuitka builds use no Commercial flags and warn that constants are not encrypted.

No bundled file currently needs embedding. The icon and optional local DejaVu
fonts remain ordinary files, and the onefile portable marker stays detectable.
Traceback encryption is disabled until a key-management process is chosen.
Existing private `.key` files remain excluded from Git and release payloads.

For signed Commercial release builds, configure the certificate thumbprint once
per Windows account, using a code-signing certificate already installed there:

```powershell
[Environment]::SetEnvironmentVariable('WINDOWS_CERTIFICATE_SHA1', '<certificate thumbprint>', 'User')
```

The scripts read the user setting directly, with an inherited process value as
a fallback. Without a configured certificate or Commercial Nuitka, release
builds remain unsigned and print a warning. They never enable deep DLL signing.

PyMuPDF and MuPDF retain their separate AGPL/commercial licensing requirements;
see the repository README's license section.

## Privacy and release checks

The build scripts contain their own metadata reading and bounded privacy scan;
no helper module is required. After compilation, they scan the unpacked
`main.dist` executables and text files for the developer username, repository
and project paths, and author emails in UTF-8 and UTF-16LE. Each hit produces a
warning. Only the icon, optional fonts, and onefile marker are bundled
explicitly; screenshots, user settings, tests, logs, and credentials are
excluded.

Both standalone variants then run `validate_release.ps1`. This report-only
command fails for runtime data, portable markers, `.env` or `.key` files,
application test folders, a missing payload, or a payload without an executable.
Dependency-owned data and test folders are allowed. The command never deletes
or changes the payload.

## Distribution and installer

- Ship the portable `build/onefile/Open PDF.exe` alone, without its generated
  `open-pdf-data` folder.
- Package the complete release `build/standalone/main.dist` folder for an
  installer. Keep the debug output for troubleshooting.
- Keep build intermediates for reuse, but never distribute them, compilation
  reports, build logs, or decryption keys.
- Run smoke tests on a copy of the `.dist` folder so tests cannot alter the
  installer input.

Build the installer with `scripts/advanced_installer/build_installer.ps1`; see
the [installer README](../advanced_installer/README.md). The persistent project
is `dev-docs/packaging/advanced_installer/open-pdf.aip`. It installs under
Program Files and keeps user data in `%LOCALAPPDATA%/open-pdf`; uninstalling
preserves that data. The installer script runs the release validator before
editing the AIP. When building through the Advanced Installer GUI, run this
check first with `platform/windows/` as the working directory:

```powershell
pwsh -NoProfile -File scripts/nuitka/validate_release.ps1
```

The Windows build workflow runs CI before building free-Nuitka standalone and
onefile artifacts. It runs manually or on version tags once published. Use those
unsigned artifacts to check builds; produce Commercial distributions locally.
Publishing uses the repository's `github-repo-upload` selection.
