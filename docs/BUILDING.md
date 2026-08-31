# Building ONVIF Deck

## Source environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
pytest -q
```

PyInstaller is platform-specific. Build a Windows application on Windows and a
macOS application on macOS.

## macOS application bundle

The checked-in spec targets the current macOS architecture and includes the
`imageio-ffmpeg` binary plus the macOS keyring backend.

```bash
python -m pip install "pyinstaller>=6.11,<7"
pyinstaller --noconfirm --clean packaging/onvif-deck.spec
codesign --verify --deep --strict "dist/ONVIF设备工作台.app"
```

Create distributable archives:

```bash
hdiutil create \
  -volname "ONVIF Deck" \
  -srcfolder "dist/ONVIF设备工作台.app" \
  -ov -format UDZO \
  "dist/ONVIF-Deck-macOS.dmg"

ditto -c -k --sequesterRsrc --keepParent \
  "dist/ONVIF设备工作台.app" \
  "dist/ONVIF-Deck-macOS.zip"
```

The local build uses an ad-hoc signature. Public releases should use an Apple
Developer ID certificate and Apple notarization.

## Windows

Install PyInstaller in a Windows virtual environment and create a Windows spec
that keeps the same hidden imports and `imageio_ffmpeg` data collection. A
Windows artifact has not yet been added to the repository; contributions are
welcome.

## Release checklist

1. Update the version in `pyproject.toml`, `src/onvif_scanner/__init__.py`, the
   sidebar label, and the macOS spec.
2. Run `ruff check src tests scripts` and `pytest -q`.
3. Generate screenshots with `python scripts/demo.py --capture-dir docs/images`.
4. Run a privacy review of every tracked image and text file.
5. Build and test the application on the target operating system.
6. Generate SHA-256 checksums for release artifacts.
7. Publish binaries through GitHub Releases, not in the Git repository.
