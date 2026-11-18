"""로그인할 때 자동 실행.

macOS  : ~/Library/LaunchAgents/kr.savorfamily.wurubururu.plist
Windows: HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run 의 wurubururu 값
"""
from __future__ import annotations

import os
import plistlib
import sys
from pathlib import Path

LABEL = "kr.savorfamily.wurubururu"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def supported() -> bool:
    return sys.platform in ("darwin", "win32")


def launch_command() -> list[str]:
    """지금 실행 중인 프로그램을 다시 띄우는 명령."""
    if getattr(sys, "frozen", False):
        exe = sys.executable
        if sys.platform == "darwin" and ".app/Contents/MacOS/" in exe:
            app = exe.split(".app/Contents/MacOS/")[0] + ".app"
            return ["/usr/bin/open", "-a", app]
        return [exe]
    return [sys.executable, "-m", "wurubururu", "run"]


def _plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def is_enabled() -> bool:
    if sys.platform == "darwin":
        return _plist_path().exists()
    if sys.platform == "win32":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
                winreg.QueryValueEx(k, "wurubururu")
            return True
        except OSError:
            return False
    return False


def enable() -> None:
    cmd = launch_command()
    if sys.platform == "darwin":
        p = _plist_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "wb") as f:
            plistlib.dump({"Label": LABEL, "ProgramArguments": cmd, "RunAtLoad": True,
                           "ProcessType": "Interactive"}, f)
    elif sys.platform == "win32":
        import subprocess
        import winreg
        line = subprocess.list2cmdline(cmd)
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, "wurubururu", 0, winreg.REG_SZ, line)
    else:
        raise OSError("이 운영체제에서는 자동 실행을 지원하지 않습니다")


def disable() -> None:
    if sys.platform == "darwin":
        try:
            os.remove(_plist_path())
        except FileNotFoundError:
            pass
    elif sys.platform == "win32":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, "wurubururu")
        except OSError:
            pass


def set_enabled(on: bool) -> None:
    enable() if on else disable()
