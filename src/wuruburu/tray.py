"""시스템 트레이 아이콘. pystray가 없으면 아이콘 없이 그냥 대기한다."""
from __future__ import annotations

import time
import webbrowser


def _icon_image():
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((12, 14, 52, 60), radius=12, fill=(200, 80, 30, 255))
    d.ellipse((8, 4, 24, 22), fill=(200, 80, 30, 255))
    d.ellipse((40, 4, 56, 22), fill=(200, 80, 30, 255))
    d.ellipse((24, 26, 40, 42), fill=(255, 255, 255, 255))
    return img


def run(engine, url: str) -> None:
    """메인 스레드에서 호출한다. 종료할 때까지 돌아오지 않는다."""
    try:
        import pystray
    except ImportError:
        while True:
            time.sleep(3600)
    item = pystray.MenuItem
    menu = pystray.Menu(
        item("설정 화면 열기", lambda: webbrowser.open(url), default=True),
        item("모두 확인", lambda: engine.ack_all()),
        item("방해 금지", lambda: engine.toggle_dnd(), checked=lambda _: engine.dnd),
        item("브리핑 듣기", lambda: engine.briefing()),
        pystray.Menu.SEPARATOR,
        item("끝내기", lambda icon, _: icon.stop()),
    )
    pystray.Icon("wuruburu", _icon_image(), "우르부르", menu).run()
