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


def run(app) -> None:
    """메인 스레드에서 호출한다. 끝내기를 누를 때까지 돌아오지 않는다."""
    try:
        import pystray
    except Exception:   # 설치 안 됨, 또는 화면이 없는 환경 (리눅스 서버 등)
        while True:
            time.sleep(3600)

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
    pystray.Icon("wurubururu", icon_image(64), "우르부르", menu).run()
