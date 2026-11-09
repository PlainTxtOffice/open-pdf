# macOS port notes

## Ownership and code reuse

The first macOS implementation adapts the committed Windows viewer at
`0c9ca2914e3831940a67862cb4f5d88936b1e7f5`. It preserves the document domains,
workflows, PyMuPDF adapter, tabbed viewer, search, printing, optional OCR, and
light editing. It does not include the separate experimental Rust engine.

Linux and macOS currently have independent source trees. This avoids changing
another agent's work or importing Windows internals. Fixes in common PDF or
Qt behavior currently need deliberate propagation. Once both ports settle,
document domains, workflows, and rendering can be candidates for a separately
installable shared package; platform entrypoints, storage, credential access,
and packaging should retain their platform owners.

macOS deliberately replaces Windows storage migration, DPAPI password files,
taskbar identification, bundled font configuration, and scrollbar styling.
Standard shortcuts, native menu roles, Finder events, and Homebrew Tesseract
discovery are macOS integration points. Existing OCR caching is preserved in
the native cache directory; no new caching or backup policy is introduced.

## Icons

The source is `../../assets/icons/open_pdf.svg`, relative to the platform root.
Generate the macOS asset catalog, ICNS, and runtime PNG with:

```sh
.venv/bin/python scripts/generate_icons.py
```

The generator uses Qt SVG rendering. Commit its outputs so app builds do not
need conversion tools or a sibling platform. The Qt app uses the PNG while
PyInstaller uses the ICNS; the asset catalog is available for native tooling.

## Mac acceptance checklist

Local validation on 2026-11-09 used the existing Windows environment's Python
3.15.2 with the macOS project as the working directory: 250 tests passed,
Ruff passed, and mypy passed for 114 source files. The tests include a separate
Qt process delivering file-open events to a real window. An isolated setuptools
wheel build succeeded, and its packaged startup module and icon were inspected.
Generated PNG dimensions, transparency, and ICNS framing were also checked.
These checks do not replace the following native Mac acceptance pass.

- Install from a clean source environment and build the app. Inspect the
  bundle's PDF association and validate its signature with `codesign`.
- Open several PDFs from the CLI, Finder Open With, and Dock drops, both at
  cold start and while the app is already running. Verify existing tabs are
  activated instead of duplicated and paths containing spaces work.
- Check About/Quit in the application menu; exercise Command-O, Command-S,
  Shift-Command-S, Command-P, Command-F, and Command-W.
- Check page navigation, search, selection/copy, Retina rendering, thumbnail
  resizing, dark mode, trackpad scrolling, and Command-wheel zoom.
- Edit, save, reopen, rename, and print a disposable PDF. Exercise Save As,
  unsaved-change cancellation, and closing several dirty tabs.
- Open an encrypted PDF, permit Keychain access, and reopen it. Repeat with
  Keychain access denied. Confirm no password JSON file appears.
- Exercise OCR from Finder with Tesseract installed outside Finder's PATH.
- Verify settings, OCR results, and logs appear only in the documented Library
  locations and the application runs from a read-only installation directory.
- Repeat on each supported CPU architecture. Record actual tested macOS
  versions before advertising a minimum OS version or distributing releases.

The repository's macOS build workflow invokes `bash scripts/ci.sh`. This runs
Python checks and packages an ad-hoc signed app with the test-only identifier
`local.openpdf.ci`. It produces a local-test artifact and does not publish,
notarize, or verify interactive system dialogs. Supply an actual publisher's
identifier explicitly to `scripts/build.py` for a distribution build.
