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


# Apple Silicon 맥의 Homebrew는 /opt/homebrew 에 설치해서 pyusb가 libusb를 못 찾는 경우가 많다
_LIBUSB_CANDIDATES = (
    "/opt/homebrew/lib/libusb-1.0.dylib",
    "/usr/local/lib/libusb-1.0.dylib",
    "/opt/local/lib/libusb-1.0.dylib",
)


def _libusb_backend():
    """libusb 백엔드를 찾는다. 순서: 함께 설치된 libusb-package → 시스템 → Homebrew 경로."""
    import os
    import sys
    try:
        import usb.backend.libusb1 as libusb1
    except ImportError:  # pragma: no cover
        return None
    try:
        import libusb_package  # 맥·윈도우용 libusb를 품고 있는 패키지 (앱 빌드에 동봉)
        backend = libusb_package.get_libusb1_backend()
        if backend is not None:
            return backend
    except Exception:
        pass
    backend = libusb1.get_backend()
    if backend is not None or sys.platform != "darwin":
        return backend
    for path in _LIBUSB_CANDIDATES:
        if os.path.exists(path):
            backend = libusb1.get_backend(find_library=lambda _name, p=path: p)
            if backend is not None:
                return backend
    return None


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
            self._dev = usb.core.find(idVendor=vid, idProduct=pid, backend=_libusb_backend())
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
            import usb.util
            usb.util.dispose_resources(self._dev)
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
            def ear(red, green):
                return {0: "··", red: "빨", green: "초", red | green: "××"}[self.leds & (red | green)]
            print(f"[mock LED] 왼쪽 {ear(0x80, 0x40):<2}  오른쪽 {ear(0x20, 0x10):<2}  ({self.leds:#04x})")

    def read_buttons(self) -> int:
        return self.buttons


class AutoDevice(Device):
    """기기를 뽑았다 다시 꽂아도 알아서 다시 연결하는 장치.
    연결이 없을 때 읽기·쓰기는 DeviceError를 내고, 몇 초마다 다시 찾아본다."""

    def __init__(self, factory=None, retry: float = 3.0):
        self._factory = factory or UsbDevice
        self._retry = retry
        self._dev: Device | None = None
        self._next_try = 0.0
        self._lock = threading.Lock()
        self.last_error: str | None = None

    @property
    def connected(self) -> bool:
        return self._dev is not None

    def _get(self) -> Device:
        import time
        with self._lock:
            if self._dev is not None:
                return self._dev
            if time.monotonic() < self._next_try:
                raise DeviceError(self.last_error or "우르부르가 연결되어 있지 않습니다")
            self._next_try = time.monotonic() + self._retry
            try:
                dev = self._factory()
                dev.init()
            except DeviceError as e:
                self.last_error = str(e)
                raise
            self._dev, self.last_error = dev, None
            return dev

    def _drop(self, e: DeviceError) -> None:
        with self._lock:
            if self._dev is not None:
                try:
                    self._dev.close()
                except Exception:
                    pass
            self._dev = None
            self.last_error = str(e)

    def init(self) -> None:
        try:
            self._get()
        except DeviceError:
            pass   # 나중에 꽂으면 그때 초기화한다

    def write_leds(self, mask: int) -> None:
        dev = self._get()
        try:
            dev.write_leds(mask)
        except DeviceError as e:
            self._drop(e)
            raise

    def read_buttons(self) -> int:
        dev = self._get()
        try:
            return dev.read_buttons()
        except DeviceError as e:
            self._drop(e)
            raise

    def describe(self) -> str:
        dev = self._get()
        return dev.describe() if hasattr(dev, "describe") else ""

    def close(self) -> None:
        with self._lock:
            if self._dev is not None:
                self._dev.close()
            self._dev = None


def open_device(mock: bool = False, verbose: bool = False) -> Device:
    dev: Device = MockDevice(verbose=verbose) if mock else UsbDevice()
    dev.init()
    return dev
