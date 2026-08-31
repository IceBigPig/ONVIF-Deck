# Security Policy

## Supported versions

Security fixes are applied to the latest release on the `main` branch.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting feature for this
repository. Do not open a public issue for a vulnerability that could expose
camera credentials, private video, or network access.

Include the affected version, operating system, reproduction steps, and impact.
Replace real addresses and identifiers with documentation values before
submitting the report.

## Credential handling

- Passwords are stored through the operating system credential vault.
- QSettings stores usernames, labels, and device/profile bindings only.
- Password fields and credential-bearing RTSP URLs are redacted on screen.
- A user-requested RTSP copy operation deliberately puts the complete URL,
  including credentials, on the clipboard. Clipboard history tools may retain
  that value; clear it after use.
- Application logs must never include passwords or credential-bearing URLs.

## Network model

ONVIF Deck is intended for trusted local networks. It performs WS-Discovery,
SOAP requests, and RTSP connections directly from the desktop. It does not use
a cloud service or send telemetry.

TLS certificate validation is disabled for camera requests because embedded
devices commonly use self-signed certificates. Do not add untrusted Internet
hosts, and isolate cameras on an appropriate VLAN where possible.
