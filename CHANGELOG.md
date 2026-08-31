# Changelog

All notable changes to ONVIF Deck are documented in this file.

## [1.1.1] - 2026-08-31

### Added

- Credential-bearing RTSP URL copy actions with correct URL encoding.
- Privacy-safe documentation demo and reproducible screenshots.
- macOS Apple Silicon application bundle specification.
- English and Simplified Chinese documentation.

### Changed

- Redesigned navigation, discovery details, credential management, and logs as
  separate workspaces.
- Improved 1/4/9-view preview layout and source aspect-ratio preservation.
- Reduced packaged application size by excluding unused OpenCV/Numpy fallback
  components when bundled FFmpeg is present.

### Fixed

- FFmpeg connection and shutdown paths no longer block the UI indefinitely.
- Media2 discovery and Media1 fallback behavior across tested cameras.

## [1.0.0] - 2026-08-21

- Initial ONVIF discovery, profile inspection, and RTSP preview implementation.
