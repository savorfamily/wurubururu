# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 설정. 실행: pyinstaller --noconfirm --clean packaging/wurubururu.spec
import re
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

ROOT = Path(SPECPATH).parent
VERSION = re.search(r'__version__ = "([^"]+)"', (ROOT / "src/wurubururu/__init__.py").read_text()).group(1)
ICONS = Path(SPECPATH) / "build"
MAC = sys.platform == "darwin"
WIN = sys.platform == "win32"

datas = collect_data_files("wurubururu") + collect_data_files("googleapiclient")
binaries = collect_dynamic_libs("libusb_package")
hiddenimports = (
    collect_submodules("wurubururu")
    + collect_submodules("keyring.backends")
    + ["usb.backend.libusb1", "libusb_package"]
    + (["pystray._darwin"] if MAC else ["pystray._win32"] if WIN else [])
)

a = Analysis(
    [str(Path(SPECPATH) / "launcher.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="wurubururu",
    console=False,
    icon=str(ICONS / ("icon.icns" if MAC else "icon.ico")),
)
coll = COLLECT(exe, a.binaries, a.datas, name="wurubururu")

if MAC:
    app = BUNDLE(
        coll,
        name="wurubururu.app",
        icon=str(ICONS / "icon.icns"),
        bundle_identifier="kr.savorfamily.wurubururu",
        version=VERSION,
        info_plist={
            "CFBundleDisplayName": "우르부르르",
            "CFBundleName": "wurubururu",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "LSUIElement": True,              # 독(Dock) 아이콘 없이 메뉴 막대에만 표시
            "LSMinimumSystemVersion": "11.0",
            "NSHumanReadableCopyright": "코드 MIT · 인트로 음원 ℗ Savorfamily, All rights reserved",
        },
    )
