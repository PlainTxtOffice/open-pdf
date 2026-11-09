"""Build an architecture-specific macOS app using an explicit bundle ID."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


def main() -> int:
    """Build on a Mac without assuming publisher or signing identities."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-id", required=True)
    parser.add_argument("--codesign-identity")
    arguments = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", arguments.bundle_id):
        parser.error("--bundle-id must be a reverse-DNS identifier")
    if sys.platform != "darwin":
        parser.error("Build the macOS app on a Mac with native dependencies.")
    environment = os.environ.copy()
    environment["OPEN_PDF_BUNDLE_ID"] = arguments.bundle_id
    if arguments.codesign_identity:
        environment["OPEN_PDF_SIGN_IDENTITY"] = arguments.codesign_identity
    else:
        environment.pop("OPEN_PDF_SIGN_IDENTITY", None)
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "scripts/open_pdf.spec"],
        cwd=PROJECT, env=environment, check=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
