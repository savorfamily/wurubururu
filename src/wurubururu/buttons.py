"""버튼 3개(왼발, 오른발, mute)의 누름 동작 판별.

눌렀을 때 비트가 1이 되는지 0이 되는지는 기기에서 확인되지 않았으므로,
시작할 때 읽은 값을 '안 누른 상태'로 삼고 거기서 달라진 비트를 눌림으로 본다.
짧게 / 길게 / 두 번 누름을 구분해 버튼 3개로 9가지 동작을 쓴다.
"""
from __future__ import annotations

import threading
import time
from typing import Callable

from .device import Device, DeviceError

# 실제 기기에서 확인 (macOS, 2026-11-18). 누르면 비트가 1이 된다.
DEFAULT_BITS = {"left": 0x02, "right": 0x01, "mute": 0x04}


class GestureDetector:
    """시간과 값을 넣어 주면 (버튼, 동작) 이벤트를 돌려주는 순수 상태 기계."""

    def __init__(self, bits: dict[str, int] | None = None, long_ms: int = 700,
                 double_ms: int = 350, press_reads: int = 1, release_reads: int = 4,
                 idle: int | None = None):
        """press_reads: 몇 번 연속 눌림으로 읽혀야 누른 것으로 볼지
        release_reads: 몇 번 연속 뗌으로 읽혀야 뗀 것으로 볼지.
        노화된 버튼은 누르는 도중 접촉이 잠깐씩 끊기므로 뗌 쪽을 더 너그럽게 본다."""
        self.bits = dict(bits or DEFAULT_BITS)
        self.long_s = long_ms / 1000
        self.double_s = double_ms / 1000
        self.press_reads = max(1, press_reads)
        self.release_reads = max(1, release_reads)
        self.idle = idle
        self._down: dict[str, bool] = {n: False for n in self.bits}
        self._streak: dict[str, int] = {n: 0 for n in self.bits}   # 현재 상태와 다른 값이 연속으로 읽힌 횟수
        self._down_at: dict[str, float] = {}
        self._long_fired: set[str] = set()
        self._pending_click: dict[str, float] = {}

    def feed(self, raw: int, now: float) -> list[tuple[str, str]]:
        if self.idle is None:
            self.idle = raw
        pressed = (raw ^ self.idle) & 0x0F
        events: list[tuple[str, str]] = []
        for name, bit in self.bits.items():
            reading = bool(pressed & bit)
            if reading == self._down[name]:
                self._streak[name] = 0
                continue
            self._streak[name] += 1
            need = self.release_reads if self._down[name] else self.press_reads
            if self._streak[name] < need:
                continue
            self._streak[name] = 0
            self._down[name] = reading
            if reading:
                self._down_at[name] = now
            else:
                self._on_release(name, now, events)
        for name, t0 in self._down_at.items():
            if name not in self._long_fired and now - t0 >= self.long_s:
                self._long_fired.add(name)
                self._pending_click.pop(name, None)
                events.append((name, "long"))
        for name, t in list(self._pending_click.items()):
            if now - t >= self.double_s and name not in self._down_at:
                del self._pending_click[name]
                events.append((name, "click"))
        return events

    def _on_release(self, name: str, now: float, events: list) -> None:
        self._down_at.pop(name, None)
        if name in self._long_fired:
            self._long_fired.discard(name)
            return
        if name in self._pending_click:
            del self._pending_click[name]
            events.append((name, "double"))
        else:
            self._pending_click[name] = now


class ButtonWatcher:
    def __init__(self, device: Device, callback: Callable[[str, str], None],
                 detector: GestureDetector | None = None, interval: float = 0.02):
        self.device = device
        self.callback = callback
        self.detector = detector or GestureDetector()
        self.interval = interval
        self.error: str | None = None
        self.on_error = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="wurubururu-buttons", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                raw = self.device.read_buttons()
                self.error = None
            except DeviceError as e:
                if self.error != str(e) and self.on_error:
                    self.on_error(str(e))
                self.error = str(e)
                self._stop.wait(2)
                continue
            for name, gesture in self.detector.feed(raw, time.monotonic()):
                try:
                    self.callback(name, gesture)
                except Exception as e:  # 버튼 처리 오류로 감시가 죽지 않게
                    self.error = f"버튼 처리 오류: {e}"
            self._stop.wait(self.interval)
