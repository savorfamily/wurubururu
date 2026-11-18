"""로컬 설정 화면과 API. 127.0.0.1 에서만 열리고, 바꾸는 요청에는 토큰이 필요하다.

  GET  /                     설정 화면
  GET  /api/status           현재 상태
  GET  /api/settings         설정 전체 + 키 저장 여부 + 자동 실행 + Google 상태
  POST /api/settings         설정 저장 후 즉시 적용 {cfg}
  POST /api/secret           API 키 저장 {name, value}
  POST /api/autostart        로그인 시 자동 실행 {enabled}
  POST /api/google/client    OAuth 클라이언트 JSON 저장 {text}
  POST /api/google/login     Google 로그인 시작 (브라우저가 열림)
  POST /api/google/logout    Google 연결 해제
  GET  /api/config           설정 파일 원문
  POST /api/config           설정 파일 원문 저장 {text}
  POST /api/notify           외부 알림 {title, body, url, priority}
  POST /api/command          버튼 명령 실행 {command}
  POST /api/led              LED 패턴 시험 {pattern}
  POST /api/ai/test          AI에 짧은 질문을 보내고 답을 읽어줌
  POST /api/quit             프로그램 끝내기
"""
from __future__ import annotations

import hmac
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources

from . import __version__, autostart, config, keystore
from .ai import KEY_ENV
from .engine import Alert
from .leds import BUILTIN

MAX_BODY = 256 * 1024
SECRET_NAMES = {f"ai.{p}" for p in KEY_ENV}


class GoogleLogin:
    """설정 화면의 'Google로 로그인' 버튼. 로그인은 브라우저에서 진행되므로 별도 스레드로 돌린다."""

    def __init__(self):
        self.running = False
        self.error: str | None = None
        self._lock = threading.Lock()

    def start(self, app) -> None:
        with self._lock:
            if self.running:
                return
            self.running, self.error = True, None
        threading.Thread(target=self._run, args=(app,), daemon=True).start()

    def _run(self, app) -> None:
        from .sources.google_auth import credentials
        try:
            credentials(app.cfg.get("google", {}), interactive=True)
            app.reload()
        except Exception as e:
            self.error = str(e)
        finally:
            self.running = False


def settings_payload(app, login: GoogleLogin) -> dict:
    from .sources.google_auth import status as google_status
    g = google_status(app.cfg.get("google", {}))
    g.update(login_running=login.running, error=login.error)
    return {
        "cfg": app.cfg,
        "secrets": {n: keystore.has(n) for n in sorted(SECRET_NAMES)},
        "autostart": {"supported": autostart.supported(), "enabled": autostart.is_enabled()},
        "google": g,
        "patterns": sorted(BUILTIN),
        "commands": sorted(app.engine.commands) if app.engine else [],
        "platform": sys.platform,
        "tray": app.icon is not None,
        "log_file": str(config.HOME / "wurubururu.log"),
        "version": __version__,
    }


def make_handler(app, token: str):
    page = resources.files("wurubururu").joinpath("web.html").read_text(encoding="utf-8")
    login = GoogleLogin()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
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
                st = app.engine.status() if app.engine else {"alerts": [], "log": [], "sources": []}
                st["device"] = app.device_status()
                st["version"] = __version__
                return self._send(200, st)
            if self.path == "/api/settings":
                return self._send(200, settings_payload(app, login))
            if self.path == "/api/config":
                config.ensure_home()
                return self._send(200, {"text": config.CONFIG_PATH.read_text(encoding="utf-8")})
            self._send(404, {"error": "not found"})

        def do_POST(self):
            if not self._local():
                return self._send(403, {"error": "local only"})
            if not hmac.compare_digest(self.headers.get("X-Wurubururu-Token", ""), token):
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
                return self._route(data)
            except Exception as e:
                return self._send(400, {"error": str(e)})

        def _route(self, data: dict):
            engine = app.engine
            path = self.path
            if path == "/api/notify":
                priority = data.get("priority", "normal")
                ok = engine.post(Alert(
                    "notify", str(data.get("title", "알림"))[:200], str(data.get("body", ""))[:2000],
                    url=str(data.get("url", "")),
                    priority=priority if priority in ("urgent", "normal") else "normal"))
                return self._send(200, {"ok": ok})
            if path == "/api/command":
                engine.run_command(str(data.get("command", "none")))
                return self._send(200, {"ok": True})
            if path == "/api/led":
                engine.leds.flash(data.get("pattern", "test"), int(data.get("repeat", 2)))
                return self._send(200, {"ok": True})
            if path == "/api/quit":
                threading.Timer(0.3, app.quit).start()
                return self._send(200, {"ok": True})
            if path == "/api/ai/test":
                if engine.provider is None:
                    raise ValueError(app.ai_error or "AI가 꺼져 있습니다")
                from .ai import AIError
                try:
                    text = engine.provider.complete(
                        "한국어로 한 문장만 답한다.", "우르부르르 알림 프로그램의 첫 인사를 한 문장으로 해줘.").strip()
                except AIError as e:
                    raise ValueError(str(e))
                engine.say(text)
                return self._send(200, {"ok": True, "text": text})
            if path == "/api/settings":
                cfg = data.get("cfg")
                if not isinstance(cfg, dict):
                    raise ValueError("cfg 가 필요합니다")
                config.save_dict(cfg)
                app.reload()
                return self._send(200, {"ok": True})
            if path == "/api/secret":
                name = str(data.get("name", ""))
                if name not in SECRET_NAMES:
                    raise ValueError("저장할 수 없는 항목입니다")
                where = keystore.set(name, str(data.get("value", "")))
                app.reload()
                return self._send(200, {"ok": True, "where": where})
            if path == "/api/autostart":
                autostart.set_enabled(bool(data.get("enabled")))
                return self._send(200, {"ok": True, "enabled": autostart.is_enabled()})
            if path == "/api/google/client":
                from .sources.google_auth import save_client_secret
                save_client_secret(app.cfg.get("google", {}), str(data.get("text", "")))
                return self._send(200, {"ok": True})
            if path == "/api/google/login":
                login.start(app)
                return self._send(200, {"ok": True})
            if path == "/api/google/logout":
                from .sources.google_auth import logout
                logout()
                app.reload()
                return self._send(200, {"ok": True})
            if path == "/api/config":
                config.save_text(str(data.get("text", "")))
                app.reload()
                return self._send(200, {"ok": True})
            return self._send(404, {"error": "not found"})

    return Handler


def start(app, port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app, config.web_token()))
    threading.Thread(target=server.serve_forever, name="wurubururu-web", daemon=True).start()
    return server
