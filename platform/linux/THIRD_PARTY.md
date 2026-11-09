# Third-party dependencies

Open PDF's MIT license covers its original code, not the dependencies bundled
with a compiled distribution. Review the applicable dependency licenses before
distributing a build.

- [PyMuPDF and MuPDF](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright)
  are offered under AGPL or commercial terms.
- [PySide6 and Qt](https://doc.qt.io/qtforpython-6/licenses.html) are available
  under LGPL/GPL or commercial terms, depending on the components used.
- [Keyring](https://github.com/jaraco/keyring),
  [SecretStorage](https://github.com/mitya57/secretstorage),
  [Pillow](https://python-pillow.github.io/), and
  [pytesseract](https://github.com/madmaze/pytesseract) retain their own
  licenses.

The archive's `build-info.json` records the main dependency versions used for
that build. Tesseract and its language data are installed separately through
the Linux distribution's package manager.
