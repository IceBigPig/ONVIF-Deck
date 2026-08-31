from __future__ import annotations

from PySide6.QtCore import QMimeData, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QDrag, QImage, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .credentials import DEFAULT_PROFILE, Credential
from .models import DeviceDetails, DiscoveredDevice, StreamProfile
from .preview import PreviewThread, safe_display_uri, uri_with_credentials

DEVICE_MIME = "application/x-onvif-device-key"


def copy_text(value: str) -> None:
    QApplication.clipboard().setText(value)


def stream_text(
    stream: StreamProfile, username: str = "", password: str = ""
) -> str:
    return "\n".join(
        (
            f"通道: {stream.channel_label}",
            f"码流: {stream.stream_role}",
            f"Profile: {stream.profile_name} ({stream.token})",
            f"编码: {stream.encoding or '-'}",
            f"分辨率: {stream.resolution}",
            f"帧率: {stream.frame_rate:g} FPS" if stream.frame_rate else "帧率: -",
            f"码率: {stream.bitrate_kbps} kbps" if stream.bitrate_kbps else "码率: -",
            f"RTSP: {uri_with_credentials(stream.rtsp_uri, username, password)}"
            if stream.rtsp_uri
            else f"RTSP: {stream.error or '-'}",
        )
    )


def device_text(
    details: DeviceDetails, username: str = "", password: str = ""
) -> str:
    info = details.information
    lines = [
        f"设备名称: {details.discovery.display_name}",
        f"IP 地址: {details.discovery.host}",
        f"厂商 / 型号: {info.title or '-'}",
        f"固件版本: {info.firmware_version or '-'}",
        f"序列号: {info.serial_number or '-'}",
        f"硬件标识: {info.hardware_id or '-'}",
        f"设备服务: {details.discovery.device_service_url}",
        f"媒体服务: {details.media_service_url or '-'}",
    ]
    for index, stream in enumerate(details.streams, start=1):
        lines.extend(
            ("", f"[码流 {index}]", stream_text(stream, username, password))
        )
    return "\n".join(lines)


class PreviewSurface(QLabel):
    def __init__(self, text: str = "拖入摄像头开始预览") -> None:
        super().__init__(text)
        self.setObjectName("videoSurface")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(220, 130)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._source_pixmap: QPixmap | None = None

    def show_image(self, image: QImage) -> None:
        self._source_pixmap = QPixmap.fromImage(image)
        self._refresh()

    def set_placeholder(self, message: str) -> None:
        self._source_pixmap = None
        self.clear()
        self.setText(message)

    def _refresh(self) -> None:
        if self._source_pixmap is None:
            return
        self.setPixmap(
            self._source_pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)
        self._refresh()


class DeviceCard(QFrame):
    clicked = Signal(str)
    add_requested = Signal(str)
    copy_requested = Signal(str)
    read_requested = Signal(str)

    def __init__(self, key: str, device: DiscoveredDevice) -> None:
        super().__init__()
        self.key = key
        self.device = device
        self.details: DeviceDetails | None = None
        self.setObjectName("deviceCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 10, 10)
        layout.setSpacing(5)
        top = QHBoxLayout()
        self.online_dot = QLabel("●")
        self.online_dot.setObjectName("onlineDot")
        self.name_label = QLabel(device.display_name)
        self.name_label.setObjectName("deviceName")
        self.name_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.stream_badge = QLabel("待读取")
        self.stream_badge.setObjectName("badge")
        top.addWidget(self.online_dot)
        top.addWidget(self.name_label, 1)
        top.addWidget(self.stream_badge)
        layout.addLayout(top)

        middle = QHBoxLayout()
        self.ip_label = QLabel(device.host)
        self.ip_label.setObjectName("muted")
        self.ip_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.model_label = QLabel("ONVIF 设备")
        self.model_label.setObjectName("muted")
        self.model_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.model_label.setMaximumWidth(138)
        self.model_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        middle.addWidget(self.ip_label)
        middle.addWidget(self.model_label, 1)
        layout.addLayout(middle)

        actions = QHBoxLayout()
        actions.setSpacing(5)
        self.status_label = QLabel("已发现，待读取")
        self.status_label.setObjectName("cardStatus")
        self.status_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.read_button = QToolButton()
        self.read_button.setText("↻")
        self.read_button.setFixedWidth(32)
        self.read_button.setToolTip("读取设备信息")
        self.copy_button = QToolButton()
        self.copy_button.setText("复制")
        self.copy_button.setFixedWidth(46)
        self.copy_button.setToolTip("复制设备信息")
        self.add_button = QPushButton("预览")
        self.add_button.setFixedWidth(54)
        self.add_button.setToolTip("加入预览")
        self.add_button.setObjectName("miniPrimary")
        actions.addWidget(self.status_label, 1)
        actions.addWidget(self.read_button)
        actions.addWidget(self.copy_button)
        actions.addWidget(self.add_button)
        layout.addLayout(actions)

        self.add_button.clicked.connect(lambda: self.add_requested.emit(self.key))
        self.copy_button.clicked.connect(lambda: self.copy_requested.emit(self.key))
        self.read_button.clicked.connect(lambda: self.read_requested.emit(self.key))

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)

    def set_status(self, message: str, error: bool = False) -> None:
        self.status_label.setText(message)
        self.status_label.setProperty("error", error)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def set_details(self, details: DeviceDetails) -> None:
        self.details = details
        info = details.information
        self.name_label.setText(details.discovery.display_name or info.title)
        self.model_label.setText(info.title or "ONVIF 设备")
        self.model_label.setToolTip(info.title or "ONVIF 设备")
        channels = len(
            {
                stream.source_token or stream.source_config_name
                for stream in details.streams
            }
        )
        self.stream_badge.setText(f"{channels} 通道 · {len(details.streams)} 码流")
        self.set_status("在线")

    def mousePressEvent(self, event: object) -> None:
        self.clicked.emit(self.key)
        super().mousePressEvent(event)


class DeviceList(QListWidget):
    device_selected = Signal(str)
    add_requested = Signal(str)
    copy_requested = Signal(str)
    read_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("deviceList")
        self.setSpacing(6)
        self.setDragEnabled(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.cards: dict[str, DeviceCard] = {}
        self.items: dict[str, QListWidgetItem] = {}
        self.itemSelectionChanged.connect(self._selection_changed)
        self.customContextMenuRequested.connect(self._context_menu)

    def add_device(self, key: str, device: DiscoveredDevice) -> DeviceCard:
        if key in self.cards:
            return self.cards[key]
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, key)
        item.setSizeHint(QSize(250, 112))
        card = DeviceCard(key, device)
        card.clicked.connect(self.select_key)
        card.add_requested.connect(self.add_requested)
        card.copy_requested.connect(self.copy_requested)
        card.read_requested.connect(self.read_requested)
        self.addItem(item)
        self.setItemWidget(item, card)
        self.cards[key] = card
        self.items[key] = item
        if self.count() == 1:
            self.setCurrentItem(item)
        return card

    def select_key(self, key: str) -> None:
        item = self.items.get(key)
        if item:
            self.setCurrentItem(item)

    def selected_key(self) -> str:
        item = self.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole) or "") if item else ""

    def filter(self, query: str) -> None:
        query = query.strip().lower()
        for key, item in self.items.items():
            card = self.cards[key]
            haystack = (
                f"{card.device.host} {card.name_label.text()} {card.model_label.text()}"
            ).lower()
            item.setHidden(bool(query and query not in haystack))

    def _selection_changed(self) -> None:
        selected = self.selected_key()
        for key, card in self.cards.items():
            card.set_selected(key == selected)
        if selected:
            self.device_selected.emit(selected)

    def startDrag(self, supported_actions: Qt.DropAction) -> None:
        key = self.selected_key()
        if not key:
            return
        mime = QMimeData()
        mime.setData(DEVICE_MIME, key.encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)

    def _context_menu(self, position: object) -> None:
        item = self.itemAt(position)
        if not item:
            return
        self.setCurrentItem(item)
        key = self.selected_key()
        menu = QMenu(self)
        add_action = QAction("加入预览", menu)
        read_action = QAction("重新读取", menu)
        copy_action = QAction("复制设备信息", menu)
        add_action.triggered.connect(lambda: self.add_requested.emit(key))
        read_action.triggered.connect(lambda: self.read_requested.emit(key))
        copy_action.triggered.connect(lambda: self.copy_requested.emit(key))
        menu.addAction(add_action)
        menu.addAction(read_action)
        menu.addSeparator()
        menu.addAction(copy_action)
        menu.exec(self.viewport().mapToGlobal(position))


class CopyField(QFrame):
    def __init__(self, label: str) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(8)
        name = QLabel(label)
        name.setObjectName("fieldName")
        name.setFixedWidth(82)
        self.value_label = QLabel("-")
        self.value_label.setObjectName("fieldValue")
        self.value_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.value_label.setWordWrap(True)
        copy_button = QToolButton()
        copy_button.setText("⧉")
        copy_button.setToolTip(f"复制{label}")
        copy_button.clicked.connect(lambda: copy_text(self.value_label.text()))
        layout.addWidget(name)
        layout.addWidget(self.value_label, 1)
        layout.addWidget(copy_button)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value or "-")


class SecureUriField(QLineEdit):
    """Show a redacted RTSP URI while copying its credential-bearing form."""

    def __init__(
        self,
        uri: str = "",
        username: str = "",
        password: str = "",
        fallback: str = "未获取 RTSP URI",
    ) -> None:
        super().__init__()
        self.raw_uri = uri
        self.username = username
        self.password = password
        self.fallback = fallback
        self.setObjectName("streamUri")
        self.setReadOnly(True)
        self._refresh_display()

    def _refresh_display(self) -> None:
        value = safe_display_uri(self.raw_uri) if self.raw_uri else self.fallback
        self.setText(value)
        self.setToolTip(
            "界面已隐藏密码；复制时自动加入当前设备凭据"
            if self.raw_uri
            else value
        )

    def set_credentials(self, username: str, password: str) -> None:
        self.username = username
        self.password = password

    def copy(self) -> None:
        if self.raw_uri:
            copy_text(uri_with_credentials(self.raw_uri, self.username, self.password))
            return
        super().copy()

    def keyPressEvent(self, event: object) -> None:
        if event.matches(QKeySequence.StandardKey.Copy):
            self.copy()
            event.accept()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event: object) -> None:
        menu = QMenu(self)
        copy_action = menu.addAction("复制 URL（含凭据）")
        copy_action.setEnabled(bool(self.raw_uri))
        copy_action.triggered.connect(self.copy)
        menu.addAction("全选", self.selectAll)
        menu.exec(event.globalPos())


class DetailsDrawer(QFrame):
    close_requested = Signal()
    credential_profile_changed = Signal(str)
    save_credentials_requested = Signal()
    test_connection_requested = Signal()
    add_stream_requested = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("detailsDrawer")
        self.setMinimumWidth(330)
        self.setMaximumWidth(390)
        self.device_key = ""
        self.details: DeviceDetails | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(10)
        header = QHBoxLayout()
        title = QLabel("设备详情")
        title.setObjectName("drawerTitle")
        self.copy_all_button = QPushButton("复制全部")
        self.copy_all_button.setObjectName("ghostButton")
        close_button = QToolButton()
        close_button.setText("×")
        close_button.setToolTip("收起详情")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.copy_all_button)
        header.addWidget(close_button)
        outer.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        self.body_layout = QVBoxLayout(body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(10)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        basic_card, basic_layout = self._card("基本信息")
        self.fields = {
            "name": CopyField("设备名称"),
            "ip": CopyField("IP 地址"),
            "model": CopyField("厂商 / 型号"),
            "firmware": CopyField("固件版本"),
            "serial": CopyField("序列号"),
            "service": CopyField("服务地址"),
        }
        for field in self.fields.values():
            basic_layout.addWidget(field)
        self.body_layout.addWidget(basic_card)

        stream_card, self.stream_layout = self._card("码流配置")
        self.stream_layout.setSpacing(6)
        self.body_layout.addWidget(stream_card)

        credential_card, credential_layout = self._card("认证配置")
        self.profile_combo = QComboBox()
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("ONVIF 用户名")
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("密码")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.show_password_button = QCheckBox("显示密码")
        self.remember_check = QCheckBox("记住密码")
        self.remember_check.setChecked(True)
        keychain_hint = QLabel("密码安全存储于系统钥匙串，不写入普通配置文件")
        keychain_hint.setObjectName("hint")
        keychain_hint.setWordWrap(True)
        credential_layout.addWidget(QLabel("凭据配置"))
        credential_layout.addWidget(self.profile_combo)
        credential_layout.addWidget(QLabel("用户名"))
        credential_layout.addWidget(self.username_edit)
        credential_layout.addWidget(QLabel("密码"))
        credential_layout.addWidget(self.password_edit)
        options = QHBoxLayout()
        options.addWidget(self.remember_check)
        options.addWidget(self.show_password_button)
        options.addStretch(1)
        credential_layout.addLayout(options)
        credential_layout.addWidget(keychain_hint)
        credential_actions = QHBoxLayout()
        self.save_credentials_button = QPushButton("保存凭据")
        self.save_credentials_button.setObjectName("primary")
        self.test_connection_button = QPushButton("测试连接")
        credential_actions.addWidget(self.save_credentials_button)
        credential_actions.addWidget(self.test_connection_button)
        credential_layout.addLayout(credential_actions)
        self.body_layout.addWidget(credential_card)
        self.body_layout.addStretch(1)

        close_button.clicked.connect(self.close_requested)
        self.copy_all_button.clicked.connect(self.copy_all)
        self.profile_combo.currentIndexChanged.connect(self._profile_changed)
        self.show_password_button.toggled.connect(self._toggle_password)
        self.save_credentials_button.clicked.connect(self.save_credentials_requested)
        self.test_connection_button.clicked.connect(self.test_connection_requested)

    @staticmethod
    def _card(title: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("drawerCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        heading = QLabel(title)
        heading.setObjectName("cardHeading")
        layout.addWidget(heading)
        return card, layout

    def set_device(
        self,
        key: str,
        device: DiscoveredDevice,
        details: DeviceDetails | None,
        device_profile_exists: bool,
    ) -> None:
        self.device_key = key
        self.details = details
        info = details.information if details else None
        self.fields["name"].set_value(device.display_name)
        self.fields["ip"].set_value(device.host)
        self.fields["model"].set_value(info.title if info else "待读取")
        self.fields["firmware"].set_value(info.firmware_version if info else "-")
        self.fields["serial"].set_value(info.serial_number if info else "-")
        self.fields["service"].set_value(device.device_service_url)
        self._populate_streams(details.streams if details else [])

        current_data = self.profile_combo.currentData()
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItem("默认摄像头账号", DEFAULT_PROFILE)
        device_profile = f"device:{key}"
        label = "当前设备专用账号" + (" · 已保存" if device_profile_exists else "")
        self.profile_combo.addItem(label, device_profile)
        index = self.profile_combo.findData(current_data)
        self.profile_combo.setCurrentIndex(max(0, index))
        self.profile_combo.blockSignals(False)

    def _populate_streams(self, streams: list[StreamProfile]) -> None:
        while self.stream_layout.count() > 1:
            item = self.stream_layout.takeAt(1)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        if not streams:
            empty = QLabel("读取设备后显示主码流、子码流和 RTSP 信息")
            empty.setObjectName("hint")
            empty.setWordWrap(True)
            self.stream_layout.addWidget(empty)
            return
        for stream in streams:
            row = QFrame()
            row.setObjectName("streamRow")
            layout = QHBoxLayout(row)
            layout.setContentsMargins(8, 7, 6, 7)
            dot = QLabel("●")
            dot.setObjectName("onlineDot")
            name = QLabel(stream.stream_role or stream.profile_name)
            name.setObjectName("streamName")
            meta = QLabel(
                f"{stream.encoding or '-'}  {stream.resolution}  "
                + (f"{stream.frame_rate:g} FPS" if stream.frame_rate else "")
            )
            meta.setObjectName("muted")
            meta.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            copy_button = QToolButton()
            copy_button.setText("⧉")
            copy_button.setToolTip("复制码流信息")
            add_button = QToolButton()
            add_button.setText("＋")
            add_button.setToolTip("将此码流加入预览")
            copy_button.clicked.connect(
                lambda _checked=False, stream=stream: copy_text(
                    stream_text(
                        stream,
                        self.username_edit.text().strip(),
                        self.password_edit.text(),
                    )
                )
            )
            add_button.clicked.connect(
                lambda _checked=False, stream=stream: self.add_stream_requested.emit(
                    stream
                )
            )
            layout.addWidget(dot)
            layout.addWidget(name)
            layout.addWidget(meta, 1)
            layout.addWidget(copy_button)
            layout.addWidget(add_button)
            self.stream_layout.addWidget(row)

    def set_credential(self, credential: Credential) -> None:
        self.username_edit.setText(credential.username)
        self.password_edit.setText(credential.password)
        self.remember_check.setChecked(credential.remember)

    def current_profile_id(self) -> str:
        data = str(self.profile_combo.currentData() or DEFAULT_PROFILE)
        if data.startswith("device:"):
            return data
        return DEFAULT_PROFILE

    def current_credential(self, profile_id: str) -> Credential:
        label = (
            "默认摄像头账号" if profile_id == DEFAULT_PROFILE else "当前设备专用账号"
        )
        return Credential(
            profile_id=profile_id,
            label=label,
            username=self.username_edit.text().strip(),
            password=self.password_edit.text(),
            remember=self.remember_check.isChecked(),
        )

    def _profile_changed(self) -> None:
        self.credential_profile_changed.emit(self.current_profile_id())

    def _toggle_password(self, visible: bool) -> None:
        mode = QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        self.password_edit.setEchoMode(mode)

    def copy_all(self) -> None:
        if self.details:
            copy_text(
                device_text(
                    self.details,
                    self.username_edit.text().strip(),
                    self.password_edit.text(),
                )
            )
            return
        values = [field.value_label.text() for field in self.fields.values()]
        copy_text("\n".join(values))


class DeviceInspector(QFrame):
    """Wide device detail view used by the discovery page."""

    refresh_requested = Signal(str)
    copy_requested = Signal(str)
    add_requested = Signal(str)
    add_stream_requested = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("deviceInspector")
        self.device_key = ""
        self.details: DeviceDetails | None = None
        self.username = ""
        self.password = ""
        self.uri_fields: list[SecureUriField] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(12)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        self.title_label = QLabel("选择一台设备")
        self.title_label.setObjectName("inspectorTitle")
        self.subtitle_label = QLabel("从左侧设备列表查看完整 ONVIF 与码流信息")
        self.subtitle_label.setObjectName("muted")
        title_box.addWidget(self.title_label)
        title_box.addWidget(self.subtitle_label)
        self.copy_button = QPushButton("复制全部")
        self.refresh_button = QPushButton("重新读取")
        self.preview_button = QPushButton("加入预览")
        self.preview_button.setObjectName("primary")
        header.addLayout(title_box, 1)
        header.addWidget(self.copy_button)
        header.addWidget(self.refresh_button)
        header.addWidget(self.preview_button)
        outer.addLayout(header)

        self.empty_state = QFrame()
        self.empty_state.setObjectName("emptyState")
        empty_layout = QVBoxLayout(self.empty_state)
        empty_layout.setContentsMargins(24, 24, 24, 24)
        empty_layout.addStretch(1)
        empty_icon = QLabel("◎")
        empty_icon.setObjectName("emptyIcon")
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_title = QLabel("尚未选择设备")
        empty_title.setObjectName("emptyTitle")
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_hint = QLabel("扫描完成后选择左侧设备，可查看基础信息、通道和全部码流")
        empty_hint.setObjectName("hint")
        empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_hint.setWordWrap(True)
        empty_layout.addWidget(empty_icon)
        empty_layout.addWidget(empty_title)
        empty_layout.addWidget(empty_hint)
        empty_layout.addStretch(1)
        outer.addWidget(self.empty_state, 1)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(12)

        overview = QFrame()
        overview.setObjectName("contentCard")
        overview_layout = QVBoxLayout(overview)
        overview_layout.setContentsMargins(14, 12, 14, 14)
        overview_layout.setSpacing(8)
        overview_layout.addWidget(self._heading("设备信息", "可选择文本或使用字段复制按钮"))
        field_grid = QGridLayout()
        field_grid.setContentsMargins(0, 0, 0, 0)
        field_grid.setHorizontalSpacing(16)
        field_grid.setVerticalSpacing(2)
        self.fields = {
            "name": CopyField("设备名称"),
            "ip": CopyField("IP 地址"),
            "model": CopyField("厂商 / 型号"),
            "firmware": CopyField("固件版本"),
            "serial": CopyField("序列号"),
            "service": CopyField("服务地址"),
        }
        for index, field in enumerate(self.fields.values()):
            field_grid.addWidget(field, index // 2, index % 2)
        overview_layout.addLayout(field_grid)
        body_layout.addWidget(overview)

        streams = QFrame()
        streams.setObjectName("contentCard")
        self.stream_layout = QVBoxLayout(streams)
        self.stream_layout.setContentsMargins(14, 12, 14, 14)
        self.stream_layout.setSpacing(8)
        self.stream_layout.addWidget(
            self._heading("通道与码流", "每路码流可单独复制或加入预览")
        )
        body_layout.addWidget(streams)
        body_layout.addStretch(1)
        self.scroll.setWidget(body)
        self.scroll.setVisible(False)
        outer.addWidget(self.scroll, 1)

        self.copy_button.clicked.connect(
            lambda: self.copy_requested.emit(self.device_key)
        )
        self.refresh_button.clicked.connect(
            lambda: self.refresh_requested.emit(self.device_key)
        )
        self.preview_button.clicked.connect(
            lambda: self.add_requested.emit(self.device_key)
        )
        self._set_actions_enabled(False)

    @staticmethod
    def _heading(title: str, hint: str) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 2)
        label = QLabel(title)
        label.setObjectName("cardHeading")
        helper = QLabel(hint)
        helper.setObjectName("hint")
        layout.addWidget(label)
        layout.addStretch(1)
        layout.addWidget(helper)
        return widget

    def _set_actions_enabled(self, enabled: bool) -> None:
        self.copy_button.setEnabled(enabled)
        self.refresh_button.setEnabled(enabled)
        self.preview_button.setEnabled(enabled)

    def set_credentials(self, username: str, password: str) -> None:
        self.username = username
        self.password = password
        for field in self.uri_fields:
            field.set_credentials(username, password)

    def set_device(
        self,
        key: str,
        device: DiscoveredDevice,
        details: DeviceDetails | None,
    ) -> None:
        self.device_key = key
        self.details = details
        info = details.information if details else None
        self.title_label.setText(device.display_name)
        self.subtitle_label.setText(
            f"{device.host}  ·  {info.title if info else '设备信息待读取'}"
        )
        self.fields["name"].set_value(device.display_name)
        self.fields["ip"].set_value(device.host)
        self.fields["model"].set_value(info.title if info else "待读取")
        self.fields["firmware"].set_value(info.firmware_version if info else "-")
        self.fields["serial"].set_value(info.serial_number if info else "-")
        self.fields["service"].set_value(device.device_service_url)
        self._populate_streams(details.streams if details else [])
        self.empty_state.setVisible(False)
        self.scroll.setVisible(True)
        self._set_actions_enabled(True)

    def _populate_streams(self, streams: list[StreamProfile]) -> None:
        self.uri_fields.clear()
        while self.stream_layout.count() > 1:
            item = self.stream_layout.takeAt(1)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        if not streams:
            empty = QLabel("正在等待设备返回 Profile 与 RTSP 信息…")
            empty.setObjectName("hint")
            empty.setWordWrap(True)
            self.stream_layout.addWidget(empty)
            return
        for stream in streams:
            row = QFrame()
            row.setObjectName("wideStreamRow")
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(12, 9, 10, 9)
            row_layout.setSpacing(7)
            top = QHBoxLayout()
            role = QLabel(stream.stream_role or "码流")
            role.setObjectName("roleBadge")
            channel = QLabel(stream.channel_label or stream.profile_name)
            channel.setObjectName("streamName")
            metrics = QLabel(
                "  ·  ".join(
                    part
                    for part in (
                        stream.encoding or "-",
                        stream.resolution,
                        f"{stream.frame_rate:g} FPS" if stream.frame_rate else "",
                        f"{stream.bitrate_kbps} kbps" if stream.bitrate_kbps else "",
                    )
                    if part
                )
            )
            metrics.setObjectName("muted")
            copy_button = QToolButton()
            copy_button.setText("复制")
            copy_button.setToolTip("复制完整码流信息（RTSP URL 含凭据）")
            preview_button = QPushButton("预览此码流")
            preview_button.setObjectName("miniPrimary")
            copy_button.clicked.connect(
                lambda _checked=False, stream=stream: copy_text(
                    stream_text(stream, self.username, self.password)
                )
            )
            preview_button.clicked.connect(
                lambda _checked=False, stream=stream: self.add_stream_requested.emit(
                    stream
                )
            )
            top.addWidget(role)
            top.addWidget(channel)
            top.addWidget(metrics)
            top.addStretch(1)
            top.addWidget(copy_button)
            top.addWidget(preview_button)
            row_layout.addLayout(top)
            uri = SecureUriField(
                stream.rtsp_uri,
                self.username,
                self.password,
                stream.error or "未获取 RTSP URI",
            )
            self.uri_fields.append(uri)
            row_layout.addWidget(uri)
            self.stream_layout.addWidget(row)


class CredentialsPanel(QFrame):
    """Dedicated credential page with default and per-device profiles."""

    credential_profile_changed = Signal(str)
    save_credentials_requested = Signal()
    test_connection_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("credentialsPanel")
        self.setMinimumWidth(700)
        self.setMaximumWidth(820)
        self.device_key = ""

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 22, 24, 24)
        outer.setSpacing(16)
        title = QLabel("ONVIF 认证配置")
        title.setObjectName("formTitle")
        self.context_label = QLabel("默认账号将用于所有没有专用凭据的摄像头")
        self.context_label.setObjectName("muted")
        outer.addWidget(title)
        outer.addWidget(self.context_label)

        card = QFrame()
        card.setObjectName("contentCard")
        form = QVBoxLayout(card)
        form.setContentsMargins(20, 18, 20, 20)
        form.setSpacing(9)
        form.addWidget(QLabel("凭据范围"))
        self.profile_combo = QComboBox()
        form.addWidget(self.profile_combo)
        form.addSpacing(5)
        form.addWidget(QLabel("用户名"))
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("ONVIF 用户名")
        self.username_edit.setClearButtonEnabled(True)
        form.addWidget(self.username_edit)
        form.addWidget(QLabel("密码"))
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("ONVIF 密码")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addWidget(self.password_edit)
        options = QHBoxLayout()
        self.remember_check = QCheckBox("记住密码")
        self.remember_check.setChecked(True)
        self.show_password_button = QCheckBox("显示密码")
        options.addWidget(self.remember_check)
        options.addWidget(self.show_password_button)
        options.addStretch(1)
        form.addLayout(options)
        security = QLabel(
            "密码只写入系统钥匙串；普通配置文件仅保存用户名和设备绑定关系。"
        )
        security.setObjectName("securityHint")
        security.setWordWrap(True)
        form.addWidget(security)
        actions = QHBoxLayout()
        self.save_credentials_button = QPushButton("保存凭据")
        self.save_credentials_button.setObjectName("primary")
        self.test_connection_button = QPushButton("测试当前设备")
        self.test_connection_button.setEnabled(False)
        actions.addWidget(self.save_credentials_button)
        actions.addWidget(self.test_connection_button)
        actions.addStretch(1)
        form.addLayout(actions)
        outer.addWidget(card)

        help_card = QFrame()
        help_card.setObjectName("tipCard")
        help_layout = QVBoxLayout(help_card)
        help_layout.setContentsMargins(16, 13, 16, 13)
        help_title = QLabel("凭据使用规则")
        help_title.setObjectName("cardHeading")
        help_text = QLabel(
            "• 默认账号用于首次扫描和普通设备\n"
            "• 选择设备后可建立专用账号，不影响其他摄像头\n"
            "• 输入内容会立即在当前会话生效，点击保存后下次启动仍可使用"
        )
        help_text.setObjectName("hint")
        help_text.setWordWrap(True)
        help_layout.addWidget(help_title)
        help_layout.addWidget(help_text)
        outer.addWidget(help_card)
        outer.addStretch(1)

        self.profile_combo.currentIndexChanged.connect(self._profile_changed)
        self.show_password_button.toggled.connect(self._toggle_password)
        self.save_credentials_button.clicked.connect(self.save_credentials_requested)
        self.test_connection_button.clicked.connect(self.test_connection_requested)
        self.set_context("", None, False)

    def set_context(
        self,
        key: str,
        device: DiscoveredDevice | None,
        device_profile_exists: bool,
    ) -> None:
        self.device_key = key
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItem("默认摄像头账号", DEFAULT_PROFILE)
        if key and device:
            label = "当前设备专用账号"
            if device_profile_exists:
                label += " · 已保存"
            self.profile_combo.addItem(label, f"device:{key}")
            self.context_label.setText(
                f"当前设备：{device.display_name}  ·  {device.host}"
            )
            self.test_connection_button.setEnabled(True)
        else:
            self.context_label.setText("默认账号将用于所有没有专用凭据的摄像头")
            self.test_connection_button.setEnabled(False)
        self.profile_combo.setCurrentIndex(0)
        self.profile_combo.blockSignals(False)

    def select_profile(self, profile_id: str) -> None:
        index = self.profile_combo.findData(profile_id)
        self.profile_combo.blockSignals(True)
        self.profile_combo.setCurrentIndex(max(index, 0))
        self.profile_combo.blockSignals(False)

    def set_credential(self, credential: Credential) -> None:
        self.username_edit.setText(credential.username)
        self.password_edit.setText(credential.password)
        self.remember_check.setChecked(credential.remember)

    def current_profile_id(self) -> str:
        data = str(self.profile_combo.currentData() or DEFAULT_PROFILE)
        return data if data.startswith("device:") else DEFAULT_PROFILE

    def current_credential(self, profile_id: str) -> Credential:
        label = (
            "默认摄像头账号"
            if profile_id == DEFAULT_PROFILE
            else "当前设备专用账号"
        )
        return Credential(
            profile_id=profile_id,
            label=label,
            username=self.username_edit.text().strip(),
            password=self.password_edit.text(),
            remember=self.remember_check.isChecked(),
        )

    def _profile_changed(self) -> None:
        self.credential_profile_changed.emit(self.current_profile_id())

    def _toggle_password(self, visible: bool) -> None:
        mode = QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        self.password_edit.setEchoMode(mode)


class VideoTile(QFrame):
    log_message = Signal(str)
    remove_requested = Signal(object)
    maximize_requested = Signal(object)
    device_dropped = Signal(str, object)

    def __init__(self, index: int) -> None:
        super().__init__()
        self.index = index
        self.setObjectName("videoTile")
        self.setAcceptDrops(True)
        self.details: DeviceDetails | None = None
        self.device_key = ""
        self.username = ""
        self.password = ""
        self._worker: PreviewThread | None = None
        self._workers: set[PreviewThread] = set()
        self._latest_image: QImage | None = None
        self._paused = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        header = QFrame()
        header.setObjectName("videoHeader")
        header.setFixedHeight(43)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(9, 6, 6, 6)
        header_layout.setSpacing(6)
        self.online_dot = QLabel("●")
        self.online_dot.setObjectName("onlineDot")
        self.title_label = QLabel(f"预览位 {index + 1}")
        self.title_label.setObjectName("videoTitle")
        self.stream_combo = QComboBox()
        self.stream_combo.setObjectName("streamCombo")
        self.stream_combo.setMinimumWidth(145)
        self.stream_combo.setMaximumWidth(235)
        self.copy_button = QToolButton()
        self.copy_button.setText("⧉")
        self.copy_button.setToolTip("复制当前 RTSP 地址（含凭据）")
        self.snapshot_button = QToolButton()
        self.snapshot_button.setText("◉")
        self.snapshot_button.setToolTip("保存当前画面")
        self.maximize_button = QToolButton()
        self.maximize_button.setText("⛶")
        self.maximize_button.setToolTip("聚焦 / 恢复分屏")
        self.close_button = QToolButton()
        self.close_button.setText("×")
        self.close_button.setToolTip("关闭此预览")
        for button in (
            self.copy_button,
            self.snapshot_button,
            self.maximize_button,
            self.close_button,
        ):
            button.setFixedSize(31, 31)
        header_layout.addWidget(self.online_dot)
        header_layout.addWidget(self.title_label, 1)
        header_layout.addWidget(self.stream_combo)
        header_layout.addWidget(self.copy_button)
        header_layout.addWidget(self.snapshot_button)
        header_layout.addWidget(self.maximize_button)
        header_layout.addWidget(self.close_button)
        outer.addWidget(header)

        self.surface = PreviewSurface("＋\n拖入摄像头开始预览")
        outer.addWidget(self.surface, 1)
        footer = QFrame()
        footer.setObjectName("videoFooter")
        footer.setFixedHeight(28)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(10, 5, 10, 5)
        self.meta_label = QLabel("空闲")
        self.meta_label.setObjectName("videoMeta")
        self.meta_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.state_label = QLabel("未连接")
        self.state_label.setObjectName("videoState")
        footer_layout.addWidget(self.meta_label)
        footer_layout.addStretch(1)
        footer_layout.addWidget(self.state_label)
        outer.addWidget(footer)

        self.timeout_timer = QTimer(self)
        self.timeout_timer.setSingleShot(True)
        self.timeout_timer.setInterval(10000)
        self.timeout_timer.timeout.connect(self._on_timeout)
        self.stream_combo.currentIndexChanged.connect(self._stream_changed)
        self.copy_button.clicked.connect(self.copy_uri)
        self.snapshot_button.clicked.connect(self.save_snapshot)
        self.maximize_button.clicked.connect(lambda: self.maximize_requested.emit(self))
        self.close_button.clicked.connect(lambda: self.remove_requested.emit(self))
        self._set_controls_enabled(False)

    def set_compact(self, compact: bool) -> None:
        self.copy_button.setVisible(not compact)
        self.snapshot_button.setVisible(not compact)
        self.stream_combo.setMinimumWidth(108 if compact else 145)
        self.title_label.setMaximumWidth(80 if compact else 16777215)

    def _set_controls_enabled(self, enabled: bool) -> None:
        self.stream_combo.setEnabled(enabled)
        self.copy_button.setEnabled(enabled)
        self.snapshot_button.setEnabled(enabled)
        self.maximize_button.setEnabled(enabled)
        self.close_button.setEnabled(enabled)

    def assign(
        self,
        device_key: str,
        details: DeviceDetails,
        username: str,
        password: str,
        *,
        prefer_substream: bool,
        preferred_token: str = "",
    ) -> None:
        self.stop()
        self.device_key = device_key
        self.details = details
        self.username = username
        self.password = password
        self._paused = False
        self.title_label.setText(
            details.discovery.display_name
            or details.information.title
            or details.discovery.host
        )
        self.title_label.setToolTip(self.title_label.text())
        self.stream_combo.blockSignals(True)
        self.stream_combo.clear()
        for stream in details.streams:
            text = " · ".join(
                part
                for part in (
                    stream.channel_label,
                    stream.stream_role,
                    stream.encoding,
                )
                if part
            )
            self.stream_combo.addItem(text or stream.profile_name, stream.token)
        chosen = 0
        if preferred_token:
            index = self.stream_combo.findData(preferred_token)
            chosen = max(index, 0)
        elif prefer_substream:
            for index, stream in enumerate(details.streams):
                if stream.stream_role == "子码流":
                    chosen = index
                    break
        self.stream_combo.setCurrentIndex(chosen)
        self.stream_combo.blockSignals(False)
        self._set_controls_enabled(True)
        self.start()

    def current_stream(self) -> StreamProfile | None:
        if not self.details:
            return None
        token = str(self.stream_combo.currentData() or "")
        return next(
            (stream for stream in self.details.streams if stream.token == token), None
        )

    def select_role(self, role: str) -> bool:
        """Select the first stream with the requested classified role."""
        if not self.details:
            return False
        stream = next(
            (
                candidate
                for candidate in self.details.streams
                if candidate.stream_role == role
            ),
            None,
        )
        if stream is None:
            return False
        index = self.stream_combo.findData(stream.token)
        if index < 0 or index == self.stream_combo.currentIndex():
            return False
        self.stream_combo.setCurrentIndex(index)
        return True

    def start(self) -> None:
        stream = self.current_stream()
        if not stream or not stream.rtsp_uri or self._paused:
            return
        self.stop()
        self.surface.set_placeholder("正在连接视频流…")
        self.state_label.setText("连接中")
        self.meta_label.setText(
            f"{stream.resolution} · {stream.frame_rate:g} FPS"
            if stream.frame_rate
            else stream.resolution
        )
        worker = PreviewThread(stream.rtsp_uri, self.username, self.password, self)
        self._worker = worker
        self._workers.add(worker)
        worker.frame_ready.connect(lambda image, w=worker: self._on_frame(w, image))
        worker.preview_state.connect(lambda state, w=worker: self._on_state(w, state))
        worker.preview_error.connect(
            lambda message, w=worker: self._on_error(w, message)
        )
        worker.finished.connect(lambda w=worker: self._on_finished(w))
        worker.start()
        self.timeout_timer.start()
        self.log_message.emit(
            f"预览连接：{self.details.discovery.host} / {stream.stream_role}"
        )

    def stop(self) -> None:
        self.timeout_timer.stop()
        worker = self._worker
        self._worker = None
        if worker:
            worker.stop()

    def pause(self) -> None:
        self._paused = True
        self.stop()
        if self.details:
            self.state_label.setText("已暂停")

    def resume(self) -> None:
        self._paused = False
        if self.details:
            self.start()

    def clear(self) -> None:
        self.stop()
        self.details = None
        self.device_key = ""
        self.username = ""
        self.password = ""
        self._latest_image = None
        self._paused = False
        self.title_label.setText(f"预览位 {self.index + 1}")
        self.stream_combo.clear()
        self.surface.set_placeholder("＋\n拖入摄像头开始预览")
        self.meta_label.setText("空闲")
        self.state_label.setText("未连接")
        self._set_controls_enabled(False)

    def update_credentials(self, username: str, password: str) -> None:
        self.username = username
        self.password = password

    def copy_uri(self) -> None:
        stream = self.current_stream()
        if stream and stream.rtsp_uri:
            copy_text(
                uri_with_credentials(stream.rtsp_uri, self.username, self.password)
            )
            self.state_label.setText("已复制（含凭据）")

    def save_snapshot(self) -> None:
        if self._latest_image is None:
            return
        default_name = (
            f"snapshot-{self.details.discovery.host if self.details else 'camera'}.jpg"
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "保存当前画面", default_name, "JPEG 图片 (*.jpg);;PNG 图片 (*.png)"
        )
        if path:
            self._latest_image.save(path)
            self.state_label.setText("截图已保存")

    def _stream_changed(self) -> None:
        if self.details and not self._paused:
            self.start()

    def _on_frame(self, worker: PreviewThread, image: QImage) -> None:
        if self._worker is not worker:
            return
        self.timeout_timer.stop()
        self._latest_image = image
        self.surface.show_image(image)

    def _on_state(self, worker: PreviewThread, state: str) -> None:
        if self._worker is worker:
            self.state_label.setText(state.replace("预览中 · ", ""))

    def _on_error(self, worker: PreviewThread, message: str) -> None:
        if self._worker is not worker:
            return
        self.timeout_timer.stop()
        self.surface.set_placeholder(message)
        self.state_label.setText("连接失败")
        self.log_message.emit(message)

    def _on_finished(self, worker: PreviewThread) -> None:
        if self._worker is worker:
            self._worker = None
            self.timeout_timer.stop()
        self._workers.discard(worker)
        worker.deleteLater()

    def _on_timeout(self) -> None:
        worker = self._worker
        if not worker:
            return
        worker.stop()
        self.surface.set_placeholder("连接超过 10 秒，已强制取消")
        self.state_label.setText("连接超时")
        self.log_message.emit("RTSP 连接超时，已终止解码进程")

    def shutdown(self) -> None:
        self.timeout_timer.stop()
        workers = list(self._workers)
        self._worker = None
        for worker in workers:
            worker.stop()
        for worker in workers:
            if worker.isRunning():
                worker.wait(3500)
        self._workers.clear()

    def dragEnterEvent(self, event: object) -> None:
        if event.mimeData().hasFormat(DEVICE_MIME):
            event.acceptProposedAction()

    def dropEvent(self, event: object) -> None:
        if not event.mimeData().hasFormat(DEVICE_MIME):
            return
        key = bytes(event.mimeData().data(DEVICE_MIME)).decode("utf-8")
        self.device_dropped.emit(key, self)
        event.acceptProposedAction()

    def mouseDoubleClickEvent(self, event: object) -> None:
        if self.details:
            self.maximize_requested.emit(self)
        super().mouseDoubleClickEvent(event)


class VideoWall(QWidget):
    log_message = Signal(str)
    device_dropped = Signal(str, object)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("videoWall")
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(6)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tiles = [VideoTile(index) for index in range(9)]
        self.mode = 4
        self.focused_tile: VideoTile | None = None
        for tile in self.tiles:
            tile.log_message.connect(self.log_message)
            tile.remove_requested.connect(self._remove_tile)
            tile.maximize_requested.connect(self.toggle_focus)
            tile.device_dropped.connect(self.device_dropped)
        self.set_mode(4)

    def visible_tiles(self) -> list[VideoTile]:
        if self.focused_tile:
            return [self.focused_tile]
        return self.tiles[: self.mode]

    def set_mode(self, count: int) -> None:
        if count not in {1, 4, 9}:
            raise ValueError("分屏数量只能是 1、4 或 9")
        self.focused_tile = None
        self.mode = count
        while self.grid.count():
            self.grid.takeAt(0)
        columns = 1 if count == 1 else 2 if count == 4 else 3
        for index, tile in enumerate(self.tiles):
            visible = index < count
            tile.setVisible(visible)
            tile.set_compact(count == 9)
            if visible:
                self.grid.addWidget(tile, index // columns, index % columns)
                changed = tile.select_role("主码流" if count == 1 else "子码流")
                if tile._paused:
                    tile.resume()
                elif tile.details and not changed and tile._worker is None:
                    tile.start()
            else:
                tile.pause()
        QTimer.singleShot(0, self._fit_tiles)

    def add_device(
        self,
        key: str,
        details: DeviceDetails,
        username: str,
        password: str,
        preferred_token: str = "",
        target: VideoTile | None = None,
    ) -> bool:
        tile = target or next(
            (candidate for candidate in self.visible_tiles() if not candidate.details),
            None,
        )
        if tile is None:
            return False
        tile.assign(
            key,
            details,
            username,
            password,
            prefer_substream=self.mode > 1,
            preferred_token=preferred_token,
        )
        return True

    def update_credentials(self, key: str, username: str, password: str) -> None:
        for tile in self.tiles:
            if tile.device_key == key:
                tile.update_credentials(username, password)

    def toggle_focus(self, tile: VideoTile) -> None:
        if self.focused_tile is tile:
            self.set_mode(self.mode)
            return
        self.focused_tile = tile
        while self.grid.count():
            self.grid.takeAt(0)
        for candidate in self.tiles:
            candidate.setVisible(candidate is tile)
            if candidate is not tile:
                candidate.pause()
        tile.setVisible(True)
        tile.set_compact(False)
        changed = tile.select_role("主码流")
        if tile._paused:
            tile.resume()
        elif tile.details and not changed and tile._worker is None:
            tile.start()
        self.grid.addWidget(tile, 0, 0)
        QTimer.singleShot(0, self._fit_tiles)

    def _fit_tiles(self) -> None:
        visible = self.visible_tiles()
        if not visible or self.width() < 20 or self.height() < 20:
            return
        count = 1 if self.focused_tile else self.mode
        columns = 1 if count == 1 else 2 if count == 4 else 3
        rows = (count + columns - 1) // columns
        spacing = self.grid.spacing()
        cell_width = max(
            220.0, (self.width() - spacing * (columns - 1) - 4) / columns
        )
        cell_height = max(
            170.0, (self.height() - spacing * (rows - 1) - 4) / rows
        )
        chrome_height = 71.0
        width_from_height = max(220.0, (cell_height - chrome_height) * 16 / 9)
        tile_width = min(cell_width, width_from_height)
        tile_height = min(cell_height, tile_width * 9 / 16 + chrome_height)
        if tile_height < chrome_height + 120:
            tile_height = min(cell_height, chrome_height + 120)
            tile_width = min(cell_width, (tile_height - chrome_height) * 16 / 9)
        size = QSize(int(tile_width), int(tile_height))
        for tile in visible:
            tile.setFixedSize(size)

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)
        self._fit_tiles()

    def stop_all(self) -> None:
        for tile in self.tiles:
            tile.clear()

    def shutdown(self) -> None:
        for tile in self.tiles:
            tile.shutdown()

    @staticmethod
    def _remove_tile(tile: VideoTile) -> None:
        tile.clear()
