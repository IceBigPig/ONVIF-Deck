# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

project_root = Path(SPECPATH).parent
datas = []
binaries = []
hiddenimports = ["keyring.backends.macOS"]
collected = collect_all("imageio_ffmpeg")
datas += collected[0]
binaries += collected[1]
hiddenimports += collected[2]

analysis = Analysis(
    [str(project_root / "run.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["cv2", "numpy"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="ONVIF设备工作台",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
collection = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="ONVIF设备工作台",
)
app = BUNDLE(
    collection,
    name="ONVIF设备工作台.app",
    icon=None,
    bundle_identifier="io.github.icebigpig.onvif-deck",
    info_plist={
        "CFBundleShortVersionString": "1.1.1",
        "CFBundleVersion": "1.1.1",
        "LSApplicationCategoryType": "public.app-category.utilities",
        "NSHighResolutionCapable": True,
        "NSLocalNetworkUsageDescription": "用于扫描并连接局域网中的 ONVIF 摄像头。",
    },
)
