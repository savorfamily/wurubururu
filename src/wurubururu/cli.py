"""명령줄 진입점.

  wurubururu run                 상주 실행 (알림 감시 + 설정 화면 + 트레이)
  wurubururu info                기기 인식 확인
  wurubururu leds                LED 비트 하나씩 점등 (어느 귀·어느 색인지 확인용)
  wurubururu buttons             버튼 값 실시간 표시 (어느 비트가 어느 버튼인지 확인용)
  wurubururu blink <패턴> [횟수]  LED 패턴 재생 (left, right, both, urgent, alarm ...)
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
import urllib.request

from . import __version__, actions, config
from .device import ADDR_IN, DeviceError, open_device
from .leds import BUILTIN, TICK, parse_pattern


def cmd_info(args, cfg):
    dev = open_device(mock=args.mock)
    print(dev.describe() if hasattr(dev, "describe") else "가짜 장치(mock)")
    print(f"입력 레지스터 {ADDR_IN:#06x} = {dev.read_buttons():#04x}")


def cmd_leds(args, cfg):
    dev = open_device(mock=args.mock, verbose=True)
    for bit in (0x80, 0x40, 0x20, 0x10):
        print(f"출력 {bit:#04x} — 어느 귀가 무슨 색으로 켜지는지 적어 두세요")
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


def cmd_notify(args, cfg):
    body = {"title": args.title, "body": args.body, "url": args.url,
            "priority": "urgent" if args.urgent else "normal"}
    req = urllib.request.Request(
        f"http://127.0.0.1:{cfg['web']['port']}/api/notify", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "X-Wurubururu-Token": config.web_token()})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            print(r.read().decode())
    except OSError as e:
        sys.exit(f"실행 중인 우르부르에 연결하지 못했습니다 (wurubururu run 먼저): {e}")


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


def cmd_run(args, cfg):
    from .ai import AIError, get_provider
    from .engine import Engine
    from .sources import build_sources
    from . import tray, web

    mock = args.mock or cfg.get("device", {}).get("mock", False)
    try:
        dev = open_device(mock=mock, verbose=mock)
    except DeviceError as e:
        sys.exit(f"{e}\n기기 없이 시험하려면: wurubururu --mock run")
    try:
        provider = get_provider(cfg.get("ai", {}))
    except AIError as e:
        print(f"AI 설정 오류, AI 없이 실행합니다: {e}")
        provider = None
    engine = Engine(cfg, dev, provider)
    engine.sources = build_sources(cfg)
    engine.start()
    port = int(cfg.get("web", {}).get("port", 8737))
    web.start(engine, port)
    url = f"http://127.0.0.1:{port}/"
    print(f"우르부르 실행 중 — 설정 화면: {url}  (Ctrl+C 종료)")
    try:
        tray.run(engine, url)
    except KeyboardInterrupt:
        pass
    finally:
        engine.stop()


def main(argv=None):
    p = argparse.ArgumentParser(prog="wurubururu", description="우르부르 알림 단말",
                                epilog=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--mock", action="store_true", help="기기 없이 가짜 장치로 실행")
    sub = p.add_subparsers(dest="cmd")
    for name in ("run", "info", "leds", "buttons", "login", "config"):
        sub.add_parser(name)
    b = sub.add_parser("blink")
    b.add_argument("pattern", choices=sorted(BUILTIN))
    b.add_argument("repeat", nargs="?", type=int, default=3)
    n = sub.add_parser("notify")
    n.add_argument("title")
    n.add_argument("body", nargs="?", default="")
    n.add_argument("--url", default="")
    n.add_argument("--urgent", action="store_true")
    sub.add_parser("say").add_argument("text")
    sub.add_parser("ai").add_argument("prompt")
    args = p.parse_args(argv)
    if not args.cmd:
        p.print_help()
        return
    cfg = config.load()
    try:
        globals()[f"cmd_{args.cmd}"](args, cfg)
    except DeviceError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
