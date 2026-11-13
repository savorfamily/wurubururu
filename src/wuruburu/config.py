"""설정 파일 읽기. 기본값(default_config.toml) 위에 사용자 설정을 덮어쓴다."""
from __future__ import annotations

import os
import secrets
import tomllib
from importlib import resources
from pathlib import Path

HOME = Path(os.environ.get("WURUBURU_HOME", "~/.wuruburu")).expanduser()
CONFIG_PATH = HOME / "config.toml"
TOKEN_PATH = HOME / "web_token"


def default_text() -> str:
    return resources.files("wuruburu").joinpath("default_config.toml").read_text(encoding="utf-8")


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def ensure_home() -> None:
    HOME.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(default_text(), encoding="utf-8")


def load(path: Path | None = None) -> dict:
    base = tomllib.loads(default_text())
    path = path or CONFIG_PATH
    if path.exists():
        return _merge(base, tomllib.loads(path.read_text(encoding="utf-8")))
    return base


def save_text(text: str) -> None:
    tomllib.loads(text)  # 문법 오류면 여기서 예외
    ensure_home()
    CONFIG_PATH.write_text(text, encoding="utf-8")


def web_token() -> str:
    """로컬 설정 화면과 notify 명령이 공유하는 비밀 토큰."""
    ensure_home()
    if not TOKEN_PATH.exists():
        TOKEN_PATH.write_text(secrets.token_urlsafe(24), encoding="utf-8")
        try:
            TOKEN_PATH.chmod(0o600)
        except OSError:
            pass
    return TOKEN_PATH.read_text(encoding="utf-8").strip()


def expand(p: str) -> Path:
    return Path(p).expanduser()
