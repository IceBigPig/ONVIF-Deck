# Contributing to ONVIF Deck

Thank you for helping improve ONVIF Deck. Camera firmware differs widely, so
small compatibility reports and focused fixes are especially useful.

## Before opening an issue

1. Search existing issues.
2. Confirm that ONVIF is enabled and that the account is an ONVIF user.
3. Test both discovery and manual Device Service URL entry.
4. Remove credentials and private data before attaching diagnostics.

Never publish:

- RTSP URLs containing usernames or passwords;
- public IP addresses, VPN addresses, or precise locations;
- camera serial numbers or hardware identifiers;
- faces, homes, offices, license plates, or other private video frames.

Use documentation addresses such as `192.0.2.10` in examples.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
ruff check src tests scripts
pytest -q
```

`python scripts/demo.py` launches a reproducible demo that never accesses the
network, system keychain, or a real camera.

## Pull requests

- Keep changes focused and explain the camera behavior being addressed.
- Add or update tests for parsing and classification changes.
- Preserve UI responsiveness: network and decoder work must not run on the Qt
  main thread.
- Do not log credentials or credential-bearing RTSP URLs.
- Update the README or changelog when behavior changes.
- Run lint and tests before opening the pull request.

## Commit messages

Use a short imperative subject, for example:

- `Add Media2 profile fallback`
- `Prevent blocked FFmpeg shutdown`
- `Document Dahua multi-sensor profiles`

By contributing, you agree that your contribution is licensed under the MIT
License used by this repository.
