"""우르부르 USB 장치 계층.

원본 WebToy v1.6.6.0 정적 분석으로 복원한 프로토콜 (docs/PROTOCOL.md 참고):
  읽기  : 벤더 컨트롤 IN  (0xC0), bRequest=5, wIndex=레지스터 주소
  쓰기  : 벤더 컨트롤 OUT (0x40), bRequest=4, wIndex=레지스터 주소
"""
from __future__ import annotations

import threading

VID, PID = 0x074D, 0x3552
REQ_WRITE, REQ_READ = 4, 5
ADDR_INIT_A, ADDR_INIT_B = 0xB051, 0x8087
ADDR_OUT, ADDR_IN = 0xB0A0, 0xB0A2
INIT_VALUE = 0xF0


class DeviceError(Exception):
    """장치를 찾지 못했거나 통신에 실패했을 때."""


class Device:
    """LED 4비트 쓰기와 버튼 3비트 읽기만 아는 최소 인터페이스."""

    def init(self) -> None: ...
    def write_leds(self, mask: int) -> None: ...
    def read_buttons(self) -> int: ...
    def close(self) -> None: ...


class UsbDevice(Device):
    def __init__(self, vid: int = VID, pid: int = PID):
        try:
            import usb.core
        except ImportError as e:  # pragma: no cover
            raise DeviceError("pyusb가 설치되어 있지 않습니다: pip install pyusb") from e
        self._usb = usb.core
        self._lock = threading.Lock()
        try:
            self._dev = usb.core.find(idVendor=vid, idProduct=pid)
        except usb.core.NoBackendError as e:
            raise DeviceError("libusb를 찾지 못했습니다 (macOS: brew install libusb)") from e
        if self._dev is None:
            raise DeviceError(f"우르부르를 찾지 못했습니다 (VID {vid:04X} / PID {pid:04X})")

    def _set_mem(self, addr: int, value: int) -> None:
        try:
            with self._lock:
                self._dev.ctrl_transfer(0x40, REQ_WRITE, 0, addr, bytes([value & 0xFF]), timeout=1000)
        except self._usb.USBError as e:
            raise DeviceError(f"쓰기 실패 @{addr:#06x}: {e}") from e

    def _get_mem(self, addr: int) -> int:
        try:
            with self._lock:
                data = self._dev.ctrl_transfer(0xC0, REQ_READ, 0, addr, 1, timeout=1000)
        except self._usb.USBError as e:
            raise DeviceError(f"읽기 실패 @{addr:#06x}: {e}") from e
        if len(data) != 1:
            raise DeviceError(f"읽기 길이 오류 @{addr:#06x}")
        return data[0]

    def init(self) -> None:
        self._set_mem(ADDR_INIT_A, INIT_VALUE)
        self._set_mem(ADDR_INIT_B, INIT_VALUE)

    def write_leds(self, mask: int) -> None:
        self._set_mem(ADDR_OUT, mask & 0xF0)

    def read_buttons(self) -> int:
        return self._get_mem(ADDR_IN)

    def describe(self) -> str:
        d = self._dev
        lines = [f"{d.manufacturer!r} / {d.product!r}  USB {d.bcdUSB:#06x}"]
        for cfg in d:
            for intf in cfg:
                eps = ", ".join(f"EP {e.bEndpointAddress:#04x}" for e in intf)
                lines.append(
                    f"  인터페이스 {intf.bInterfaceNumber} alt {intf.bAlternateSetting} "
                    f"class {intf.bInterfaceClass:#04x}  {eps}"
                )
        return "\n".join(lines)

    def close(self) -> None:
        try:
            self._usb.util.dispose_resources(self._dev)  # type: ignore[attr-defined]
        except Exception:
            pass


class MockDevice(Device):
    """기기 없이 개발·테스트할 때 쓰는 가짜 장치."""

    def __init__(self, verbose: bool = False):
        self.leds = 0
        self.buttons = 0
        self.history: list[int] = []
        self.verbose = verbose
        self.initialized = False

    def init(self) -> None:
        self.initialized = True

    def write_leds(self, mask: int) -> None:
        self.leds = mask & 0xF0
        self.history.append(self.leds)
        if self.verbose:
            bits = "".join("●" if self.leds & b else "○" for b in (0x80, 0x40, 0x20, 0x10))
            print(f"[mock LED] {bits}  ({self.leds:#04x})")

    def read_buttons(self) -> int:
        return self.buttons


def open_device(mock: bool = False, verbose: bool = False) -> Device:
    dev: Device = MockDevice(verbose=verbose) if mock else UsbDevice()
    dev.init()
    return dev
