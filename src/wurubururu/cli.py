"""명령줄 진입점.

  wurubururu run                 상주 실행 (알림 감시 + 설정 화면 + 트레이)
  wurubururu info                기기 인식 확인
  wurubururu leds                LED 비트 하나씩 점등 (어느 귀·어느 색인지 확인용)
  wurubururu buttons             버튼 값 실시간 표시 (어느 비트가 어느 버튼인지 확인용)
  wurubururu blink <패턴> [횟수]  LED 패턴 재생 (green_left, urgent, alarm, both ...)
  wurubururu led <값> [초]       LED에 값을 그대로 씀 (예: 0x90 = 왼쪽 빨강 + 오른쪽 초록)
  wurubururu notify "제목" [본문] 실행 중인 프로그램에 알림 보내기 (작업 완료 알림 등)
  wurubururu say "문장"           우르부르 스피커로 말하기
  wurubururu ai "질문"            설정된 AI 연결 시험
  wurubururu login               Google 계정 연결
  wurubururu config              설정 파일 위치 출력 (없으면 생성)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

from . import __version__, actions, config
from .device import ADDR_IN, DeviceError, open_device
from .leds import BUILTIN, TICK, parse_pattern

LED_NAMES = {0x80: "왼쪽 빨강", 0x40: "왼쪽 초록", 0x20: "오른쪽 빨강", 0x10: "오른쪽 초록"}


def cmd_info(args, cfg):
    dev = open_device(mock=args.mock)
    print(dev.describe() if hasattr(dev, "describe") else "가짜 장치(mock)")
    print(f"입력 레지스터 {ADDR_IN:#06x} = {dev.read_buttons():#04x}")


def cmd_leds(args, cfg):
    dev = open_device(mock=args.mock, verbose=True)
    for bit in (0x80, 0x40, 0x20, 0x10):
        print(f"출력 {bit:#04x} — {LED_NAMES[bit]}")
        dev.write_leds(bit)
        time.sleep(1.5)
    dev.write_leds(0)


def cmd_buttons(args, cfg):
    dev = open_device(mock=args.mock)
    print("버튼을 하나씩 눌러 보세요 (Ctrl+C 종료)")
    last = None
    try:
        while True:
            v = dev.read_buttons()
            if v != last:
                print(f"{v:#04x}  bits {v:08b}")
                last = v
            time.sleep(0.03)
    except KeyboardInterrupt:
        pass


def cmd_blink(args, cfg):
    dev = open_device(mock=args.mock, verbose=args.mock)
    for _ in range(args.repeat):
        for value, ticks in parse_pattern(args.pattern):
            dev.write_leds(value)
            time.sleep(ticks * TICK)
    dev.write_leds(0)


def cmd_led(args, cfg):
    from .leds import ear_conflict
    if ear_conflict(args.value):
        print("주의: 같은 귀의 빨강·초록을 동시에 켜면 그 귀는 꺼집니다")
    dev = open_device(mock=args.mock, verbose=args.mock)
    dev.write_leds(args.value)
    time.sleep(args.seconds)
    dev.write_leds(0)


def cmd_notify(args, cfg):
    body = {"title": args.title, "body": args.body, "url": args.url,
            "priority": "urgent" if args.urgent else "normal"}
    req = urllib.request.Request(
        f"http://127.0.0.1:{cfg['web']['port']}/api/notify", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "X-Wurubururu-Token": config.web_token()})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            ok = json.loads(r.read().decode()).get("ok")
        print("알림을 보냈습니다" if ok else "같은 알림이 이미 있어서 무시됐습니다")
    except urllib.error.HTTPError as e:
        sys.exit(f"우르부르르가 알림을 거절했습니다 (HTTP {e.code})")
    except OSError as e:
        sys.exit(f"실행 중인 우르부르르에 연결하지 못했습니다 (wurubururu run 먼저): {e}")


def cmd_say(args, cfg):
    if not actions.speak(args.text, cfg.get("speech", {})):
        sys.exit("음성 출력을 시작하지 못했습니다")


def cmd_ai(args, cfg):
    from .ai import AIError, get_provider
    try:
        provider = get_provider(cfg.get("ai", {}))
        if provider is None:
            sys.exit("AI가 꺼져 있습니다 (설정의 [ai] provider)")
        print(f"[{provider.name}]", provider.complete("짧게 답한다.", args.prompt).strip())
    except AIError as e:
        sys.exit(f"AI 오류: {e}")


def cmd_login(args, cfg):
    from .sources.google_auth import GoogleSetupError, credentials
    try:
        credentials(cfg.get("google", {}), interactive=True)
        print("Google 계정을 연결했습니다")
    except GoogleSetupError as e:
        sys.exit(str(e))


def cmd_config(args, cfg):
    config.ensure_home()
    print(config.CONFIG_PATH)


def cmd_selftest(args, cfg):
    """앱으로 묶였을 때 필요한 것이 다 들어 있는지 점검한다 (빌드 확인용)."""
    import importlib
    from pathlib import Path
    results = {}

    def check(name, fn):
        try:
            v = fn()
            results[name] = "ok" if v in (None, True) else str(v)
        except Exception as e:
            results[name] = f"FAIL: {type(e).__name__}: {e}"

    from importlib import resources
    check("web.html", lambda: len(resources.files("wurubururu").joinpath("web.html").read_text("utf-8")) > 1000)
    check("default_config", lambda: bool(config.defaults()["ai"]["provider"]))
    check("intro.mp3", lambda: Path(actions.bundled_intro()).stat().st_size > 100000)
    from .device import _libusb_backend
    check("libusb", lambda: _libusb_backend() is not None)
    check("keyring", lambda: type(importlib.import_module("keyring").get_keyring()).__name__)
    mods = ["PIL", "googleapiclient.discovery", "google_auth_oauthlib.flow"]
    if sys.platform in ("darwin", "win32"):
        mods.append("pystray")   # 리눅스 서버에서는 화면이 없어 불러올 수 없음
    for mod in mods:
        check(mod, lambda m=mod: importlib.import_module(m) and None)
    check("gmail discovery", lambda: __import__("googleapiclient.discovery_cache", fromlist=["get_static_doc"])
          .get_static_doc("gmail", "v1") is not None)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    if any(v.startswith("FAIL") for v in results.values()):
        sys.exit(1)


def cmd_run(args, cfg):
    from .app import App
    App(mock=args.mock, echo=True).run(open_browser=args.open)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):   # 한글을 못 찍는 콘솔에서도 죽지 않게
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass
    p = argparse.ArgumentParser(prog="wurubururu", description="우르부르르 — 우르부르 알림 단말 프로그램",
                                epilog=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--mock", action="store_true", help="기기 없이 가짜 장치로 실행")
    sub = p.add_subparsers(dest="cmd")
    for name in ("info", "leds", "buttons", "login", "config", "selftest"):
        sub.add_parser(name)
    sub.add_parser("run").add_argument("--open", action="store_true", help="설정 화면을 바로 연다")
    b = sub.add_parser("blink")
    b.add_argument("pattern", choices=sorted(BUILTIN))
    b.add_argument("repeat", nargs="?", type=int, default=3)
    l = sub.add_parser("led")
    l.add_argument("value", type=lambda v: int(v, 0))
    l.add_argument("seconds", nargs="?", type=float, default=2.0)
    n = sub.add_parser("notify")
    n.add_argument("title")
    n.add_argument("body", nargs="?", default="")
    n.add_argument("--url", default="")
    n.add_argument("--urgent", action="store_true")
    sub.add_parser("say").add_argument("text")
    sub.add_parser("ai").add_argument("prompt")
    args = p.parse_args(argv)
    if not args.cmd:
        from .app import App, frozen
        if frozen():   # 앱(더블클릭)으로 실행됐을 때. 진행 상황은 기록 파일에 남긴다
            App(echo=True).run()
            return
        p.print_help()
        return
    cfg = config.load()
    try:
        globals()[f"cmd_{args.cmd}"](args, cfg)
    except DeviceError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
