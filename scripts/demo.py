"""Launch ONVIF Deck with reproducible, privacy-safe demonstration data.

This helper never contacts a camera. It is used to review the UI and generate
the screenshots published in the repository documentation.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QRectF, QSettings, Qt, QTemporaryDir, QTimer
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QApplication

from onvif_scanner.credentials import DEFAULT_PROFILE, Credential, CredentialStore
from onvif_scanner.models import (
    DeviceDetails,
    DeviceInformation,
    DiscoveredDevice,
    StreamProfile,
)
from onvif_scanner.ui import MainWindow


class MemoryVault:
    """Minimal keyring replacement used only by the documentation demo."""

    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.values.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.values[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        self.values.pop((service, username), None)


def make_stream(
    host: str,
    token: str,
    source: str,
    channel: str,
    role: str,
    encoding: str,
    width: int,
    height: int,
    fps: float,
    bitrate: int,
) -> StreamProfile:
    channel_number = token.split("-")[0].removeprefix("ch")
    stream_number = "01" if role == "主码流" else "02"
    return StreamProfile(
        token=token,
        profile_name=f"Profile_{token}",
        source_token=source,
        source_config_name=channel,
        encoder_name=f"{encoding} {role}",
        encoding=encoding,
        width=width,
        height=height,
        frame_rate=fps,
        bitrate_kbps=bitrate,
        rtsp_uri=f"rtsp://{host}/Streaming/Channels/{channel_number}{stream_number}",
        channel_label=channel,
        stream_role=role,
    )


def make_device(
    number: int,
    name: str,
    manufacturer: str,
    model: str,
    streams: list[StreamProfile],
) -> tuple[str, DiscoveredDevice, DeviceDetails]:
    host = f"192.0.2.{10 + number}"
    key = f"urn:uuid:onvif-deck-demo-{number}"
    service = f"http://{host}/onvif/device_service"
    device = DiscoveredDevice(
        endpoint=key,
        xaddrs=[service],
        scopes=[f"onvif://www.onvif.org/name/{name.replace(' ', '%20')}"],
        types=["dn:NetworkVideoTransmitter"],
        remote_address=host,
    )
    information = DeviceInformation(
        manufacturer=manufacturer,
        model=model,
        firmware_version=f"V1.{number + 2}.0",
        serial_number=f"DEMO-2026-{number + 1:04d}",
        hardware_id=f"DEMO-{model}",
    )
    details = DeviceDetails(
        discovery=device,
        information=information,
        streams=streams,
        media_service_url=f"http://{host}/onvif/media_service",
    )
    return key, device, details


def demo_devices() -> list[tuple[str, DiscoveredDevice, DeviceDetails]]:
    hosts = [f"192.0.2.{number}" for number in range(10, 14)]
    devices = [
        make_device(
            0,
            "North Lobby",
            "ArcVision",
            "AV-Dome-4K",
            [
                make_stream(
                    hosts[0], "ch1-main", "sensor-wide", "通道 1 · 广角",
                    "主码流", "H265", 3840, 2160, 25, 6144,
                ),
                make_stream(
                    hosts[0], "ch1-sub", "sensor-wide", "通道 1 · 广角",
                    "子码流", "H264", 640, 360, 15, 768,
                ),
            ],
        ),
        make_device(
            1,
            "Parking PTZ",
            "VisionCraft",
            "VC-PTZ-30X",
            [
                make_stream(
                    hosts[1], "ch1-main", "sensor-wide", "通道 1 · 广角",
                    "主码流", "H265", 2560, 1440, 25, 4096,
                ),
                make_stream(
                    hosts[1], "ch1-sub", "sensor-wide", "通道 1 · 广角",
                    "子码流", "H264", 640, 360, 15, 768,
                ),
                make_stream(
                    hosts[1], "ch2-main", "sensor-tele", "通道 2 · 长焦",
                    "主码流", "H265", 1920, 1080, 25, 3072,
                ),
                make_stream(
                    hosts[1], "ch2-sub", "sensor-tele", "通道 2 · 长焦",
                    "子码流", "H264", 640, 360, 15, 640,
                ),
            ],
        ),
        make_device(
            2,
            "Warehouse West",
            "OpenCam",
            "OC-Bullet-2MP",
            [
                make_stream(
                    hosts[2], "ch1-main", "sensor-1", "通道 1",
                    "主码流", "H264", 1920, 1080, 20, 3072,
                ),
                make_stream(
                    hosts[2], "ch1-sub", "sensor-1", "通道 1",
                    "子码流", "H264", 640, 360, 15, 512,
                ),
            ],
        ),
        make_device(
            3,
            "Loading Dock",
            "SafeSight",
            "SS-Turret-5MP",
            [
                make_stream(
                    hosts[3], "ch1-main", "sensor-1", "通道 1",
                    "主码流", "H265", 2592, 1944, 20, 4096,
                ),
                make_stream(
                    hosts[3], "ch1-sub", "sensor-1", "通道 1",
                    "子码流", "H264", 640, 480, 15, 640,
                ),
            ],
        ),
    ]
    return devices


def demo_frame(index: int, title: str) -> QImage:
    image = QImage(1280, 720, QImage.Format.Format_RGB32)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    palettes = [
        ("#243b55", "#3f6f8f", "#74c0a7"),
        ("#3a3042", "#73627e", "#d8a45d"),
        ("#263b35", "#3f695d", "#8cc6a8"),
        ("#33415c", "#5c677d", "#d7b377"),
    ]
    start, end, accent = palettes[index % len(palettes)]
    gradient = QLinearGradient(0, 0, image.width(), image.height())
    gradient.setColorAt(0, QColor(start))
    gradient.setColorAt(1, QColor(end))
    painter.fillRect(image.rect(), gradient)

    painter.setPen(QPen(QColor(255, 255, 255, 32), 2))
    for x in range(80, 1280, 120):
        painter.drawLine(x, 0, x, 720)
    for y in range(70, 720, 90):
        painter.drawLine(0, y, 1280, y)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(accent))
    painter.drawRoundedRect(QRectF(110, 150, 360, 350), 24, 24)
    painter.setBrush(QColor(8, 18, 30, 150))
    painter.drawRoundedRect(QRectF(540, 220, 620, 280), 24, 24)
    painter.setBrush(QColor(255, 255, 255, 46))
    painter.drawRoundedRect(QRectF(590, 270, 170, 170), 18, 18)
    painter.drawRoundedRect(QRectF(800, 270, 300, 72), 15, 15)
    painter.drawRoundedRect(QRectF(800, 368, 220, 72), 15, 15)

    painter.setPen(QColor("#ffffff"))
    painter.setFont(QFont("Arial", 25, QFont.Weight.Bold))
    painter.drawText(QRectF(55, 45, 900, 50), title.upper())
    painter.setFont(QFont("Arial", 18))
    painter.setPen(QColor(255, 255, 255, 190))
    painter.drawText(QRectF(55, 100, 500, 40), "ONVIF DECK · DEMO CAMERA")
    painter.setFont(QFont("Arial", 16, QFont.Weight.Bold))
    painter.drawText(
        QRectF(890, 655, 330, 32),
        Qt.AlignmentFlag.AlignRight,
        "SYNTHETIC DEMO",
    )
    painter.end()
    return image


def populate_window(window: MainWindow) -> None:
    credential = Credential(
        profile_id=DEFAULT_PROFILE,
        label="默认摄像头账号",
        username="demo-operator",
        password="demo-password",
        remember=True,
    )
    window.session_credentials[DEFAULT_PROFILE] = credential
    window.credentials_panel.set_credential(credential)

    devices = demo_devices()
    for key, device, details in devices:
        window.devices[key] = device
        window.details[key] = details
        window.device_list.add_device(key, device).set_details(details)
        label = f"{device.display_name}  ·  {device.host}"
        window.preview_device_combo.addItem(label, key)
        window.credential_device_combo.addItem(label, key)

    selected_key = devices[1][0]
    window.device_list.select_key(selected_key)
    window.show_device_details(selected_key)
    window._update_summary()
    window.online_chip.setText("演示数据")
    window.statusBar().showMessage("演示模式 · 所有设备和画面均为合成数据")

    for key, device, details in devices:
        window.log(f"发现演示设备：{device.host} → {device.device_service_url}")
        window.log(f"读取成功：{device.host}，{len(details.streams)} 路码流")
    window.log("演示模式不会访问网络、摄像头或系统钥匙串")

    window.video_wall.set_mode(4)
    for index, (key, device, details) in enumerate(devices):
        tile = window.video_wall.tiles[index]
        tile.stop()
        tile.device_key = key
        tile.details = details
        tile.username = "demo-operator"
        tile.password = "demo-password"
        tile._paused = True
        tile.title_label.setText(device.display_name)
        tile.stream_combo.blockSignals(True)
        tile.stream_combo.clear()
        for stream in details.streams:
            tile.stream_combo.addItem(
                " · ".join(
                    (stream.channel_label, stream.stream_role, stream.encoding)
                ),
                stream.token,
            )
        substream_index = next(
            (
                stream_index
                for stream_index, stream in enumerate(details.streams)
                if stream.stream_role == "子码流"
            ),
            0,
        )
        tile.stream_combo.setCurrentIndex(substream_index)
        tile.stream_combo.blockSignals(False)
        tile._set_controls_enabled(True)
        tile.surface.show_image(demo_frame(index, device.display_name))
        stream = details.streams[substream_index]
        tile.meta_label.setText(f"{stream.resolution} · {stream.frame_rate:g} FPS")
        tile.state_label.setText("演示画面")

    window.credential_device_combo.setCurrentIndex(2)
    window.credentials_panel.set_credential(credential)


def capture_pages(
    app: QApplication, window: MainWindow, output_directory: Path
) -> None:
    output_directory.mkdir(parents=True, exist_ok=True)
    pages = (
        ("discovery", 0),
        ("preview", 1),
        ("credentials", 2),
        ("logs", 3),
    )
    for name, page_index in pages:
        window._activate_nav(page_index)
        app.processEvents()
        if page_index == 1:
            window.video_wall._fit_tiles()
            app.processEvents()
        window.grab().save(str(output_directory / f"{name}.png"), "PNG")
    window.close()
    app.quit()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--page",
        choices=("discovery", "preview", "credentials", "logs"),
        default="discovery",
        help="Page shown when running interactively.",
    )
    parser.add_argument(
        "--capture-dir",
        type=Path,
        help="Capture every documentation page to this directory and exit.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("ONVIF Deck Documentation Demo")
    app.setOrganizationName("IceBigPig")
    app.setStyle("Fusion")
    temporary_directory = QTemporaryDir()
    settings = QSettings(
        str(Path(temporary_directory.path()) / "demo.ini"),
        QSettings.Format.IniFormat,
    )
    window = MainWindow(CredentialStore(settings, MemoryVault()))
    window.resize(1580, 980)
    populate_window(window)
    page_names = {"discovery": 0, "preview": 1, "credentials": 2, "logs": 3}
    window._activate_nav(page_names[args.page])
    window.show()
    if args.capture_dir:
        QTimer.singleShot(500, lambda: capture_pages(app, window, args.capture_dir))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
