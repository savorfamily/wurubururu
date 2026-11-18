"""메뉴 막대(맥) / 알림 영역(윈도우) 아이콘. pystray가 없으면 아이콘 없이 대기한다."""
from __future__ import annotations

import time
import webbrowser

from . import autostart


def icon_image(size: int = 64):
    """우르부르 실루엣: 몸통, 양쪽 귀, 가운데 삼각 스피커."""
    from PIL import Image, ImageDraw
    s = size / 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    body = (70, 120, 200, 255)
    d.rounded_rectangle((12 * s, 12 * s, 52 * s, 60 * s), radius=12 * s, fill=body)
    d.polygon([(10 * s, 6 * s), (24 * s, 14 * s), (12 * s, 24 * s)], fill=body)
    d.polygon([(54 * s, 6 * s), (40 * s, 14 * s), (52 * s, 24 * s)], fill=body)
    d.ellipse((9 * s, 4 * s, 17 * s, 12 * s), fill=(240, 180, 60, 255))
    d.ellipse((47 * s, 4 * s, 55 * s, 12 * s), fill=(240, 180, 60, 255))
    d.polygon([(24 * s, 28 * s), (40 * s, 28 * s), (32 * s, 42 * s)], fill=(40, 40, 50, 255))
    return img


def _log_error(msg: str) -> None:
    import sys
    import traceback
    print(f"[tray] {msg}", file=sys.stderr, flush=True)
    traceback.print_exc(file=sys.stderr)


def _wait_forever(app) -> None:
    """아이콘 없이 계속 실행한다. 설정 화면의 '끝내기'로 끝낼 수 있다."""
    app.quit_event.wait()


def run(app) -> None:
    """메인 스레드에서 호출한다. 끝내기를 누를 때까지 돌아오지 않는다."""
    import sys
    try:
        import pystray
    except Exception:   # 설치 안 됨, 또는 화면이 없는 환경 (리눅스 서버 등)
        if sys.platform in ("darwin", "win32"):
            _log_error("메뉴 막대 아이콘 라이브러리를 불러오지 못했습니다")
            app.note("메뉴 막대 아이콘을 띄우지 못했습니다. 설정 화면에서 끝낼 수 있습니다")
            webbrowser.open(app.url)
        _wait_forever(app)
        return

    def eng():
        return app.engine

    def toggle_autostart(icon, _item):
        try:
            autostart.set_enabled(not autostart.is_enabled())
        except OSError:
            pass

    item = pystray.MenuItem
    menu = pystray.Menu(
        item("설정 열기", lambda: webbrowser.open(app.url), default=True),
        pystray.Menu.SEPARATOR,
        item("알림 모두 확인", lambda: eng().ack_all()),
        item("방해 금지", lambda: eng().toggle_dnd(), checked=lambda _: bool(eng() and eng().dnd)),
        item("브리핑 듣기", lambda: eng().briefing()),
        item("집중 타이머", lambda: eng().pomodoro_toggle()),
        pystray.Menu.SEPARATOR,
        item("로그인 시 자동 실행", toggle_autostart, checked=lambda _: autostart.is_enabled(),
             visible=autostart.supported()),
        item("끝내기", lambda icon, _: icon.stop()),
    )
    icon = pystray.Icon("wurubururu", icon_image(64), "우르부르르", menu)

    def show(ic):
        try:
            ic.visible = True
            app.note("메뉴 막대 아이콘 표시")
        except Exception:
            _log_error("아이콘을 표시하지 못했습니다")

    def setup(ic):
        # macOS는 화면 요소를 메인 스레드에서만 바꿔야 한다. 기본 동작은 다른 스레드에서 바꿔서
        # 최신 macOS에서 아이콘이 안 보일 수 있다.
        if sys.platform == "darwin":
            try:
                from PyObjCTools import AppHelper
                AppHelper.callAfter(show, ic)
                return
            except Exception:
                _log_error("메인 스레드 예약 실패, 기본 방식으로 표시합니다")
        show(ic)

    app.icon = icon
    try:
        icon.run(setup=setup)
    except Exception:
        _log_error("메뉴 막대 아이콘 실행 중 오류")
        app.note("메뉴 막대 아이콘을 띄우지 못했습니다. 설정 화면에서 끝낼 수 있습니다")
        app.icon = None
        webbrowser.open(app.url)
        _wait_forever(app)
