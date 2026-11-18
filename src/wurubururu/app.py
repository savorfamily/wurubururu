"""상주 프로그램 본체. 기기·엔진·설정 화면을 묶고, 설정이 바뀌면 엔진을 다시 만든다."""
from __future__ import annotations

import json
import sys
import threading
import urllib.request
import webbrowser

from . import config
from .ai import AIError, get_provider
from .device import AutoDevice, Device, MockDevice
from .engine import Engine
from .sources import build_sources


class App:
    def __init__(self, mock: bool = False, echo: bool = False):
        self.cfg = config.load()
        self.mock = mock or bool(self.cfg.get("device", {}).get("mock", False))
        self.echo = echo
        self.device: Device = MockDevice(verbose=echo) if self.mock else AutoDevice()
        self.device.init()
        self.engine: Engine | None = None
        self.ai_error: str | None = None
        self._lock = threading.RLock()
        self.port = int(self.cfg.get("web", {}).get("port", 8737))
        self.url = f"http://127.0.0.1:{self.port}/"
        self.server = None
        self.icon = None                       # 메뉴 막대 아이콘 (tray.py가 채움)
        self.quit_event = threading.Event()

    # ---- 엔진 ----------------------------------------------------------
    def _build_engine(self) -> Engine:
        try:
            provider = get_provider(self.cfg.get("ai", {}))
            self.ai_error = None
        except AIError as e:
            provider, self.ai_error = None, str(e)
        engine = Engine(self.cfg, self.device, provider)
        engine.echo = self.echo
        engine.sources = build_sources(self.cfg)
        if self.ai_error:
            engine.note(f"AI 설정 오류: {self.ai_error}")
        return engine

    def start_engine(self, greet: bool = True) -> None:
        with self._lock:
            self.engine = self._build_engine()
            self.engine.start(greet=greet)

    def reload(self) -> None:
        """설정을 다시 읽고 엔진을 새로 만든다. 확인하지 않은 알림은 넘겨받는다."""
        with self._lock:
            old = self.engine
            alerts = list(old.alerts) if old else []
            posted = set(old._posted) if old else set()
            log = list(old.log) if old else []
            if old:
                old.stop()
            self.cfg = config.load()
            self.engine = self._build_engine()
            self.engine.alerts, self.engine._posted = alerts, posted
            self.engine.log.extend(log)
            self.engine.start(greet=False)
            self.engine.note("설정을 적용했습니다")
            self.engine.refresh_leds()

    def note(self, msg: str) -> None:
        if self.engine:
            self.engine.note(msg)

    def quit(self) -> None:
        """설정 화면이나 메뉴에서 끝내기."""
        self.quit_event.set()
        icon = self.icon
        if icon is None:
            return
        if sys.platform == "darwin":
            try:
                from PyObjCTools import AppHelper
                AppHelper.callAfter(icon.stop)
                return
            except Exception:
                pass
        icon.stop()

    def device_status(self) -> dict:
        if isinstance(self.device, MockDevice):
            return {"connected": True, "mock": True, "error": None}
        dev: AutoDevice = self.device  # type: ignore[assignment]
        err = (self.engine.leds.error or self.engine.buttons.error) if self.engine else None
        return {"connected": dev.connected and not err, "mock": False, "error": err or dev.last_error}

    # ---- 실행 ----------------------------------------------------------
    def already_running(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.url}api/status", timeout=1.5) as r:
                return "alerts" in json.loads(r.read())
        except Exception:
            return False

    def run(self, open_browser: bool = False) -> None:
        from . import tray, web
        if self.already_running():
            webbrowser.open(self.url)
            return
        first = config.is_first_run()
        config.ensure_home()
        self.start_engine(greet=True)
        self.server = web.start(self, self.port)
        if self.echo:
            e = self.engine
            print(f"기기: {'가짜 장치(mock)' if self.mock else ('우르부르 연결됨' if self.device_status()['connected'] else '연결 안 됨')}"
                  f"  /  AI: {e.provider.name if e.provider else '없음'}"
                  f"  /  알림 소스: {', '.join(s.name for s in e.sources) or '없음'}")
            print(f"우르부르르 실행 중 — 설정 화면: {self.url}  (Ctrl+C 종료)", flush=True)
        if first or open_browser:
            threading.Timer(1.0, webbrowser.open, args=(self.url,)).start()
        try:
            tray.run(self)
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        with self._lock:
            if self.engine:
                self.engine.stop()
            if self.server:
                self.server.shutdown()
            self.device.close()


def frozen() -> bool:
    return bool(getattr(sys, "frozen", False))
