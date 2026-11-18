"""설정 파일 읽기. 기본값(default_config.toml) 위에 사용자 설정을 덮어쓴다."""
from __future__ import annotations

import os
import secrets
import tomllib
from importlib import resources
from pathlib import Path

HOME = Path(os.environ.get("WURUBURURU_HOME", "~/.wurubururu")).expanduser()
CONFIG_PATH = HOME / "config.toml"
TOKEN_PATH = HOME / "web_token"


def default_text() -> str:
    return resources.files("wurubururu").joinpath("default_config.toml").read_text(encoding="utf-8")


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def ensure_home() -> None:
    HOME.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(HEADER, encoding="utf-8")


def is_first_run() -> bool:
    return not CONFIG_PATH.exists()


def load(path: Path | None = None) -> dict:
    base = tomllib.loads(default_text())
    path = path or CONFIG_PATH
    if path.exists():
        return _merge(base, tomllib.loads(path.read_text(encoding="utf-8")))
    return base


HEADER = """# wurubururu 설정 — 설정 화면에서 저장하면 기본값과 다른 항목만 이 파일에 남습니다.
# 기본값 전체는 config.example.toml 참고. API 키는 이 파일이 아니라 키체인에 저장됩니다.
"""


def defaults() -> dict:
    return tomllib.loads(default_text())


def save_dict(cfg: dict) -> None:
    """설정 전체(dict)를 받아 기본값과 다른 부분만 저장한다."""
    from .tomlwrite import diff, dumps
    text = dumps(diff(cfg, defaults()), header=HEADER)
    tomllib.loads(text)  # 다시 읽을 수 있는지 확인
    HOME.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(text, encoding="utf-8")


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
