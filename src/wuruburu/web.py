"""로컬 설정 화면과 알림 수신 API. 127.0.0.1 에서만 열리고, 변경 요청에는 토큰이 필요하다.

  GET  /                상태·설정 화면
  GET  /api/status      현재 상태 (JSON)
  POST /api/notify      외부 프로그램이 알림을 보냄 {title, body, url, priority}
  POST /api/command     버튼 명령 실행 {command}
  POST /api/led         LED 패턴 시험 {pattern}
  POST /api/config      설정 파일 저장 {text}
"""
from __future__ import annotations

import hmac
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources

from . import config
from .engine import Alert, Engine

MAX_BODY = 256 * 1024


def make_handler(engine: Engine, token: str):
    page = resources.files("wuruburu").joinpath("web.html").read_text(encoding="utf-8")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # 콘솔을 조용히
            pass

        def _send(self, code: int, body, ctype="application/json; charset=utf-8"):
            data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _local(self) -> bool:
            host = (self.headers.get("Host") or "").split(":")[0]
            return host in ("127.0.0.1", "localhost")

        def do_GET(self):
            if not self._local():
                return self._send(403, {"error": "local only"})
            if self.path == "/":
                html = page.replace("__TOKEN__", token)
                return self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
            if self.path == "/api/status":
                return self._send(200, engine.status())
            if self.path == "/api/config":
                config.ensure_home()
                return self._send(200, {"text": config.CONFIG_PATH.read_text(encoding="utf-8")})
            self._send(404, {"error": "not found"})

        def do_POST(self):
            if not self._local():
                return self._send(403, {"error": "local only"})
            if not hmac.compare_digest(self.headers.get("X-Wuruburu-Token", ""), token):
                return self._send(401, {"error": "token"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length > MAX_BODY:
                    return self._send(413, {"error": "too large"})
                data = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(data, dict):
                    raise ValueError("object expected")
            except (ValueError, json.JSONDecodeError) as e:
                return self._send(400, {"error": str(e)})
            try:
                if self.path == "/api/notify":
                    priority = data.get("priority", "normal")
                    ok = engine.post(Alert(
                        "notify", str(data.get("title", "알림"))[:200], str(data.get("body", ""))[:2000],
                        url=str(data.get("url", "")),
                        priority=priority if priority in ("urgent", "normal") else "normal"))
                    return self._send(200, {"ok": ok})
                if self.path == "/api/command":
                    engine.run_command(str(data.get("command", "none")))
                    return self._send(200, {"ok": True})
                if self.path == "/api/led":
                    engine.leds.flash(data.get("pattern", "test"), int(data.get("repeat", 2)))
                    return self._send(200, {"ok": True})
                if self.path == "/api/config":
                    config.save_text(str(data.get("text", "")))
                    return self._send(200, {"ok": True, "note": "다시 시작하면 적용됩니다"})
            except Exception as e:
                return self._send(400, {"error": str(e)})
            self._send(404, {"error": "not found"})

    return Handler


def start(engine: Engine, port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(engine, config.web_token()))
    threading.Thread(target=server.serve_forever, name="wuruburu-web", daemon=True).start()
    return server
