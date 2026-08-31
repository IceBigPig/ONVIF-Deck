from __future__ import annotations

import hashlib
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QSettings

SERVICE_NAME = "ONVIF Camera Scanner"
DEFAULT_PROFILE = "default"


class CredentialStoreError(RuntimeError):
    pass


@dataclass(slots=True)
class Credential:
    profile_id: str = DEFAULT_PROFILE
    label: str = "默认摄像头账号"
    username: str = ""
    password: str = ""
    remember: bool = True


class CredentialStore:
    """Store metadata in QSettings and passwords in the OS credential vault."""

    def __init__(
        self,
        settings: QSettings | None = None,
        vault: Any | None = None,
    ) -> None:
        self.settings = settings or QSettings()
        if vault is None:
            try:
                import keyring

                vault = keyring
            except ImportError:
                vault = None
        self.vault = vault

    @staticmethod
    def device_profile_id(device_key: str) -> str:
        digest = hashlib.sha256(device_key.encode("utf-8")).hexdigest()[:20]
        return f"device_{digest}"

    @staticmethod
    def _as_bool(value: object, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def load(self, profile_id: str = DEFAULT_PROFILE) -> Credential:
        prefix = f"credentials/{profile_id}"
        label_default = (
            "默认摄像头账号" if profile_id == DEFAULT_PROFILE else "当前设备专用账号"
        )
        username = str(self.settings.value(f"{prefix}/username", "") or "")
        remember = self._as_bool(
            self.settings.value(f"{prefix}/remember", True), default=True
        )
        label = str(
            self.settings.value(f"{prefix}/label", label_default) or label_default
        )
        password = ""
        if remember and self.vault is not None:
            try:
                password = self.vault.get_password(SERVICE_NAME, profile_id) or ""
            except Exception:  # noqa: BLE001 - credential backends vary by platform
                password = ""
        return Credential(profile_id, label, username, password, remember)

    def save(self, credential: Credential) -> None:
        prefix = f"credentials/{credential.profile_id}"
        self.settings.setValue(f"{prefix}/label", credential.label)
        self.settings.setValue(f"{prefix}/username", credential.username)
        self.settings.setValue(f"{prefix}/remember", credential.remember)
        if credential.remember:
            if self.vault is None:
                raise CredentialStoreError(
                    "系统凭据存储不可用；为安全起见，密码没有写入普通配置文件"
                )
            try:
                self.vault.set_password(
                    SERVICE_NAME, credential.profile_id, credential.password
                )
            except Exception as exc:
                raise CredentialStoreError(f"无法写入系统钥匙串：{exc}") from exc
        elif self.vault is not None:
            with suppress(Exception):
                self.vault.delete_password(SERVICE_NAME, credential.profile_id)
        self.settings.sync()

    def bind_device(self, device_key: str, profile_id: str) -> None:
        slot = self.device_profile_id(device_key)
        self.settings.setValue(f"devices/{slot}/credential_profile", profile_id)
        self.settings.sync()

    def profile_for_device(self, device_key: str) -> str:
        slot = self.device_profile_id(device_key)
        return str(
            self.settings.value(f"devices/{slot}/credential_profile", DEFAULT_PROFILE)
            or DEFAULT_PROFILE
        )

    def resolve(self, device_key: str) -> Credential:
        return self.load(self.profile_for_device(device_key))

    def has_profile(self, profile_id: str) -> bool:
        return self.settings.contains(f"credentials/{profile_id}/username")
