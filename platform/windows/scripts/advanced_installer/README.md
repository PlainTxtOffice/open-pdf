# Advanced Installer Builds

Run from `platform/windows/` using PowerShell 7.3 or newer:

```powershell
$env:ADVINST_COM = 'C:\Program Files (x86)\Caphyon\Advanced Installer 24.1\bin\x86\AdvancedInstaller.com'
./scripts/nuitka/standalone.ps1
./scripts/advanced_installer/build_installer.ps1
```

The build needs licensed Advanced Installer Professional, the project
`.venv/Scripts/python.exe` with Python 3.12 or newer, and the complete release
Nuitka payload. Follow the [Nuitka README](../nuitka/README.md) for compilation,
Commercial features, privacy checks, and application signing. Recompile after
changing application code or version; the installer script does not compile it.

The current x64 output is `build/installer/open-pdf-1.0.0-x64-setup.exe`.
The filename follows the project version and executable architecture. The script
prints the exact installer and AIP paths and reports the Authenticode status
after verifying a fresh, nonempty artifact.

## Parameters and paths

| Parameter | Default |
| --- | --- |
| `ProjectRoot` | Two levels above the script directory |
| `SourceDirectory` | `build/standalone/main.dist` |
| `PackagingDirectory` | `dev-docs/packaging/advanced_installer` |
| `OutputDirectory` | `build/installer` |
| `AdvancedInstaller` | `ADVINST_COM`, with surrounding quotes accepted |

Relative directory overrides resolve against the Windows project root.
A relative `ProjectRoot` resolves against the script directory. An explicitly
supplied invalid CLI path fails without selecting a different installation.
The build is named `DefaultBuild`.

For example, call the script from a different working directory, substituting
your checkout's absolute path:

```powershell
Set-Location $env:TEMP
& 'C:\Projects\open_pdf\platform\windows\scripts\advanced_installer\build_installer.ps1' -OutputDirectory 'build/installer review'
```

A separate packaging directory can initialize an isolated project for an
alternate release payload:

```powershell
./scripts/advanced_installer/build_installer.ps1 -SourceDirectory 'build/release candidate/main.dist' -PackagingDirectory 'build/installer candidate/project' -OutputDirectory 'build/installer candidate/output'
```

An isolated project has a different upgrade identity and is for testing only.
Distributed releases must keep using the persistent
`dev-docs/packaging/advanced_installer/open-pdf.aip`. An existing AIP with a
different synchronized source fails clearly; deliberately edit its mapping in
Advanced Installer before using a new source directory. Keep source references
relative to the AIP so the checkout can move.

## Installation and upgrades

The installer installs Open PDF per machine under
`[ProgramFiles64Folder][Manufacturer]\[ProductName]` for x64, or the
corresponding 32-bit Program Files folder for x86. It requires elevation and
creates one Start menu shortcut. Running the application does not require
elevation. Application data stays in `%LOCALAPPDATA%/open-pdf`; uninstall leaves
that data alone. Target PCs do not need Python installed separately.

The AIP owns the UpgradeCode, installation scope, shortcuts, synchronized
payload mapping, upgrade policy, and signing settings. Keep it in version
control. Rebuilds refresh the single APPDIR synchronization and update the
version and output paths without reimporting the payload or recreating
shortcuts. Major upgrades remove the old product before installing the new
product. Increment the version for every distributed update. Do not regenerate
the AIP or use this synchronization workflow for patches or overlapping
upgrades.

The script rejects architecture and identity mismatches, duplicate payload
entries, missing standalone dependencies, invalid MSI versions, and executable
versions that differ from `pyproject.toml`. Console debug and portable builds
are rejected. The existing release validator also rejects runtime data and
private inputs. Keep the complete `.dist` folder intact and smoke-test a copy.

Installer signing is configured separately on the persistent AIP's Digital
Signature page. No installer signing certificate is configured initially.
Do not store certificate passwords or keys in the repository. A successful
unsigned build is not evidence of signing or distribution readiness.

`build_installer.ps1` contains all installer-specific metadata, executable,
AIP validation, and build functions. No installer helper scripts are needed.
It still invokes Nuitka's shared `validate_release.ps1` before packaging.
Initial projects disable Advanced Installer's automatic AIP backups; no
script-level backup or cache is added.

## Validation before distribution

Inspect the generated MSI and extracted payload, then test installation and
Start menu launch on a disposable Windows machine without Python. Exercise PDF
opening and editing, upgrade from an older version, downgrade handling, repair,
and uninstall. Check that user data survives and obsolete application files do
not remain. Build validation alone does not establish these behaviors.

Retain final installers, complete standalone folders, and reusable Nuitka
intermediates; remove only verified disposable test output.
