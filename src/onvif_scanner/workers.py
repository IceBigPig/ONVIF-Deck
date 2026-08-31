from __future__ import annotations

from threading import Event

from PySide6.QtCore import QThread, Signal

from .client import OnvifClient
from .discovery import discover_devices
from .models import DeviceDetails, DiscoveredDevice


class DiscoveryThread(QThread):
    device_found = Signal(object)
    scan_error = Signal(str)
    scan_complete = Signal(int)

    def __init__(self, timeout: float, parent: object | None = None) -> None:
        super().__init__(parent)
        self.timeout = timeout
        self._stop_event = Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        try:
            results = discover_devices(
                self.timeout,
                stop_event=self._stop_event,
                on_device=self.device_found.emit,
            )
            self.scan_complete.emit(len(results))
        except Exception as exc:  # noqa: BLE001 - must report any worker failure to Qt
            self.scan_error.emit(str(exc))


class DeviceQueryThread(QThread):
    query_complete = Signal(object)
    query_error = Signal(object, str)

    def __init__(
        self,
        device: DiscoveredDevice,
        username: str,
        password: str,
        parent: object | None = None,
    ) -> None:
        super().__init__(parent)
        self.device = device
        self.username = username
        self.password = password

    def run(self) -> None:
        try:
            with OnvifClient(
                self.device.device_service_url,
                username=self.username,
                password=self.password,
            ) as client:
                details: DeviceDetails = client.read_details(self.device)
            self.query_complete.emit(details)
        except Exception as exc:  # noqa: BLE001 - must report any worker failure to Qt
            self.query_error.emit(self.device, str(exc))
