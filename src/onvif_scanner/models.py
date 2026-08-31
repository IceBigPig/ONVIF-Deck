from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlsplit


@dataclass(slots=True)
class DiscoveredDevice:
    endpoint: str
    xaddrs: list[str]
    scopes: list[str] = field(default_factory=list)
    types: list[str] = field(default_factory=list)
    remote_address: str = ""

    @property
    def device_service_url(self) -> str:
        for address in self.xaddrs:
            if "device_service" in address.lower():
                return address
        return self.xaddrs[0] if self.xaddrs else ""

    @property
    def host(self) -> str:
        try:
            return urlsplit(self.device_service_url).hostname or self.remote_address
        except ValueError:
            return self.remote_address

    @property
    def display_name(self) -> str:
        prefixes = (
            "onvif://www.onvif.org/name/",
            "onvif://www.onvif.org/hardware/",
        )
        for prefix in prefixes:
            for scope in self.scopes:
                if scope.lower().startswith(prefix):
                    value = scope[len(prefix) :]
                    if value:
                        return value.replace("%20", " ")
        return self.host or "ONVIF 设备"


@dataclass(slots=True)
class DeviceInformation:
    manufacturer: str = ""
    model: str = ""
    firmware_version: str = ""
    serial_number: str = ""
    hardware_id: str = ""

    @property
    def title(self) -> str:
        return " ".join(
            part for part in (self.manufacturer, self.model) if part
        ).strip()


@dataclass(slots=True)
class StreamProfile:
    token: str
    profile_name: str
    source_token: str = ""
    source_config_name: str = ""
    encoder_name: str = ""
    encoding: str = ""
    width: int = 0
    height: int = 0
    frame_rate: float = 0.0
    bitrate_kbps: int = 0
    rtsp_uri: str = ""
    channel_label: str = ""
    lens_hint: str = ""
    stream_role: str = ""
    error: str = ""

    @property
    def resolution(self) -> str:
        return f"{self.width}×{self.height}" if self.width and self.height else "-"

    @property
    def quality_score(self) -> tuple[int, int, float]:
        return (self.width * self.height, self.bitrate_kbps, self.frame_rate)


@dataclass(slots=True)
class DeviceDetails:
    discovery: DiscoveredDevice
    information: DeviceInformation
    streams: list[StreamProfile]
    media_service_url: str = ""
