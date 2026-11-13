"""규칙 엔진: 알림을 모으고, LED 패턴을 정하고, 버튼 명령을 실행한다."""
from __future__ import annotations

import itertools
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass, field

from . import actions
from .ai import AIError, Provider
from .buttons import ButtonWatcher, GestureDetector
from .device import Device
from .leds import LedPlayer

_ids = itertools.count(1)


@dataclass
class Alert:
    kind: str                 # mail | calendar | site | pomodoro | notify
    title: str
    body: str = ""
    url: str = ""
    priority: str = "normal"  # urgent | normal | ignore
    summary: str = ""
    key: str = ""             # 같은 사건을 다시 찾을 때 쓰는 식별자
    id: int = field(default_factory=lambda: next(_ids))
    created: float = field(default_factory=time.time)


class Engine:
    def __init__(self, cfg: dict, device: Device, provider: Provider | None = None,
                 speak=actions.speak, open_url=actions.open_url):
        self.cfg = cfg
        self.device = device
        self.provider = provider
        self._speak, self._open_url = speak, open_url
        self.alerts: list[Alert] = []
        self._posted: set[tuple[str, str]] = set()   # 이미 알린 사건 (확인 후 다시 울리지 않게)
        self.log: deque[str] = deque(maxlen=80)
        self.dnd_until = 0.0
        self.focus_until = 0.0
        self._focus_timer: threading.Timer | None = None
        self._lock = threading.RLock()
        self.leds = LedPlayer(device)
        self.radio = actions.Radio(cfg.get("radio", {}))
        b = dict(cfg.get("device", {}).get("buttons", {}))
        detector = GestureDetector(
            bits={k: int(b[k]) for k in ("left", "right", "mute") if k in b} or None,
            long_ms=int(b.get("long_ms", 700)), double_ms=int(b.get("double_ms", 350)))
        self.buttons = ButtonWatcher(device, self.on_button, detector)
        self.sources: list = []
        self._threads: list[threading.Thread] = []
        self._stop = threading.Event()
        self.commands = {
            "open_latest": self.open_latest, "speak_latest": self.speak_latest,
            "ack_all": self.ack_all, "toggle_dnd": self.toggle_dnd, "briefing": self.briefing,
            "radio_toggle": lambda: self.say(self.radio.toggle()),
            "radio_next": lambda: self.say(self.radio.next()),
            "pomodoro_toggle": self.pomodoro_toggle, "none": lambda: None,
        }

    # ---- 실행 / 종료 ------------------------------------------------
    def start(self) -> None:
        self.buttons.start()
        for src in self.sources:
            t = threading.Thread(target=self._run_source, args=(src,), daemon=True,
                                 name=f"wuruburu-{src.name}")
            t.start()
            self._threads.append(t)
        self.leds.flash("test", 1)
        self.note("시작")

    def stop(self) -> None:
        self._stop.set()
        self.radio.stop()
        if self._focus_timer:
            self._focus_timer.cancel()
        self.buttons.stop()
        self.leds.stop()

    def _run_source(self, src) -> None:
        while not self._stop.is_set():
            try:
                src.poll(self)
                src.error = None
            except Exception as e:
                src.error = str(e)
                self.note(f"[{src.name}] 오류: {e}")
            self._stop.wait(src.interval)

    def note(self, msg: str) -> None:
        self.log.append(f"{time.strftime('%H:%M:%S')} {msg}")

    # ---- 알림 -------------------------------------------------------
    @property
    def dnd(self) -> bool:
        return time.time() < self.dnd_until

    def post(self, alert: Alert) -> bool:
        if alert.priority == "ignore":
            self.note(f"무시: {alert.title}")
            return False
        with self._lock:
            if alert.key:
                if (alert.kind, alert.key) in self._posted:
                    return False
                self._posted.add((alert.kind, alert.key))
                if len(self._posted) > 5000:
                    self._posted = {(a.kind, a.key) for a in self.alerts}
            self.alerts.append(alert)
            del self.alerts[:-50]
        self.note(f"알림 [{alert.kind}/{alert.priority}] {alert.title}")
        self.refresh_leds()
        return True

    def resolve(self, kind: str, key: str) -> None:
        """사건이 저절로 끝났을 때(사이트 복구 등) 해당 알림을 내린다."""
        with self._lock:
            self._posted.discard((kind, key))
            self.alerts = [a for a in self.alerts if not (a.kind == kind and a.key == key)]
        self.refresh_leds()

    def top(self) -> Alert | None:
        with self._lock:
            if not self.alerts:
                return None
            return max(self.alerts, key=lambda a: (a.priority == "urgent", a.created))

    def pattern_for(self, alert: Alert):
        p = self.cfg.get("patterns", {})
        return p.get(f"{alert.kind}.{alert.priority}") or p.get(f"{alert.kind}.normal") or "pulse"

    def refresh_leds(self) -> None:
        top = self.top()
        if top and (not self.dnd or top.priority == "urgent"):
            pattern = self.pattern_for(top)
        elif time.time() < self.focus_until:
            pattern = self.cfg.get("patterns", {}).get("focus", "solid_right")
        else:
            pattern = None
        try:
            self.leds.set_base(pattern)
        except ValueError as e:
            self.note(f"LED 패턴 오류: {e}")
            self.leds.set_base("pulse")

    def say(self, text: str) -> None:
        if text:
            self.note(f"말하기: {text[:60]}")
            self._speak(text, self.cfg.get("speech", {}))

    # ---- AI ---------------------------------------------------------
    def triage_mail(self, sender: str, subject: str, snippet: str) -> dict:
        if not self.provider:
            return {"priority": "normal", "summary": ""}
        if self.cfg.get("ai", {}).get("privacy", "headers") != "snippet":
            snippet = ""
        try:
            return self.provider.triage(sender, subject, snippet)
        except AIError as e:
            self.note(f"AI 분류 실패: {e}")
            return {"priority": "normal", "summary": ""}

    # ---- 버튼 명령 --------------------------------------------------
    def on_button(self, name: str, gesture: str) -> None:
        command = self.cfg.get("buttons", {}).get(f"{name}.{gesture}", "none")
        self.note(f"버튼 {name}.{gesture} → {command}")
        self.run_command(command)

    def run_command(self, command: str) -> None:
        fn = self.commands.get(command)
        if fn is None:
            self.note(f"모르는 명령: {command}")
            return
        fn()

    def _ack(self, alert: Alert) -> None:
        with self._lock:
            self.alerts = [a for a in self.alerts if a.id != alert.id]
        self.refresh_leds()

    def open_latest(self) -> None:
        top = self.top()
        if not top:
            return
        if top.url:
            self._open_url(top.url)
        self._ack(top)

    def speak_latest(self) -> None:
        top = self.top()
        if not top:
            self.say("새 알림이 없습니다")
            return
        text = top.summary
        if not text and self.provider and top.kind != "mail":
            try:
                text = self.provider.summarize(top.title, top.body)
            except AIError as e:
                self.note(f"AI 요약 실패: {e}")
        self.say(text or top.title)

    def ack_all(self) -> None:
        with self._lock:
            self.alerts.clear()
        self.refresh_leds()

    def toggle_dnd(self) -> None:
        if self.dnd:
            self.dnd_until = 0.0
            self.say("방해 금지 해제")
        else:
            minutes = int(self.cfg.get("dnd", {}).get("minutes", 60))
            self.dnd_until = time.time() + minutes * 60
            self.say(f"{minutes}분 동안 방해 금지")
        self.refresh_leds()

    def pomodoro_toggle(self) -> None:
        if self._focus_timer:
            self._focus_timer.cancel()
            self._focus_timer = None
            self.focus_until = 0.0
            self.say("집중 타이머 중지")
        else:
            minutes = int(self.cfg.get("pomodoro", {}).get("work_minutes", 25))
            self.focus_until = time.time() + minutes * 60
            self._focus_timer = threading.Timer(minutes * 60, self._focus_done)
            self._focus_timer.daemon = True
            self._focus_timer.start()
            self.say(f"{minutes}분 집중 시작")
        self.refresh_leds()

    def _focus_done(self) -> None:
        self._focus_timer = None
        self.focus_until = 0.0
        rest = int(self.cfg.get("pomodoro", {}).get("break_minutes", 5))
        self.post(Alert("pomodoro", "집중 시간 끝", f"{rest}분 쉬세요", key=f"pomo-{time.time():.0f}"))
        self.say(f"집중 시간이 끝났습니다. {rest}분 쉬세요")

    def briefing(self) -> None:
        with self._lock:
            lines = [f"[{a.kind}] {a.title} {a.summary}".strip() for a in self.alerts]
        for src in self.sources:
            lines += getattr(src, "briefing_lines", lambda: [])()
        if not lines:
            self.say("전할 소식이 없습니다")
            return
        text = ""
        if self.provider:
            try:
                text = self.provider.briefing(lines)
            except AIError as e:
                self.note(f"AI 브리핑 실패: {e}")
        self.say(text or f"알림 {len(lines)}건. " + ". ".join(lines[:5]))

    # ---- 상태 -------------------------------------------------------
    def status(self) -> dict:
        with self._lock:
            alerts = [asdict(a) for a in self.alerts]
        return {
            "alerts": alerts, "dnd": self.dnd, "focus": time.time() < self.focus_until,
            "provider": self.provider.name if self.provider else "none",
            "radio": self.radio.current() if self.radio.playing else "",
            "device_error": self.leds.error or self.buttons.error,
            "sources": [{"name": s.name, "error": s.error} for s in self.sources],
            "log": list(self.log)[-30:],
        }
