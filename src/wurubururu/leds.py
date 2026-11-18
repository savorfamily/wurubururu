"""LED 패턴 재생기.

패턴은 원본과 같은 형식인 (출력값, 지속시간 x 0.1초) 목록이다.
- 바탕 패턴(base): 확인하지 않은 알림이 있는 동안 계속 반복
- 일회성 패턴(flash): 잠깐 끼어들었다가 바탕 패턴으로 복귀
"""
from __future__ import annotations

import threading
from collections import deque

from .device import Device, DeviceError

Step = tuple[int, int]
TICK = 0.1

# 실제 기기에서 확인한 비트 배치 (macOS, 2026-11-18)
# 귀마다 다리 두 개짜리 2색 LED라서 같은 귀의 빨강·초록을 동시에 켜면 꺼진다 (노랑 불가).
L_RED, L_GREEN, R_RED, R_GREEN = 0x80, 0x40, 0x20, 0x10
RED = L_RED | R_RED
GREEN = L_GREEN | R_GREEN

BUILTIN: dict[str, list[Step]] = {
    # 원본 WebToy에 내장돼 있던 세 패턴 (빨강·초록 교대)
    "left": [(L_RED, 5), (L_GREEN, 5)],
    "right": [(R_GREEN, 5), (R_RED, 5)],
    "both": [(L_RED | R_GREEN, 5), (L_GREEN | R_RED, 5)],
    # 초록: 보통 알림
    "green_left": [(L_GREEN, 5), (0x00, 5)],
    "green_right": [(R_GREEN, 5), (0x00, 5)],
    "pulse": [(GREEN, 2), (0x00, 8)],
    # 빨강: 급한 알림
    "red_left": [(L_RED, 5), (0x00, 5)],
    "red_right": [(R_RED, 5), (0x00, 5)],
    "urgent": [(RED, 1), (0x00, 1)],
    "alarm": [(L_RED, 2), (R_RED, 2)],
    # 켜 두기
    "solid_left": [(L_GREEN, 10)],
    "solid_right": [(R_GREEN, 10)],
    "test": [(L_RED, 3), (L_GREEN, 3), (R_RED, 3), (R_GREEN, 3), (RED, 3), (GREEN, 3)],
    "off": [(0x00, 1)],
}


def ear_conflict(value: int) -> bool:
    """같은 귀의 빨강·초록을 함께 켜는 값인지 (그 귀는 꺼진다)."""
    return (value & 0xC0) == 0xC0 or (value & 0x30) == 0x30


def parse_pattern(spec) -> list[Step]:
    """이름 또는 [[값, 틱], ...] 목록을 패턴으로 바꾼다."""
    if isinstance(spec, str):
        if spec not in BUILTIN:
            raise ValueError(f"모르는 LED 패턴: {spec}")
        return BUILTIN[spec]
    steps = [(int(v) & 0xF0, max(1, int(t))) for v, t in spec]
    if not steps:
        raise ValueError("빈 패턴")
    return steps


class LedPlayer:
    def __init__(self, device: Device):
        self.device = device
        self._base: list[Step] | None = None
        self._flashes: deque[tuple[list[Step], int]] = deque()
        self._changed = threading.Event()
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self.error: str | None = None
        self.on_error = None   # 오류가 새로 생기면 불릴 함수
        self._thread = threading.Thread(target=self._run, name="wurubururu-led", daemon=True)
        self._thread.start()

    def set_base(self, pattern) -> None:
        """계속 반복할 패턴을 지정한다. None이면 끈다."""
        with self._lock:
            self._base = parse_pattern(pattern) if pattern else None
        self._changed.set()

    def flash(self, pattern, repeat: int = 3) -> None:
        with self._lock:
            self._flashes.append((parse_pattern(pattern), max(1, repeat)))
        self._changed.set()

    def stop(self) -> None:
        self._stop.set()
        self._changed.set()
        self._thread.join(timeout=2)
        self._write(0)

    def _write(self, value: int) -> None:
        try:
            self.device.write_leds(value)
            self.error = None
        except DeviceError as e:
            if self.error != str(e) and self.on_error:
                self.on_error(str(e))
            self.error = str(e)

    def _play(self, steps: list[Step], interruptible: bool) -> bool:
        """한 바퀴 재생. 도중에 상태가 바뀌어 중단됐으면 False."""
        for value, ticks in steps:
            self._write(value)
            if interruptible:
                if self._changed.wait(ticks * TICK):
                    return False
            elif self._stop.wait(ticks * TICK):
                return False
            if self._stop.is_set():
                return False
        return True

    def _run(self) -> None:
        while not self._stop.is_set():
            self._changed.clear()
            with self._lock:
                flash = self._flashes.popleft() if self._flashes else None
                base = self._base
            if flash:
                steps, repeat = flash
                for _ in range(repeat):
                    self._changed.clear()
                    self._play(steps, interruptible=False)
                    if self._stop.is_set():
                        return
                continue
            if base:
                self._play(base, interruptible=True)
                continue
            self._write(0)
            self._changed.wait()
