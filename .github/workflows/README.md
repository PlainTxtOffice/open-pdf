---
last_updated: 2026-11-09
version: 0.1.1
description: Platform workflow entrypoints, native runners, setup, and build artifacts.
---

# GitHub Workflows

These workflows validate and build Open PDF on GitHub-hosted machines after
publication. Local development and release builds still run on your own
platform machines.

| Platform | Workflow | Runner | Checks and output |
| --- | --- | --- | --- |
| Windows | [CI](ci.yml), [build](windows-build.yml) | Windows | Python lint, types, tests, Markdown; Nuitka standalone and onefile artifacts |
| Linux | [build](linux-build.yml) | Ubuntu 24.04 x86-64 | Python checks, desktop keyring and GUI tests; Nuitka standalone archive |
| macOS | [build](macos-build.yml) | macOS | Python checks and tests; PyInstaller app bundle and archived artifacts |

Android and iOS workflows are not present in this repository.

## Triggers and artifacts

- Windows CI runs on pushes to `main`, pull requests, manual requests, and
  calls from another workflow. The Windows build runs manually or on `v*`
  tags and requires CI to pass first.
- Linux runs on pushes to `main` and pull requests affecting its platform,
  workflow, shared source icon, or license. It also supports **Run workflow**;
  it has no tag trigger.
- macOS runs on pushes to `main` and pull requests affecting its platform or
  workflow, on `v*` tags, and through **Run workflow**.

Build artifacts are retained for 30 days. These workflows do not create
GitHub releases or submit applications to stores. Windows and macOS build
jobs emit skip notices when their entrypoint scripts are absent; a skipped
build is not evidence that a platform was compiled.

## Windows

CI uses Python 3.12 and 3.14. The build uses Python 3.14 and free Nuitka to
produce standalone and onefile artifacts. Use those unsigned artifacts to
check builds; produce Commercial distributions locally. The licensed Advanced
Installer build and its persistent project remain local.

See the [Windows build guide](../../platform/windows/scripts/nuitka/README.md).

## Linux

The workflow installs Python 3.14, compiler and desktop libraries, and the
project's development, build, and OCR dependencies. It runs lint, type,
Markdown, desktop-entry, and regression checks, followed by Secret Service
integration and source GUI tests.

It invokes `scripts/build.py` under Xvfb, then checks the extracted standalone
archive with `scripts/smoke_test.py`. The uploaded artifact is
`open-pdf-linux-x86_64`, containing `open-pdf-*-linux-x86_64.tar.gz`.
Linux setup and checks are defined directly in the workflow; there is no
Linux `scripts/ci.sh` entrypoint.

See the [Linux guide](../../platform/linux/README.md).

## macOS

The workflow invokes the existing script from `platform/mac_os/`:

```bash
bash -euo pipefail scripts/ci.sh
```

The script creates a virtual environment using `PYTHON_BIN` or `python3`,
requires Python 3.12 through 3.15, installs dependencies, and runs lint,
type, Markdown, and offscreen tests. It builds with PyInstaller using the
explicit test bundle identity `local.openpdf.ci`, verifies the signature,
and archives the app in `build/ci-artifacts/`.

The workflow packages that directory as `build/macos-build.tar.gz`. Its
artifact name includes the repository name and runner architecture; it does
not claim universal-binary support. Distribution signing and notarization
require a separate release process.

See the [macOS guide](../../platform/mac_os/README.md).

## Publishing and validation

The `github-repo-upload` selection includes these workflows and their platform
sources, build scripts, and dependency configuration. The Windows installer
project is intentionally excluded.

Validate workflow syntax with `actionlint` and review each platform's commands.
Local checks do not establish native runtime or packaging support. The first
hosted Linux and macOS builds remain pending; run them on GitHub after
publication.

## References

- [GitHub workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
- [GitHub-hosted runner images](https://github.com/actions/runner-images)
