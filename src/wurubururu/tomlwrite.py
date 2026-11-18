"""설정 저장용 최소 TOML 작성기 (표준 라이브러리에는 읽기만 있다)."""
from __future__ import annotations

import re

_BARE = re.compile(r"^[A-Za-z0-9_-]+$")


def _key(k: str) -> str:
    return k if _BARE.match(k) else _str(k)


def _str(v: str) -> str:
    out = v.replace("\\", "\\\\").replace('"', '\\"')
    out = out.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    out = "".join(c if ord(c) >= 0x20 or c in "\\" else f"\\u{ord(c):04x}" for c in out)
    return f'"{out}"'


def _value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, str):
        return _str(v)
    if isinstance(v, list):
        if v and all(isinstance(x, dict) for x in v):
            items = ",\n  ".join(_inline(x) for x in v)
            return f"[\n  {items},\n]"
        return "[" + ", ".join(_value(x) for x in v) + "]"
    if isinstance(v, dict):
        return _inline(v)
    raise TypeError(f"TOML로 쓸 수 없는 값: {type(v).__name__}")


def _inline(d: dict) -> str:
    return "{ " + ", ".join(f"{_key(k)} = {_value(v)}" for k, v in d.items()) + " }"


def dumps(data: dict, header: str = "") -> str:
    lines: list[str] = [header.rstrip()] if header else []

    def table(prefix: list[str], d: dict) -> None:
        scalars = {k: v for k, v in d.items() if not isinstance(v, dict)}
        tables = {k: v for k, v in d.items() if isinstance(v, dict)}
        if prefix and (scalars or not tables):
            lines.append("")
            lines.append("[" + ".".join(_key(p) for p in prefix) + "]")
        for k, v in scalars.items():
            lines.append(f"{_key(k)} = {_value(v)}")
        for k, v in tables.items():
            table(prefix + [k], v)

    table([], data)
    return "\n".join(lines).strip() + "\n"


def diff(current: dict, base: dict) -> dict:
    """base(기본값)와 다른 부분만 남긴다."""
    out = {}
    for k, v in current.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            sub = diff(v, base[k])
            if sub:
                out[k] = sub
        elif k not in base or base[k] != v:
            out[k] = v
    return out
