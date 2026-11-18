"""앱(더블클릭) 실행 진입점. PyInstaller가 이 파일로 실행 파일을 만든다."""
import os
import sys


def _prepare():
    # 창 없는 앱에서는 표준 출력이 없으므로 기록 파일로 돌린다
    if sys.stdout is None or sys.stderr is None or getattr(sys, "frozen", False):
        home = os.path.expanduser(os.environ.get("WURUBURURU_HOME", "~/.wurubururu"))
        os.makedirs(home, exist_ok=True)
        log = open(os.path.join(home, "wurubururu.log"), "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or log
        sys.stderr = log
    # Finder에서 실행하면 PATH가 짧아 Homebrew 도구(mpv 등)를 못 찾는다
    if sys.platform == "darwin":
        extra = ["/opt/homebrew/bin", "/usr/local/bin", os.path.expanduser("~/.local/bin")]
        os.environ["PATH"] = os.pathsep.join(extra + [os.environ.get("PATH", "")])


if __name__ == "__main__":
    _prepare()
    from wurubururu.cli import main
    main()
