"""Google 로그인(OAuth). 비밀번호는 저장하지 않고, 읽기 전용 권한 토큰만 ~/.wurubururu 에 둔다."""
from __future__ import annotations

from .. import config

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]
TOKEN_FILE = "google_token.json"


class GoogleSetupError(Exception):
    pass


BUNDLED_FILE = "google_client.json"   # 빌드할 때 GitHub 비밀값에서 넣는다 (저장소에는 없음)


def bundled_client() -> dict | None:
    """앱에 들어 있는 OAuth 클라이언트 (우르부르르 공용)."""
    import json
    from importlib import resources
    try:
        f = resources.files("wurubururu").joinpath("assets", BUNDLED_FILE)
        if f.is_file():
            data = json.loads(f.read_text(encoding="utf-8"))
            return data if "installed" in data else None
    except Exception:
        pass
    return None


def client_config(google_cfg: dict) -> dict | None:
    """쓸 OAuth 클라이언트. 사용자가 직접 올린 것이 있으면 그것, 없으면 앱에 들어 있는 것."""
    import json
    p = client_secret_path(google_cfg)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    return bundled_client()


def save_credentials(creds) -> None:
    token_path = config.HOME / TOKEN_FILE
    config.ensure_home()
    token_path.write_text(creds.to_json(), encoding="utf-8")
    try:
        token_path.chmod(0o600)
    except OSError:
        pass


def credentials(google_cfg: dict, interactive: bool = False):
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as e:
        raise GoogleSetupError('Google 연동 패키지가 없습니다: pip install "wurubururu[google]"') from e

    token_path = config.HOME / TOKEN_FILE
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    elif interactive:
        cc = client_config(google_cfg)
        if not cc:
            raise GoogleSetupError("Google 연결 정보가 없습니다 (설정 화면 → Gmail·캘린더 참고)")
        creds = InstalledAppFlow.from_client_config(cc, SCOPES).run_local_server(port=0)
    else:
        raise GoogleSetupError("Google 로그인이 필요합니다 (설정 화면 → Gmail·캘린더 → Google로 로그인)")
    save_credentials(creds)
    return creds


def service(name: str, version: str, google_cfg: dict):
    from googleapiclient.discovery import build
    return build(name, version, credentials=credentials(google_cfg), cache_discovery=False)


def client_secret_path(google_cfg: dict):
    """비워 두면 설정 폴더의 client_secret.json."""
    custom = (google_cfg.get("client_secret") or "").strip()
    return config.expand(custom) if custom else config.HOME / "client_secret.json"


def save_client_secret(google_cfg: dict, text: str) -> None:
    """설정 화면에서 올린 OAuth 클라이언트 JSON을 검사하고 저장한다."""
    import json
    data = json.loads(text)
    if not isinstance(data, dict) or not ({"installed", "web"} & set(data)):
        raise GoogleSetupError("OAuth 클라이언트 파일이 아닙니다 (데스크톱 앱 유형으로 만든 JSON이어야 합니다)")
    if "installed" not in data:
        raise GoogleSetupError("'웹 애플리케이션' 유형입니다. '데스크톱 앱' 유형으로 다시 만들어 주세요")
    p = client_secret_path(google_cfg)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data), encoding="utf-8")
    try:
        p.chmod(0o600)
    except OSError:
        pass


def status(google_cfg: dict) -> dict:
    token = config.HOME / TOKEN_FILE
    own = client_secret_path(google_cfg).exists()
    bundled = bundled_client() is not None
    return {"client_secret": own, "bundled": bundled, "ready": own or bundled, "logged_in": token.exists()}


SUCCESS_PAGE = """<!doctype html><meta charset="utf-8"><title>우르부르르</title>
<body style="font:16px -apple-system,'Segoe UI','Malgun Gothic',sans-serif;padding:48px;text-align:center">
<h2>{title}</h2><p>{body}</p><p style="color:#888">이 창은 닫으셔도 됩니다.</p>
<script>setTimeout(function(){{window.close()}}, 1500)</script></body>"""


class PopupLogin:
    """설정 화면의 'Google로 로그인' 버튼용.

    1. start(): 이 컴퓨터에서만 접속되는 임시 주소를 열고, Google 로그인 주소를 돌려준다.
       설정 화면은 그 주소를 작은 창(팝업)으로 연다.
    2. 사용자가 Google에서 계정을 고르고 허용하면 Google이 임시 주소로 돌아온다.
    3. 그 응답으로 토큰을 받아 저장하고 on_done()을 부른다.
    """

    def __init__(self, google_cfg: dict, on_done=None, timeout: int = 300):
        self.google_cfg = google_cfg
        self.on_done = on_done
        self.timeout = timeout
        self.running = False
        self.error: str | None = None
        self.url: str | None = None

    def start(self) -> str:
        import threading
        import urllib.parse
        from http.server import BaseHTTPRequestHandler, HTTPServer
        from google_auth_oauthlib.flow import Flow

        cc = client_config(self.google_cfg)
        if not cc:
            raise GoogleSetupError("Google 연결 정보가 없습니다")
        result: dict = {}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                if "code" not in q and "error" not in q:   # favicon 등은 무시
                    self.send_response(404)
                    self.end_headers()
                    return
                result["uri"] = self.path
                ok = "code" in q
                page = SUCCESS_PAGE.format(
                    title="Google 연결 완료" if ok else "Google 연결을 취소했습니다",
                    body="우르부르르가 새 메일과 일정을 알려드립니다." if ok else "설정 화면에서 다시 시도할 수 있습니다.")
                data = page.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        server = HTTPServer(("127.0.0.1", 0), Handler)
        server.timeout = 1
        flow = Flow.from_client_config(cc, scopes=SCOPES)
        flow.redirect_uri = f"http://127.0.0.1:{server.server_port}/"
        self.url, _ = flow.authorization_url(access_type="offline", prompt="consent")
        self.running, self.error = True, None

        def wait():
            import time
            deadline = time.monotonic() + self.timeout
            try:
                while "uri" not in result and time.monotonic() < deadline:
                    server.handle_request()
                if "uri" not in result:
                    raise GoogleSetupError("시간이 지나 로그인을 취소했습니다. 다시 눌러 주세요")
                q = urllib.parse.parse_qs(urllib.parse.urlparse(result["uri"]).query)
                if "error" in q:
                    raise GoogleSetupError("Google 로그인을 취소했습니다")
                # oauthlib은 https 주소만 받아들이므로 형식만 맞춘다 (이 컴퓨터 안의 통신)
                flow.fetch_token(authorization_response=flow.redirect_uri.replace("http", "https", 1)
                                 + result["uri"].lstrip("/"))
                save_credentials(flow.credentials)
                if self.on_done:
                    self.on_done()
            except Exception as e:
                self.error = str(e)
            finally:
                server.server_close()
                self.running = False

        threading.Thread(target=wait, name="wurubururu-google-login", daemon=True).start()
        return self.url


def logout() -> None:
    try:
        (config.HOME / TOKEN_FILE).unlink()
    except FileNotFoundError:
        pass
