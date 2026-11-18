"""HTTPS 연결 공통 설정.

앱으로 묶인 Python은 운영체제 인증서 저장소를 쓰지 못하는 경우가 있어서(맥),
certifi의 인증서 묶음으로 서버 인증서를 확인한다.
"""
from __future__ import annotations

import os
import ssl
import urllib.request

_ctx: ssl.SSLContext | None = None


def ca_file() -> str | None:
    try:
        import certifi
        return certifi.where()
    except Exception:
        return None


def ssl_context() -> ssl.SSLContext:
    global _ctx
    if _ctx is None:
        ca = ca_file()
        _ctx = ssl.create_default_context(cafile=ca) if ca else ssl.create_default_context()
    return _ctx


def use_bundled_certs() -> None:
    """다른 라이브러리(urllib을 직접 쓰는 곳 포함)도 같은 인증서 묶음을 쓰게 한다."""
    ca = ca_file()
    if ca and os.path.exists(ca):
        os.environ.setdefault("SSL_CERT_FILE", ca)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", ca)


def urlopen(req, timeout: float = 30):
    return urllib.request.urlopen(req, timeout=timeout, context=ssl_context())
