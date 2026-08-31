from __future__ import annotations

from urllib.parse import urlsplit

from PySide6.QtCore import Qt, QTime
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .credentials import (
    DEFAULT_PROFILE,
    Credential,
    CredentialStore,
    CredentialStoreError,
)
from .dashboard import (
    CredentialsPanel,
    DeviceInspector,
    DeviceList,
    VideoTile,
    VideoWall,
    copy_text,
    device_text,
)
from .models import DeviceDetails, DiscoveredDevice, StreamProfile
from .workers import DeviceQueryThread, DiscoveryThread

APP_STYLE = """
QWidget {
  color: #172033; font-size: 13px;
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei";
}
QMainWindow, QWidget#appRoot, QWidget#workspace, QWidget#page,
QStackedWidget#pageStack { background: #f4f6f9; }
QLabel { background: transparent; }
QFrame#sidebar { background: #101c2b; border: 0; }
QLabel#brand { color: white; font-size: 19px; font-weight: 760; }
QLabel#brandSub { color: #8291a5; font-size: 11px; }
QLabel#sidebarSection { color: #627389; font-size: 10px; font-weight: 700; }
QLabel#sidebarStatus {
  color: #aebdd0; background: #172638; border: 1px solid #26384d;
  border-radius: 8px; padding: 9px;
}
QPushButton#navButton {
  background: transparent; color: #c6d1df; border: 0; border-radius: 8px;
  padding: 11px 12px; text-align: left; font-weight: 630;
}
QPushButton#navButton:hover { background: #1a2a3e; color: white; }
QPushButton#navButton[active="true"] { background: #15569d; color: white; }
QFrame#topBar { background: white; border-bottom: 1px solid #dfe5ec; }
QLabel#pageTitle { font-size: 20px; font-weight: 760; color: #111c2c; }
QLabel#pageSubtitle { color: #778497; font-size: 11px; }
QLabel#summaryChip {
  background: #f0f4f8; border: 1px solid #dde5ee; border-radius: 7px;
  padding: 6px 10px; font-weight: 650;
}
QLabel#onlineChip {
  background: #eaf8ef; color: #1b7a43; border: 1px solid #d0edda;
  border-radius: 7px; padding: 6px 10px; font-weight: 650;
}
QPushButton, QToolButton {
  background: #e9eff6; color: #25364b; border: 0; border-radius: 7px;
  padding: 7px 11px; font-weight: 620;
}
QPushButton:hover, QToolButton:hover { background: #dce7f3; }
QPushButton:disabled, QToolButton:disabled { color: #9aa6b4; background: #eef1f4; }
QPushButton#primary, QPushButton#miniPrimary { background: #1672e8; color: white; }
QPushButton#primary:hover, QPushButton#miniPrimary:hover { background: #0f62c9; }
QPushButton#miniPrimary { padding: 6px 9px; font-size: 11px; }
QPushButton#danger { background: #fff0f0; color: #ad3030; }
QPushButton#ghostButton { background: transparent; color: #1672e8; }
QPushButton#segmented {
  background: white; border: 1px solid #d9e2ec; border-radius: 7px;
  padding: 7px 16px;
}
QPushButton#segmented:checked { background: #1672e8; color: white; border-color: #1672e8; }
QLineEdit, QComboBox {
  background: white; border: 1px solid #d5dee8; border-radius: 7px;
  padding: 7px 9px; selection-background-color: #1e73db;
}
QLineEdit:focus, QComboBox:focus { border-color: #3986e8; }
QFrame#toolbar, QFrame#devicePane, QFrame#deviceInspector,
QFrame#credentialsPanel, QFrame#logPageCard {
  background: white; border: 1px solid #dfe6ee; border-radius: 10px;
}
QFrame#devicePane { min-width: 316px; max-width: 350px; }
QLabel#sectionTitle { font-size: 15px; font-weight: 730; }
QLabel#inspectorTitle, QLabel#formTitle { font-size: 18px; font-weight: 760; }
QLabel#emptyIcon { color: #8ea2b8; font-size: 44px; }
QLabel#emptyTitle { font-size: 16px; font-weight: 720; }
QFrame#emptyState { background: #fafbfd; border: 1px dashed #d4dee9; border-radius: 10px; }
QListWidget#deviceList { background: transparent; border: 0; outline: 0; }
QListWidget#deviceList::item { background: transparent; border: 0; }
QFrame#deviceCard { background: #fbfcfe; border: 1px solid #e0e7ef; border-radius: 9px; }
QFrame#deviceCard:hover { border-color: #9ec5f5; background: #f6faff; }
QFrame#deviceCard[selected="true"] { border: 1px solid #4e99ef; background: #eaf3ff; }
QLabel#deviceName { font-size: 13px; font-weight: 700; }
QLabel#onlineDot { color: #19a65a; font-size: 12px; }
QLabel#badge { background: #edf2f7; color: #526274; border-radius: 5px; padding: 3px 6px; font-size: 10px; }
QLabel#muted, QLabel#fieldName { color: #718095; font-size: 11px; }
QLabel#hint { color: #7d8998; font-size: 11px; }
QLabel#cardStatus { color: #22824a; font-size: 11px; }
QLabel#cardStatus[error="true"] { color: #b33a3a; }
QFrame#contentCard {
  background: #fbfcfe; border: 1px solid #e0e7ef; border-radius: 9px;
}
QLabel#cardHeading { font-size: 14px; font-weight: 730; }
QLabel#fieldValue { color: #2b3c52; font-size: 11px; }
QFrame#wideStreamRow { background: white; border: 1px solid #e3e9f0; border-radius: 8px; }
QFrame#wideStreamRow:hover { border-color: #b7cce3; }
QLabel#roleBadge {
  background: #e9f4ff; color: #1264ba; border-radius: 5px;
  padding: 4px 7px; font-size: 11px; font-weight: 700;
}
QLabel#streamName { font-weight: 700; }
QLineEdit#streamUri { background: #f4f7fa; color: #516176; border: 0; font-size: 11px; }
QFrame#credentialsPanel { background: white; }
QLabel#securityHint {
  background: #eef7ff; color: #416783; border: 1px solid #d6e9f8;
  border-radius: 7px; padding: 10px;
}
QFrame#tipCard { background: #fafbfd; border: 1px solid #e1e7ee; border-radius: 8px; }
QWidget#videoWall { background: #e4e9ef; border-radius: 10px; }
QFrame#videoTile { background: #0d1723; border: 1px solid #2b3b4e; border-radius: 9px; }
QFrame#videoHeader, QFrame#videoFooter { background: #182535; border: 0; }
QLabel#videoTitle { color: white; font-weight: 680; }
QLabel#videoMeta, QLabel#videoState { color: #bcc9d8; font-size: 11px; }
QLabel#videoSurface { background: #07111d; color: #8290a3; font-size: 13px; }
QComboBox#streamCombo { background: #26384b; color: white; border: 0; padding: 5px 8px; }
QTextEdit#logEdit {
  background: #0f1a28; color: #c5d2e0; border: 0; border-radius: 8px;
  padding: 12px; font-family: "SF Mono", Menlo, monospace; font-size: 12px;
}
QStatusBar { background: white; border-top: 1px solid #dfe5ec; color: #526274; }
QScrollBar:vertical { background: transparent; width: 9px; margin: 2px; }
QScrollBar::handle:vertical { background: #c5cfda; border-radius: 4px; min-height: 28px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


class MainWindow(QMainWindow):
    def __init__(self, credential_store: CredentialStore | None = None) -> None:
        super().__init__()
        self.setWindowTitle("ONVIF 设备工作台")
        self.resize(1580, 980)
        self.setMinimumSize(1180, 760)
        self.setStyleSheet(APP_STYLE)

        self.devices: dict[str, DiscoveredDevice] = {}
        self.details: dict[str, DeviceDetails] = {}
        self._scan_thread: DiscoveryThread | None = None
        self._query_threads: dict[str, DeviceQueryThread] = {}
        self._pending_preview: set[str] = set()
        self._log_entries = 0
        self.credential_store = credential_store or CredentialStore()
        self.session_credentials: dict[str, Credential] = {}
        default_credential = self.credential_store.load(DEFAULT_PROFILE)
        self.session_credentials[DEFAULT_PROFILE] = default_credential

        self._build_ui()
        self._wire_events()
        self.credentials_panel.set_credential(default_credential)
        self._restore_window_state()
        self._activate_nav(0)

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("appRoot")
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._build_sidebar())

        workspace = QWidget()
        workspace.setObjectName("workspace")
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(0)
        workspace_layout.addWidget(self._build_topbar())

        self.page_stack = QStackedWidget()
        self.page_stack.setObjectName("pageStack")
        self.page_stack.addWidget(self._build_discovery_page())
        self.page_stack.addWidget(self._build_preview_page())
        self.page_stack.addWidget(self._build_credentials_page())
        self.page_stack.addWidget(self._build_log_page())
        workspace_layout.addWidget(self.page_stack, 1)
        root_layout.addWidget(workspace, 1)

        self.setCentralWidget(root)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("就绪 · 配置凭据后扫描局域网摄像头")

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(158)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 20, 12, 14)
        layout.setSpacing(7)
        brand = QLabel("ONVIF\n设备工作台")
        brand.setObjectName("brand")
        brand_sub = QLabel("发现 · 识别 · 多路预览")
        brand_sub.setObjectName("brandSub")
        layout.addWidget(brand)
        layout.addWidget(brand_sub)
        layout.addSpacing(20)
        section = QLabel("工作区")
        section.setObjectName("sidebarSection")
        layout.addWidget(section)

        self.nav_buttons: list[QPushButton] = []
        for text in ("◉  设备发现", "▣  实时预览", "⚙  凭据管理", "▤  运行日志"):
            button = QPushButton(text)
            button.setObjectName("navButton")
            button.setProperty("active", False)
            layout.addWidget(button)
            self.nav_buttons.append(button)
        layout.addStretch(1)
        self.sidebar_status = QLabel("Media2 优先\nFFmpeg · RTSP/TCP")
        self.sidebar_status.setObjectName("sidebarStatus")
        self.sidebar_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.sidebar_status)
        version = QLabel("V1.1.1")
        version.setObjectName("brandSub")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)
        return sidebar

    def _build_topbar(self) -> QFrame:
        topbar = QFrame()
        topbar.setObjectName("topBar")
        topbar.setFixedHeight(76)
        layout = QHBoxLayout(topbar)
        layout.setContentsMargins(20, 11, 18, 11)
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        self.page_title = QLabel("设备发现")
        self.page_title.setObjectName("pageTitle")
        self.page_subtitle = QLabel("扫描局域网并识别设备与码流")
        self.page_subtitle.setObjectName("pageSubtitle")
        title_box.addWidget(self.page_title)
        title_box.addWidget(self.page_subtitle)
        self.device_chip = QLabel("0 台设备")
        self.device_chip.setObjectName("summaryChip")
        self.stream_chip = QLabel("0 路码流")
        self.stream_chip.setObjectName("summaryChip")
        self.online_chip = QLabel("等待扫描")
        self.online_chip.setObjectName("onlineChip")
        self.auth_button = QPushButton("凭据设置")
        self.manual_button = QPushButton("手动添加")
        self.stop_all_button = QPushButton("停止全部预览")
        self.stop_all_button.setObjectName("danger")
        self.stop_all_button.setEnabled(False)
        self.stop_scan_button = QPushButton("停止扫描")
        self.stop_scan_button.setEnabled(False)
        self.scan_button = QPushButton("扫描设备")
        self.scan_button.setObjectName("primary")
        layout.addLayout(title_box)
        layout.addSpacing(16)
        layout.addWidget(self.device_chip)
        layout.addWidget(self.stream_chip)
        layout.addWidget(self.online_chip)
        layout.addStretch(1)
        layout.addWidget(self.auth_button)
        layout.addWidget(self.manual_button)
        layout.addWidget(self.stop_all_button)
        layout.addWidget(self.stop_scan_button)
        layout.addWidget(self.scan_button)
        return topbar

    @staticmethod
    def _page() -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        page.setObjectName("page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(10)
        return page, layout

    def _build_discovery_page(self) -> QWidget:
        page, layout = self._page()
        toolbar = QFrame()
        toolbar.setObjectName("toolbar")
        bar = QHBoxLayout(toolbar)
        bar.setContentsMargins(12, 9, 12, 9)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索设备名称、IP 或型号")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setMaximumWidth(520)
        hint = QLabel("选择设备后在右侧查看全部信息；“加入预览”会自动进入预览页")
        hint.setObjectName("hint")
        bar.addWidget(self.search_edit, 1)
        bar.addWidget(hint)
        layout.addWidget(toolbar)

        body = QHBoxLayout()
        body.setSpacing(10)
        body.addWidget(self._build_device_pane())
        self.device_inspector = DeviceInspector()
        body.addWidget(self.device_inspector, 1)
        layout.addLayout(body, 1)
        return page

    def _build_device_pane(self) -> QFrame:
        pane = QFrame()
        pane.setObjectName("devicePane")
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(10, 12, 10, 10)
        layout.setSpacing(8)
        header = QHBoxLayout()
        self.device_title = QLabel("已发现设备 (0)")
        self.device_title.setObjectName("sectionTitle")
        refresh = QToolButton()
        refresh.setText("↻")
        refresh.setToolTip("重新扫描")
        header.addWidget(self.device_title)
        header.addStretch(1)
        header.addWidget(refresh)
        layout.addLayout(header)
        self.device_list = DeviceList()
        layout.addWidget(self.device_list, 1)
        hint = QLabel("点击卡片查看详情；双击直接加入预览")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        refresh.clicked.connect(self.start_scan)
        return pane

    def _build_preview_page(self) -> QWidget:
        page, layout = self._page()
        toolbar = QFrame()
        toolbar.setObjectName("toolbar")
        bar = QHBoxLayout(toolbar)
        bar.setContentsMargins(12, 8, 12, 8)
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        for count, text in ((1, "单画面"), (4, "四分屏"), (9, "九分屏")):
            button = QPushButton(text)
            button.setObjectName("segmented")
            button.setCheckable(True)
            button.setChecked(count == 4)
            self.mode_group.addButton(button, count)
            button.toggled.connect(
                lambda checked, count=count: checked and self.set_grid_mode(count)
            )
            bar.addWidget(button)
        bar.addSpacing(12)
        helper = QLabel("单画面优先主码流，多画面优先子码流")
        helper.setObjectName("hint")
        bar.addWidget(helper)
        bar.addStretch(1)
        self.preview_device_combo = QComboBox()
        self.preview_device_combo.setMinimumWidth(280)
        self.preview_device_combo.addItem("选择要加入的设备", "")
        self.preview_add_button = QPushButton("加入空闲画面")
        self.preview_add_button.setObjectName("primary")
        bar.addWidget(self.preview_device_combo)
        bar.addWidget(self.preview_add_button)
        layout.addWidget(toolbar)
        self.video_wall = VideoWall()
        layout.addWidget(self.video_wall, 1)
        return page

    def _build_credentials_page(self) -> QWidget:
        page, layout = self._page()
        toolbar = QFrame()
        toolbar.setObjectName("toolbar")
        bar = QHBoxLayout(toolbar)
        bar.setContentsMargins(12, 9, 12, 9)
        label = QLabel("配置对象")
        label.setObjectName("sectionTitle")
        self.credential_device_combo = QComboBox()
        self.credential_device_combo.setMinimumWidth(330)
        self.credential_device_combo.addItem("默认账号（应用于所有普通设备）", "")
        helper = QLabel("设备专用凭据会覆盖默认账号")
        helper.setObjectName("hint")
        bar.addWidget(label)
        bar.addWidget(self.credential_device_combo)
        bar.addWidget(helper)
        bar.addStretch(1)
        layout.addWidget(toolbar)
        holder = QHBoxLayout()
        holder.addStretch(1)
        self.credentials_panel = CredentialsPanel()
        holder.addWidget(self.credentials_panel)
        holder.addStretch(1)
        layout.addLayout(holder, 1)
        return page

    def _build_log_page(self) -> QWidget:
        page, layout = self._page()
        card = QFrame()
        card.setObjectName("logPageCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 11, 12, 12)
        card_layout.setSpacing(8)
        header = QHBoxLayout()
        title = QLabel("运行日志")
        title.setObjectName("sectionTitle")
        self.log_count = QLabel("0 条")
        self.log_count.setObjectName("badge")
        self.copy_log_button = QPushButton("复制全部")
        self.clear_log_button = QPushButton("清空")
        header.addWidget(title)
        header.addWidget(self.log_count)
        header.addStretch(1)
        header.addWidget(self.copy_log_button)
        header.addWidget(self.clear_log_button)
        card_layout.addLayout(header)
        self.log_edit = QTextEdit()
        self.log_edit.setObjectName("logEdit")
        self.log_edit.setReadOnly(True)
        self.log_edit.setPlaceholderText("扫描、认证、码流读取和预览事件会显示在这里")
        card_layout.addWidget(self.log_edit, 1)
        layout.addWidget(card, 1)
        return page

    def _wire_events(self) -> None:
        self.scan_button.clicked.connect(self.start_scan)
        self.stop_scan_button.clicked.connect(self.stop_scan)
        self.stop_all_button.clicked.connect(self.stop_all_previews)
        self.manual_button.clicked.connect(self.add_manual_device)
        self.auth_button.clicked.connect(lambda: self._activate_nav(2))
        self.search_edit.textChanged.connect(self.device_list.filter)
        self.preview_add_button.clicked.connect(self._add_preview_combo_device)
        self.copy_log_button.clicked.connect(
            lambda: copy_text(self.log_edit.toPlainText())
        )
        self.clear_log_button.clicked.connect(self.clear_logs)
        self.credential_device_combo.currentIndexChanged.connect(
            self._credential_device_changed
        )
        self.device_list.device_selected.connect(self.show_device_details)
        self.device_list.add_requested.connect(self.add_device_to_wall)
        self.device_list.copy_requested.connect(self.copy_device)
        self.device_list.read_requested.connect(self.query_device)
        self.device_list.itemDoubleClicked.connect(
            lambda _item: self.add_device_to_wall(self.device_list.selected_key())
        )
        self.device_inspector.refresh_requested.connect(self.query_device)
        self.device_inspector.copy_requested.connect(self.copy_device)
        self.device_inspector.add_requested.connect(self.add_device_to_wall)
        self.device_inspector.add_stream_requested.connect(self.add_stream_to_wall)
        self.video_wall.log_message.connect(self.log)
        self.video_wall.device_dropped.connect(self._device_dropped)
        self.credentials_panel.credential_profile_changed.connect(
            self.load_credential_profile
        )
        self.credentials_panel.save_credentials_requested.connect(
            self.save_current_credentials
        )
        self.credentials_panel.test_connection_requested.connect(
            self.test_current_connection
        )
        self.credentials_panel.username_edit.textChanged.connect(
            self._cache_current_credentials
        )
        self.credentials_panel.password_edit.textChanged.connect(
            self._cache_current_credentials
        )
        self.credentials_panel.remember_check.toggled.connect(
            self._cache_current_credentials
        )
        for index, button in enumerate(self.nav_buttons):
            button.clicked.connect(lambda _checked=False, index=index: self._activate_nav(index))
        QShortcut(QKeySequence.StandardKey.Copy, self).activated.connect(
            self.copy_selected_context
        )

    def _restore_window_state(self) -> None:
        geometry = self.credential_store.settings.value("window/geometry")
        if geometry:
            self.restoreGeometry(geometry)
        mode = int(self.credential_store.settings.value("preview/grid_mode", 4) or 4)
        button = self.mode_group.button(mode)
        if button:
            button.setChecked(True)

    def _activate_nav(self, index: int) -> None:
        titles = (
            ("设备发现", "扫描局域网并识别设备、通道与码流"),
            ("实时预览", "多路 RTSP 预览与独立码流控制"),
            ("凭据管理", "管理默认账号和设备专用账号"),
            ("运行日志", "查看扫描、认证和预览运行记录"),
        )
        self.page_stack.setCurrentIndex(index)
        self.page_title.setText(titles[index][0])
        self.page_subtitle.setText(titles[index][1])
        for button_index, button in enumerate(self.nav_buttons):
            button.setProperty("active", button_index == index)
            button.style().unpolish(button)
            button.style().polish(button)
        is_discovery = index == 0
        self.scan_button.setVisible(is_discovery)
        self.stop_scan_button.setVisible(is_discovery)
        self.manual_button.setVisible(is_discovery)
        self.stop_all_button.setVisible(index == 1)
        self.auth_button.setVisible(index != 2)
        if index == 0:
            self.device_list.setFocus()
        elif index == 1:
            self.video_wall.setFocus()
        elif index == 2:
            self.credentials_panel.username_edit.setFocus()
        else:
            self.log_edit.setFocus()

    def log(self, message: str) -> None:
        timestamp = QTime.currentTime().toString("HH:mm:ss")
        self.log_edit.append(f"{timestamp}  {message}")
        self._log_entries += 1
        self.log_count.setText(f"{self._log_entries} 条")

    def clear_logs(self) -> None:
        self.log_edit.clear()
        self._log_entries = 0
        self.log_count.setText("0 条")

    def start_scan(self) -> None:
        if self._scan_thread and self._scan_thread.isRunning():
            return
        default = self.session_credentials.get(DEFAULT_PROFILE)
        if not default or not default.username:
            self._activate_nav(2)
            QMessageBox.information(
                self,
                "请先配置 ONVIF 账号",
                "首次扫描前请填写默认用户名和密码。输入后可直接扫描，保存后下次自动读取。",
            )
            return
        self.scan_button.setEnabled(False)
        self.stop_scan_button.setEnabled(True)
        self.online_chip.setText("扫描中…")
        self.statusBar().showMessage("正在通过 WS-Discovery 扫描所有活动 IPv4 网卡…")
        self.log("开始扫描局域网设备（5 秒）")
        worker = DiscoveryThread(5.0, self)
        self._scan_thread = worker
        worker.device_found.connect(self.add_discovered_device)
        worker.scan_error.connect(self._on_scan_error)
        worker.scan_complete.connect(self._on_scan_complete)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def stop_scan(self) -> None:
        if self._scan_thread:
            self._scan_thread.stop()
            self.stop_scan_button.setEnabled(False)
            self.statusBar().showMessage("正在停止扫描…")

    def _on_scan_error(self, message: str) -> None:
        self.log(f"扫描失败：{message}")
        self.statusBar().showMessage(f"扫描失败：{message}")
        self.online_chip.setText("扫描失败")
        self._reset_scan_buttons()

    def _on_scan_complete(self, count: int) -> None:
        self.log(f"扫描完成，本轮收到 {count} 个设备响应")
        self.statusBar().showMessage(f"扫描完成，共发现 {len(self.devices)} 个设备")
        self._reset_scan_buttons()
        self._update_summary()

    def _reset_scan_buttons(self) -> None:
        self.scan_button.setEnabled(True)
        self.stop_scan_button.setEnabled(False)
        self._scan_thread = None

    def add_discovered_device(self, device: DiscoveredDevice) -> None:
        key = device.endpoint or device.device_service_url
        if key in self.devices:
            return
        self.devices[key] = device
        self.device_list.add_device(key, device)
        label = f"{device.display_name}  ·  {device.host}"
        self.preview_device_combo.addItem(label, key)
        self.credential_device_combo.addItem(label, key)
        self.log(f"发现设备：{device.host} → {device.device_service_url}")
        self._update_summary()
        self.query_device(key)

    def add_manual_device(self) -> None:
        raw, accepted = QInputDialog.getText(
            self,
            "手动添加设备",
            "输入摄像头 IP、IP:端口或完整 Device Service URL：",
            text="192.168.1.100",
        )
        raw = raw.strip()
        if not accepted or not raw:
            return
        url = raw if "://" in raw else f"http://{raw}"
        parsed = urlsplit(url)
        if not parsed.hostname:
            QMessageBox.warning(self, "地址无效", "无法识别该 IP 或 URL。")
            return
        if parsed.path in ("", "/"):
            url = url.rstrip("/") + "/onvif/device_service"
        device = DiscoveredDevice(
            endpoint=url, xaddrs=[url], remote_address=parsed.hostname
        )
        self.add_discovered_device(device)
        self.device_list.select_key(device.endpoint)

    def query_device(self, key: str) -> None:
        if not key or key not in self.devices:
            return
        running = self._query_threads.get(key)
        if running and running.isRunning():
            return
        device = self.devices[key]
        card = self.device_list.cards[key]
        card.set_status("正在认证并读取…")
        credential = self.credentials_for_device(key)
        worker = DeviceQueryThread(
            device, credential.username, credential.password, self
        )
        self._query_threads[key] = worker
        worker.query_complete.connect(self._on_query_complete)
        worker.query_error.connect(self._on_query_error)
        worker.finished.connect(lambda key=key: self._cleanup_query(key))
        worker.start()
        self.log(f"读取设备：{device.host}")

    def _cleanup_query(self, key: str) -> None:
        worker = self._query_threads.pop(key, None)
        if worker:
            worker.deleteLater()

    def _on_query_complete(self, details: DeviceDetails) -> None:
        key = details.discovery.endpoint or details.discovery.device_service_url
        self.details[key] = details
        card = self.device_list.cards.get(key)
        if card:
            card.set_details(details)
        self.log(f"读取成功：{details.discovery.host}，{len(details.streams)} 路码流")
        if self.device_list.selected_key() == key:
            self.show_device_details(key)
        self._update_summary()
        if key in self._pending_preview:
            self._pending_preview.discard(key)
            self.add_device_to_wall(key)

    def _on_query_error(self, device: DiscoveredDevice, message: str) -> None:
        key = device.endpoint or device.device_service_url
        card = self.device_list.cards.get(key)
        if card:
            card.set_status("读取失败", error=True)
        self.log(f"读取失败：{device.host}：{message}")
        self.statusBar().showMessage(f"读取失败：{message}")
        self._update_summary()

    def show_device_details(self, key: str) -> None:
        device = self.devices.get(key)
        if device:
            credential = self.credentials_for_device(key)
            self.device_inspector.set_credentials(
                credential.username, credential.password
            )
            self.device_inspector.set_device(key, device, self.details.get(key))

    def _add_preview_combo_device(self) -> None:
        self.add_device_to_wall(str(self.preview_device_combo.currentData() or ""))

    def add_device_to_wall(self, key: str) -> None:
        if not key:
            self.statusBar().showMessage("请先选择一台设备")
            return
        details = self.details.get(key)
        if not details:
            self._pending_preview.add(key)
            self.query_device(key)
            self.statusBar().showMessage("正在读取设备，完成后将自动加入预览…")
            return
        credential = self.credentials_for_device(key)
        if not self.video_wall.add_device(
            key, details, credential.username, credential.password
        ):
            QMessageBox.information(
                self,
                "分屏已满",
                "当前分屏没有空位。请关闭一个画面或切换到更多分屏。",
            )
            return
        self.stop_all_button.setEnabled(True)
        self.log(f"加入预览：{details.discovery.host}")
        self._activate_nav(1)

    def add_stream_to_wall(self, stream: StreamProfile) -> None:
        key = self.device_inspector.device_key
        details = self.details.get(key)
        if not details:
            return
        credential = self.credentials_for_device(key)
        if not self.video_wall.add_device(
            key,
            details,
            credential.username,
            credential.password,
            preferred_token=stream.token,
        ):
            QMessageBox.information(self, "分屏已满", "请先释放一个预览画面。")
            return
        self.stop_all_button.setEnabled(True)
        self._activate_nav(1)

    def _device_dropped(self, key: str, tile: VideoTile) -> None:
        details = self.details.get(key)
        if not details:
            self._pending_preview.add(key)
            self.query_device(key)
            return
        credential = self.credentials_for_device(key)
        self.video_wall.add_device(
            key,
            details,
            credential.username,
            credential.password,
            target=tile,
        )
        self.stop_all_button.setEnabled(True)

    def set_grid_mode(self, count: int) -> None:
        self.video_wall.set_mode(count)
        self.credential_store.settings.setValue("preview/grid_mode", count)
        self.credential_store.settings.sync()
        self.log(f"切换为 {count} 画面布局")

    def stop_all_previews(self) -> None:
        self.video_wall.stop_all()
        self.stop_all_button.setEnabled(False)
        self.log("已停止全部预览")

    def _credential_device_changed(self) -> None:
        key = str(self.credential_device_combo.currentData() or "")
        device = self.devices.get(key)
        profile_id = self.credential_store.device_profile_id(key) if key else ""
        self.credentials_panel.set_context(
            key,
            device,
            bool(profile_id and self.credential_store.has_profile(profile_id)),
        )
        bound = self.credential_store.profile_for_device(key) if key else DEFAULT_PROFILE
        ui_profile = f"device:{key}" if key and bound != DEFAULT_PROFILE else DEFAULT_PROFILE
        self.credentials_panel.select_profile(ui_profile)
        self.load_credential_profile(ui_profile)

    def _ui_profile_to_store_id(self, ui_profile_id: str) -> str:
        if ui_profile_id.startswith("device:"):
            key = ui_profile_id.removeprefix("device:")
            return self.credential_store.device_profile_id(key)
        return DEFAULT_PROFILE

    def load_credential_profile(self, ui_profile_id: str) -> None:
        store_id = self._ui_profile_to_store_id(ui_profile_id)
        credential = self.session_credentials.get(store_id)
        if credential is None:
            credential = self.credential_store.load(store_id)
            if store_id != DEFAULT_PROFILE and not credential.username:
                default = self.session_credentials.get(DEFAULT_PROFILE)
                if default:
                    credential.username = default.username
                    credential.password = default.password
                    credential.remember = default.remember
            self.session_credentials[store_id] = credential
        self.credentials_panel.set_credential(credential)

    def _cache_current_credentials(self, _value: object = None) -> None:
        store_id = self._ui_profile_to_store_id(
            self.credentials_panel.current_profile_id()
        )
        self.session_credentials[store_id] = self.credentials_panel.current_credential(
            store_id
        )
        inspector_key = self.device_inspector.device_key
        if inspector_key:
            credential = self.credentials_for_device(inspector_key)
            self.device_inspector.set_credentials(
                credential.username, credential.password
            )

    def save_current_credentials(self, silent: bool = False) -> None:
        ui_profile_id = self.credentials_panel.current_profile_id()
        store_id = self._ui_profile_to_store_id(ui_profile_id)
        credential = self.credentials_panel.current_credential(store_id)
        try:
            self.credential_store.save(credential)
        except CredentialStoreError as exc:
            if not silent:
                QMessageBox.warning(self, "凭据未保存", str(exc))
            return
        self.session_credentials[store_id] = credential
        key = self.credentials_panel.device_key
        if key:
            self.credential_store.bind_device(key, store_id)
            resolved = self.credentials_for_device(key)
            self.video_wall.update_credentials(
                key, resolved.username, resolved.password
            )
            if self.device_inspector.device_key == key:
                self.device_inspector.set_credentials(
                    resolved.username, resolved.password
                )
        self.log(f"凭据已安全保存：{credential.label}")
        self._credential_device_changed()
        if not silent:
            self.statusBar().showMessage("凭据已保存到系统钥匙串")

    def credentials_for_device(self, key: str) -> Credential:
        store_id = self.credential_store.profile_for_device(key)
        credential = self.session_credentials.get(store_id)
        if credential is None:
            credential = self.credential_store.load(store_id)
            self.session_credentials[store_id] = credential
        ui_store_id = self._ui_profile_to_store_id(
            self.credentials_panel.current_profile_id()
        )
        if store_id == DEFAULT_PROFILE and ui_store_id == DEFAULT_PROFILE:
            return self.session_credentials.get(DEFAULT_PROFILE, credential)
        if self.credentials_panel.device_key == key and ui_store_id == store_id:
            return self.credentials_panel.current_credential(store_id)
        return credential

    def test_current_connection(self) -> None:
        key = self.credentials_panel.device_key
        if not key:
            QMessageBox.information(
                self, "请选择设备", "请从页面顶部选择一台摄像头。"
            )
            return
        self.query_device(key)
        self.statusBar().showMessage("正在使用当前凭据测试连接…")

    def copy_device(self, key: str) -> None:
        details = self.details.get(key)
        if details:
            credential = self.credentials_for_device(key)
            copy_text(
                device_text(details, credential.username, credential.password)
            )
            self.statusBar().showMessage("设备及码流信息已复制（RTSP URL 含凭据）")
            return
        device = self.devices.get(key)
        if device:
            copy_text(
                f"设备名称: {device.display_name}\n"
                f"IP 地址: {device.host}\n"
                f"设备服务: {device.device_service_url}"
            )
            self.statusBar().showMessage("设备信息已复制")

    def copy_selected_context(self) -> None:
        focused = self.focusWidget()
        if isinstance(focused, (QLineEdit, QTextEdit)):
            focused.copy()
            return
        key = self.device_list.selected_key()
        if key:
            self.copy_device(key)

    def _update_summary(self) -> None:
        device_count = len(self.devices)
        read_count = len(self.details)
        stream_count = sum(len(details.streams) for details in self.details.values())
        self.device_chip.setText(f"{device_count} 台设备")
        self.stream_chip.setText(f"{stream_count} 路码流")
        self.device_title.setText(f"已发现设备 ({device_count})")
        if self._scan_thread and self._scan_thread.isRunning():
            self.online_chip.setText("扫描中…")
        elif not device_count:
            self.online_chip.setText("等待扫描")
        elif read_count == device_count:
            self.online_chip.setText("全部已读取")
        else:
            self.online_chip.setText(f"{read_count}/{device_count} 已读取")

    def closeEvent(self, event: QCloseEvent) -> None:
        self.credential_store.settings.setValue("window/geometry", self.saveGeometry())
        self.credential_store.settings.sync()
        if self._scan_thread and self._scan_thread.isRunning():
            self._scan_thread.stop()
            self._scan_thread.wait(1000)
        self.video_wall.shutdown()
        for worker in list(self._query_threads.values()):
            if worker.isRunning() and not worker.wait(700):
                worker.terminate()
                worker.wait(300)
        event.accept()
