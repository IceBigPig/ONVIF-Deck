<div align="center">

# ONVIF Deck

**Discover ONVIF cameras, inspect every media profile, and preview multiple
RTSP streams from one desktop workspace.**

[![CI](https://github.com/IceBigPig/ONVIF-Deck/actions/workflows/ci.yml/badge.svg)](https://github.com/IceBigPig/ONVIF-Deck/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.10--3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Qt](https://img.shields.io/badge/UI-PySide6-41CD52?logo=qt&logoColor=white)](https://doc.qt.io/qtforpython-6/)
[![License](https://img.shields.io/github/license/IceBigPig/ONVIF-Deck)](LICENSE)

**English** · [简体中文](README.zh-CN.md)

</div>

![ONVIF Deck multi-view preview](docs/images/preview.png)

> All screenshots use documentation-only IP addresses and synthetic video
> frames. No real camera, serial number, credential, or private scene is
> included in this repository.

## Download for Apple Silicon

The ready-to-run macOS build supports Apple Silicon (M1, M2, M3, M4, and
later) on macOS 11 or newer:

- [Download DMG](https://github.com/IceBigPig/ONVIF-Deck/releases/download/v1.1.1/ONVIF%E8%AE%BE%E5%A4%87%E5%B7%A5%E4%BD%9C%E5%8F%B0-v1.1.1-macOS-arm64.dmg)
- [Download ZIP](https://github.com/IceBigPig/ONVIF-Deck/releases/download/v1.1.1/ONVIF%E8%AE%BE%E5%A4%87%E5%B7%A5%E4%BD%9C%E5%8F%B0-v1.1.1-macOS-arm64.zip)
- [Release notes and checksums](docs/releases/v1.1.1.md)

This first binary release uses an ad-hoc signature and is not Apple-notarized.
If macOS blocks the first launch, Control-click the application, choose
**Open**, then confirm **Open**. You only need to do this once.

## Highlights

- Discover devices with WS-Discovery across active IPv4 interfaces.
- Add a camera manually using an IP address, host/port, or Device Service URL.
- Read device metadata and ONVIF Media1/Media2 profiles.
- Group profiles by `VideoSourceToken` to identify multi-sensor cameras.
- Classify main, sub, and auxiliary streams within each video source.
- Show codec, resolution, frame rate, bitrate, channel, and RTSP URI.
- Preview 1, 4, or 9 streams with independent stream selection.
- Preserve the source aspect ratio without stretching or cropping.
- Keep the interface responsive with isolated FFmpeg worker processes and
  connection timeouts.
- Store passwords in the operating system credential vault instead of normal
  application settings.
- Copy individual fields, complete device reports, or credential-bearing RTSP
  URLs when they are needed by another player.

## Screenshots

### Device discovery and profile inspection

![Device discovery](docs/images/discovery.png)

### Credential profiles

![Credential profiles](docs/images/credentials.png)

### Selectable runtime logs

![Runtime logs](docs/images/logs.png)

## Requirements

- Python 3.10–3.13
- macOS, Windows, or Linux with a desktop environment
- Cameras on a reachable local network with ONVIF enabled
- An ONVIF user account configured on each camera

ONVIF Deck uses a system FFmpeg installation when available. Otherwise it uses
the FFmpeg binary supplied by `imageio-ffmpeg`.

## Installation

```bash
git clone https://github.com/IceBigPig/ONVIF-Deck.git
cd ONVIF-Deck

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e .
onvif-deck
```

The source tree can also be launched directly:

```bash
python -m pip install -r requirements.txt
python run.py
```

## Basic workflow

1. Open **Credentials** and enter the default ONVIF username and password.
2. Optionally enable **Remember password** and save it to the OS credential
   vault.
3. Select **Scan devices**. Cameras that do not answer WS-Discovery can be
   added manually.
4. Select a device to inspect its identity, channels, profiles, and RTSP URIs.
5. Add the whole device or a specific profile to the preview wall.
6. Switch between 1, 4, and 9 views, then select a different stream in any
   preview tile.

The web administration account is not always an ONVIF account. If
authentication fails, enable ONVIF in the camera administration page and
create a dedicated ONVIF user.

## Credentials and copied URLs

- macOS uses Keychain, Windows uses Credential Manager, and Linux uses an
  available Secret Service/keyring backend.
- Normal settings contain usernames, profile labels, and device bindings, but
  never plaintext passwords.
- RTSP fields are redacted on screen.
- By design, copying an RTSP URL adds the selected camera username and password
  using URL encoding so the result can be pasted directly into a player.
- A copied RTSP URL therefore places plaintext credentials on the clipboard.
  Clear the clipboard after use and never paste it into an issue or log.

See [SECURITY.md](SECURITY.md) for reporting and deployment guidance.

## How stream classification works

- **Channel / lens:** profiles are grouped by
  `VideoSourceConfiguration.SourceToken`. Each distinct token is treated as a
  separate sensor or video source.
- **Main / sub stream:** quality is ranked only inside the same video source.
  The highest pixel count is the main stream and the lowest is the sub stream;
  intermediate entries are auxiliary streams.
- **Tele / wide hints:** ONVIF does not define a universal focal-length field.
  A hint is displayed only when profile, source, encoder, or token names contain
  explicit words such as `tele`, `zoom`, `wide`, or `panorama`.

## Development

```bash
python -m pip install -e ".[dev]"
ruff check src tests scripts
pytest -q
```

Launch the privacy-safe documentation demo:

```bash
python scripts/demo.py --page preview
```

Regenerate all repository screenshots:

```bash
python scripts/demo.py --capture-dir docs/images
```

Build instructions are documented in [docs/BUILDING.md](docs/BUILDING.md).

## Protocol notes and limitations

- WS-Discovery uses UDP multicast `239.255.255.250:3702`. Firewalls, guest
  Wi-Fi, AP isolation, and VLAN boundaries can prevent discovery.
- Some vendors return incomplete profiles, temporary RTSP URIs, or private
  channel conventions. ONVIF Deck preserves every readable profile and reports
  individual failures.
- The application calls read-only ONVIF operations and does not modify camera
  configuration.
- TLS certificate verification is disabled for local cameras because embedded
  devices commonly use self-signed certificates. Do not add untrusted public
  Internet URLs.
- Practical preview capacity depends on decoder performance, camera connection
  limits, and network bandwidth. Multi-view modes prefer sub streams.

## Contributing

Issues and pull requests are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md)
before submitting a change. Please remove credentials, public IPs, serial
numbers, faces, and private scenes from diagnostics and screenshots.

## License

ONVIF Deck is released under the [MIT License](LICENSE).

ONVIF is a trademark of ONVIF, Inc. This project is independent and is not
affiliated with or endorsed by ONVIF, Inc.
