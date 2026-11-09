# Build only through build.py on macOS. PyInstaller supplies the build classes.
import os
import tomllib
from pathlib import Path

project = Path(SPECPATH).parent
metadata = tomllib.loads((project / "pyproject.toml").read_text(encoding="utf-8"))
version = metadata["project"]["version"]
analysis = Analysis(
    [str(project / "open_pdf/main.py")],
    pathex=[str(project)],
    datas=[(str(project / "open_pdf/assets/open_pdf.png"), "open_pdf/assets")],
    hiddenimports=["keyring.backends.macOS", "pytesseract", "PIL.Image"],
    excludes=["tkinter"],
)
archive = PYZ(analysis.pure)
executable = EXE(
    archive, analysis.scripts, [],
    exclude_binaries=True,
    name="Open PDF",
    console=False,
    argv_emulation=False,
    codesign_identity=os.environ.get("OPEN_PDF_SIGN_IDENTITY"),
)
collection = COLLECT(
    executable, analysis.binaries, analysis.datas, name="Open PDF",
)
app = BUNDLE(
    collection,
    name="Open PDF.app",
    icon=str(project / "assets/open_pdf.icns"),
    bundle_identifier=os.environ["OPEN_PDF_BUNDLE_ID"],
    version=version,
    info_plist={
        "CFBundleDisplayName": "Open PDF",
        "CFBundleShortVersionString": version,
        "NSHighResolutionCapable": True,
        "NSPrincipalClass": "NSApplication",
        "CFBundleDocumentTypes": [{
            "CFBundleTypeName": "PDF document",
            "CFBundleTypeRole": "Editor",
            "LSItemContentTypes": ["com.adobe.pdf"],
            "LSHandlerRank": "Alternate",
        }],
    },
)
