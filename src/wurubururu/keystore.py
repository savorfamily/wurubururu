"""API 키 같은 비밀값 보관.

맥은 키체인, 윈도우는 자격 증명 관리자에 저장한다(keyring).
keyring을 쓸 수 없는 환경이면 ~/.wurubururu/secrets.json 에 본인만 읽을 수 있게 저장한다.
"""
from __future__ import annotations

import json

from . import config

SERVICE = "wurubururu"


def _keyring():
    try:
        import keyring
        from keyring.backends import fail
        kr = keyring.get_keyring()
        if isinstance(kr, fail.Keyring):
            return None
        return keyring
    except Exception:
        return None


def _file_path():
    return config.HOME / "secrets.json"


def _file_load() -> dict:
    p = _file_path()
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _file_save(data: dict) -> None:
    config.ensure_home()
    p = _file_path()
    p.write_text(json.dumps(data), encoding="utf-8")
    try:
        p.chmod(0o600)
    except OSError:
        pass


def get(name: str) -> str:
    kr = _keyring()
    if kr is not None:
        try:
            v = kr.get_password(SERVICE, name)
            if v:
                return v
        except Exception:
            pass
    return _file_load().get(name, "")


def set(name: str, value: str) -> str:
    """저장하고 어디에 저장했는지 돌려준다. 빈 값이면 지운다."""
    value = (value or "").strip()
    if not value:
        delete(name)
        return "deleted"
    kr = _keyring()
    if kr is not None:
        try:
            kr.set_password(SERVICE, name, value)
            data = _file_load()
            if data.pop(name, None) is not None:
                _file_save(data)
            return "keychain"
        except Exception:
            pass
    data = _file_load()
    data[name] = value
    _file_save(data)
    return "file"


def delete(name: str) -> None:
    kr = _keyring()
    if kr is not None:
        try:
            kr.delete_password(SERVICE, name)
        except Exception:
            pass
    data = _file_load()
    if data.pop(name, None) is not None:
        _file_save(data)


def has(name: str) -> bool:
    return bool(get(name))
