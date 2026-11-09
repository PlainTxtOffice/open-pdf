#!/usr/bin/env bash
# Local and hosted macOS validation; outputs follow the workflow contract.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Run macOS CI on a Mac." >&2
  exit 1
fi

python_bin="${PYTHON_BIN:-python3}"
"$python_bin" -c 'import sys; assert (3, 12) <= sys.version_info[:2] < (3, 16), "Use Python 3.12 through 3.15"'
"$python_bin" -m venv .venv
.venv/bin/python -m pip install -e '.[dev,build,ocr]'
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy open_pdf
.venv/bin/rumdl check .
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest

# A test-only identity, never an inferred publisher or distribution identity.
.venv/bin/python scripts/build.py --bundle-id local.openpdf.ci
codesign --verify --deep --strict 'dist/Open PDF.app'
mkdir -p build/ci-artifacts
ditto -c -k --sequesterRsrc --keepParent \
  'dist/Open PDF.app' build/ci-artifacts/open-pdf-macos.zip
