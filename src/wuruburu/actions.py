"""기기 밖에서 일어나는 동작: 말하기, 화면 열기, 라디오 재생."""
from __future__ import annotations

import shutil
import subprocess
import sys
import webbrowser


def open_url(url: str) -> None:
    if url.startswith(("http://", "https://")):
        webbrowser.open(url)


def speak(text: str, cfg: dict | None = None) -> bool:
    """운영체제 기본 음성으로 읽는다. 읽기 시작에 성공하면 True."""
    cfg = cfg or {}
    text = " ".join((text or "").split())[:1500]
    if not text or not cfg.get("enabled", True):
        return False
    try:
        if sys.platform == "darwin":
            cmd = ["say"]
            if cfg.get("voice"):
                cmd += ["-v", cfg["voice"]]
            if cfg.get("audio_device"):
                cmd += ["-a", cfg["audio_device"]]
            subprocess.Popen(cmd + ["--", text])
        elif sys.platform == "win32":
            script = ("Add-Type -AssemblyName System.Speech; "
                      "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                      "$s.Speak([Console]::In.ReadToEnd())")
            p = subprocess.Popen(["powershell", "-NoProfile", "-Command", script],
                                 stdin=subprocess.PIPE, creationflags=0x08000000)
            p.stdin.write(text.encode("utf-8", "replace"))
            p.stdin.close()
        else:
            exe = shutil.which("espeak-ng") or shutil.which("espeak")
            if not exe:
                return False
            subprocess.Popen([exe, "--", text])
        return True
    except OSError:
        return False


class Radio:
    """외부 재생기(mpv, ffplay, vlc)로 인터넷 방송을 튼다."""

    def __init__(self, cfg: dict):
        self.stations = list(cfg.get("stations") or [])
        self.player = cfg.get("player") or ""
        self.index = 0
        self.proc: subprocess.Popen | None = None

    def _command(self, url: str) -> list[str] | None:
        known = (("mpv", ["--no-video", "--really-quiet"]),
                 ("ffplay", ["-nodisp", "-loglevel", "quiet"]),
                 ("vlc", ["--intf", "dummy"]))
        if self.player:
            args = next((a for n, a in known if n in self.player.lower()), [])
            return [self.player, *args, url]
        for name, args in known:
            exe = shutil.which(name)
            if exe:
                return [exe, *args, url]
        return None

    @property
    def playing(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def current(self) -> str:
        return self.stations[self.index].get("name", "") if self.stations else ""

    def stop(self) -> None:
        if self.playing:
            self.proc.terminate()
        self.proc = None

    def play(self) -> str:
        """재생을 시작하고 상태 문장을 돌려준다."""
        self.stop()
        if not self.stations:
            return "등록된 방송이 없습니다"
        url = str(self.stations[self.index].get("url", ""))
        cmd = self._command(url) if url.startswith(("http://", "https://")) else None
        if not cmd:
            return "재생기(mpv, ffplay, vlc)를 찾지 못했습니다"
        try:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as e:
            return f"재생 실패: {e}"
        return self.current()

    def toggle(self) -> str:
        if self.playing:
            self.stop()
            return "라디오 끔"
        return self.play()

    def next(self) -> str:
        if self.stations:
            self.index = (self.index + 1) % len(self.stations)
        return self.play()
